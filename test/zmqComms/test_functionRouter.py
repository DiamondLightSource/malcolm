#!/bin/env dls-python
from pkg_resources import require
require("mock")
require("pyzmq")
import unittest
import sys
import os
import multiprocessing
import json
import zmq
import time
from support import make_sock

#import logging
# logging.basicConfig(level=logging.DEBUG)
from mock import patch, MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqComms.functionRouter import FunctionRouter


class FunctionRouterTest(unittest.TestCase):

    def setUp(self):
        self.fr = FunctionRouter()
        self.fr.fe_stream = MagicMock()
        self.fr.be_stream = MagicMock()
        self.fr.cs_stream = MagicMock()

    def send_request_check_reply(self, **args):
        client = "CUUID"
        request = json.dumps(args)
        self.fr.handle_fe([client, "", request])
        self.fr.fe_stream.send_multipart.assert_called_once_with(
            [client, "", self.expected_reply])

    def test_list_no_devices(self):
        self.expected_reply = json.dumps(dict(type="return", val=[]))
        self.send_request_check_reply(type="call", device="malcolm", method="devices")

    def test_get_malcolm_returns_devices(self):
        self.expected_reply = '{"type": "return", "val": {"methods": {"devices": {"descriptor": "List all available malcolm devices", "args": {}}, "pleasestopnow": {"descriptor": "Stop the router and all of the devices attached to it", "args": {}}}}}'
        self.send_request_check_reply(type="get", device="malcolm")

    def test_get_device_forwarded_single_device(self):
        client = "CUUID"
        data = json.dumps(
            dict(type="ready", device="zebra1", pubsocket="ipc://zebra1"))
        device = "DUUID"
        self.fr.handle_be([device, client, "", data])
        request = json.dumps(dict(type="get", device="zebra1", param="status"))
        self.fr.handle_fe([client, "", request])
        self.fr.be_stream.send_multipart.assert_called_once_with(
            [device, client, "", request])

    def test_no_providers_error(self):
        self.expected_reply = json.dumps(
            dict(type="error", name="AssertionError", message="No device named foo registered"))
        self.send_request_check_reply(type="call", device="foo", method="func", args=dict(bar="bat"))

    def test_single_provider(self):
        client = "CUUID"
        data = json.dumps(
            dict(type="ready", device="zebra1", pubsocket="ipc://zebra1"))
        device = "DUUID"
        self.fr.handle_be([device, client, "", data])
        request = json.dumps(dict(type="call", device="zebra1", method="do"))
        self.fr.handle_fe([client, "", request])
        self.fr.be_stream.send_multipart.assert_called_once_with(
            [device, client, "", request])

    def test_provider_responds(self):
        client = "CUUID"
        device = "DUUID"
        data = json.dumps(dict(type="return", val=[]))
        self.fr.handle_be([device, client, "", data])
        self.fr.fe_stream.send_multipart.assert_called_once_with(
            [client, "", data])


class FunctionRouterProcTest(unittest.TestCase):

    def setUp(self):
        """
        Creates and starts a PongProc process and sets up sockets to
        communicate with it.

        """
        self.context = zmq.Context()

        # make_sock creates and connects a TestSocket that we will use to
        # mimic the Ping process
        fe_addr = "ipc://frfe.ipc"
        be_addr = "ipc://frbe.ipc"
        self.req_sock = make_sock(self.context, zmq.REQ,
                                  connect=fe_addr)
        self.dev_sock = make_sock(self.context, zmq.DEALER,
                                  connect=be_addr)
        self.fr = FunctionRouter(fe_addr=fe_addr, be_addr=be_addr)
        self.fr.start()

    def test_no_providers_error(self):
        request = json.dumps(dict(type="call", device="foo", method="func", args=dict(bar="bat")))
        self.req_sock.send(request)
        reply = self.req_sock.recv()
        expected = json.dumps(
            dict(type="error", name="AssertionError", message="No device named foo registered"))
        self.assertEqual(reply, expected)

    def test_single_provider_callsback(self):
        ready = json.dumps(
            dict(type="ready", device="zebra1", pubsocket="ipc://zebra1.ipc"))
        self.dev_sock.send_multipart(["malcolm", "", ready])
        # give it time to register zebra
        time.sleep(0.2)
        request = json.dumps(dict(type="call", device="zebra1", method="do"))
        self.req_sock.send(request)
        at_device = self.dev_sock.recv_multipart()
        self.assertEqual(at_device[1], "")
        self.assertEqual(at_device[2], request)
        # send a function response
        response = json.dumps(dict(type="return", name=None))
        self.dev_sock.send_multipart([at_device[0], "", response])
        at_req = self.req_sock.recv()
        self.assertEqual(at_req, response)

    def test_single_provider_getsback(self):
        ready = json.dumps(
            dict(type="ready", device="zebra1", pubsocket="ipc://zebra1.ipc"))
        self.dev_sock.send_multipart(["malcolm", "", ready])
        # give it time to register zebra
        time.sleep(0.2)
        request = json.dumps(dict(type="get", device="zebra1", method="status"))
        self.req_sock.send(request)
        at_device = self.dev_sock.recv_multipart()
        self.assertEqual(at_device[1], "")
        self.assertEqual(at_device[2], request)
        # send a function response
        response = json.dumps(dict(type="return", val=dict(message="Message", percent=54.3)))
        self.dev_sock.send_multipart([at_device[0], "", response])
        at_req = self.req_sock.recv()
        self.assertEqual(at_req, response)

    def tearDown(self):
        """
        Sends a kill message to the pp and waits for the process to terminate.

        """
        # Send a stop message to the prong process and wait until it joins
        self.req_sock.send(json.dumps(dict(type="call", device="malcolm", method="pleasestopnow")))
        self.fr.join()

        self.req_sock.close()
        self.dev_sock.close()

if __name__ == '__main__':
    unittest.main(verbosity=2)
