#!/bin/env dls-python
from pkg_resources import require
from test.zmqComms.support import make_sock
require("mock")
require("pyzmq")
import unittest
import sys
import os
import multiprocessing
import json
import zmq
import time

import logging
logging.basicConfig()
#logging.basicConfig(level=logging.DEBUG)
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
        self.fr.handle_fe([client, request])
        self.fr.fe_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])

    def test_list_no_devices(self):
        self.expected_reply = json.dumps(dict(id=0, type="return", val=[]))
        self.send_request_check_reply(id=0, type="call", method="malcolm.devices")

    def test_get_malcolm_returns_devices(self):
        self.expected_reply = '{"type": "return", "id": 0, "val": {"methods": {"devices": {"descriptor": "List all available malcolm devices", "args": {}}, "pleasestopnow": {"descriptor": "Stop the router and all of the devices attached to it", "args": {}}}}}'
        self.send_request_check_reply(id=0, type="get", param="malcolm")

    def test_get_device_forwarded_single_device(self):
        client = "CUUID"
        data = json.dumps(
            dict(id=0, type="ready", device="zebra1"))
        device = "DUUID"
        self.fr.handle_be([device, client, data])
        request = json.dumps(dict(id=0, type="get", param="zebra1.status"))
        self.fr.handle_fe([client, request])
        self.fr.be_stream.send_multipart.assert_called_once_with(
            [device, client, request])

    @patch("malcolm.zmqComms.functionRouter.log.exception")
    def test_no_providers_error(self, mock_exception):
        self.expected_reply = json.dumps(
            dict(id=0, type="error", name="AssertionError", message="No device named foo registered"))
        self.send_request_check_reply(id=0, type="call", method="foo.func", args=dict(bar="bat"))
        self.assertEqual(mock_exception.call_count, 1)

    def test_single_provider(self):
        client = "CUUID"
        data = json.dumps(
            dict(type="ready", device="zebra1"))
        device = "DUUID"
        self.fr.handle_be([device, client, data])
        request = json.dumps(dict(id=0, type="call", method="zebra1.do"))
        self.fr.handle_fe([client, request])
        self.fr.be_stream.send_multipart.assert_called_once_with(
            [device, client, request])

    def test_provider_responds(self):
        client = "CUUID"
        device = "DUUID"
        data = json.dumps(dict(id=0, type="return", val=[]))
        self.fr.handle_be([device, client, data])
        self.fr.fe_stream.send_multipart.assert_called_once_with(
            [client, data])


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
        for x in sys.modules.keys():
            if x.startswith("cothread"):
                del sys.modules[x]        
        self.caller_sock = make_sock(self.context, zmq.DEALER, fe_addr, bind=False)
        self.dev_sock = make_sock(self.context, zmq.DEALER, be_addr, bind=False)
        self.fr = FunctionRouter(fe_addr=fe_addr, be_addr=be_addr, timeout=1)
        self.fr.start()

    def test_single_provider_callsback(self):
        ready = json.dumps(
            dict(type="ready", device="zebra1"))
        self.dev_sock.send_multipart(["malcolm", ready])
        # give it time to register zebra
        time.sleep(0.2)
        request = json.dumps(dict(id=0, type="call", method="zebra1.do"))
        self.caller_sock.send(request)
        at_device = self.dev_sock.recv_multipart()
        self.assertEqual(at_device[1], request)
        # send a function response
        response = json.dumps(dict(id=0, type="return", name=None))
        self.dev_sock.send_multipart([at_device[0], response])
        at_req = self.caller_sock.recv()
        self.assertEqual(at_req, response)

    def test_single_provider_getsback(self):
        ready = json.dumps(
            dict(type="ready", device="zebra1"))
        self.dev_sock.send_multipart(["malcolm", ready])
        # give it time to register zebra
        time.sleep(0.2)
        request = json.dumps(dict(id=0, type="get", param="zebra1.status"))
        self.caller_sock.send(request)
        at_device = self.dev_sock.recv_multipart()
        self.assertEqual(at_device[1], request)
        # send a function response
        response = json.dumps(dict(id=0, type="return", val=dict(message="Message", percent=54.3)))
        self.dev_sock.send_multipart([at_device[0], response])
        at_req = self.caller_sock.recv()
        self.assertEqual(at_req, response)

    def tearDown(self):
        """
        Sends a kill message to the pp and waits for the process to terminate.

        """
        # Send a stop message to the prong process and wait until it joins
        self.caller_sock.send(json.dumps(dict(id=-1, type="call", method="malcolm.pleasestopnow")))
        self.fr.join()

        self.caller_sock.close()
        self.dev_sock.close()

if __name__ == '__main__':
    unittest.main(verbosity=2)
