#!/bin/env dls-python
from pkg_resources import require
from test.zmqComms.support import make_sock
require("mock")
require("pyzmq")
import unittest
import sys
import os
import json
import zmq
import time

#import logging
# logging.basicConfig(level=logging.DEBUG)
from mock import MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqComms.deviceWrapper import DeviceWrapper


class DeviceWrapperTest(unittest.TestCase):

    def setUp(self):
        self.dw = DeviceWrapper("zebra1", object)
        self.dw.device = MagicMock()
        self.dw.be_stream = MagicMock()

    def send_request(self, **args):
        client = "CUUID"
        request = json.dumps(args)
        self.dw.handle_be([client, request])
        return client

    def test_no_matching_func_error(self):
        self.expected_reply = json.dumps(
            dict(id=0, type="error", name="AssertionError", message="Invalid function foo"))
        client = self.send_request(id=0,
                                   type="call", method="zebra1.foo", args=dict(bar="bat"))
        self.dw.be_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])

    def test_wrong_device_name_error(self):
        self.expected_reply = json.dumps(
            dict(id=0, type="error", name="AssertionError", message="Wrong device name thing"))
        client = self.send_request(id=0,
                                   type="call", method="thing.foo", args=dict(bar="bat"))
        self.dw.be_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])

    def test_simple_function(self):
        def func():
            return "done"
        self.dw.device.methods = dict(func=func)
        self.expected_reply = json.dumps(
            dict(id=0, type="return", val="done"))
        client = self.send_request(id=0,
                                   type="call", method="zebra1.func", args={})
        # running this directly, not under the ioloop, so get to yield manually
        import cothread
        cothread.Yield()
        self.dw.be_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])

    def test_simple_get(self):
        class dev:

            def to_dict(self):
                return dict(status=dict(message="boo"), attributes={})
        self.dw.device = dev()
        self.expected_reply = json.dumps(
            dict(id=0, type="return", val=dict(status=dict(message="boo"), attributes={})))
        client = self.send_request(id=0,
                                   type="get", param="zebra1")
        self.dw.be_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])

    def test_parameter_get(self):
        class dev:

            def to_dict(self):
                return dict(status=dict(message="boo"), attributes={})
        self.dw.device = dev()
        self.expected_reply = json.dumps(
            dict(id=0, type="return", val="boo"))
        client = self.send_request(id=0,
                                   type="get", param="zebra1.status.message")
        self.dw.be_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])

    def test_status_function(self):
        def add_listener(send_status):
            self.send_status = send_status
        self.dw.device.add_listener.side_effect = add_listener

        def func():
            for i in range(10):
                self.send_status(i=i)
            return "done"
        self.dw.device.methods = dict(func=func)
        client = self.send_request(id=0,
                                   type="call", method="zebra1.func", args={})
        # running this directly, not under the ioloop, so get to yield manually
        import cothread
        cothread.Yield()
        cuuids = [a[0][0][0]
                  for a in self.dw.be_stream.send_multipart.call_args_list]
        expected = ["CUUID"] * 11
        self.assertEqual(cuuids, expected)
        messages = [a[0][0][1]
                    for a in self.dw.be_stream.send_multipart.call_args_list]
        expected = [json.dumps(dict(id=0, type="value", val=dict(i=i))) for i in range(10)] + \
            [json.dumps(dict(id=0, type="return", val="done"))]
        self.assertEqual(messages, expected)
        self.dw.device.remove_listener.assert_called_once_with(self.send_status)

class Counter(object):

    def __init__(self, name):
        self.counter = 0
        self.status = dict(message="Message", percent=54.3)
        self.attributes = dict(
            who=dict(descriptor="Who name", value="Me", tags=["hello"]))
        self.methods = dict(get_count=self.get_count, hello=self.hello)

    def add_listener(self, func):
        pass
    
    def remove_listener(self, func):
        pass

    def start_event_loop(self):
        import cothread
        cothread.Spawn(self.do_count)

    def do_count(self):
        import cothread
        while True:
            self.counter += 1
            cothread.Sleep(0.01)

    def get_count(self):
        return self.counter

    def hello(self, who):
        return "world {}".format(who)

    def to_dict(self):
        return dict(status=self.status, attributes=self.attributes, methods=self.methods)


class DeviceWrapperProcTest(unittest.TestCase):

    def setUp(self):
        """
        Creates and starts a PongProc process and sets up sockets to
        communicate with it.

        """

        # make_sock creates and connects a TestSocket that we will use to
        # mimic the Ping process
        for x in sys.modules.keys():
            if x.startswith("cothread"):
                del sys.modules[x]
        be_addr = "ipc://frbe.ipc"
        self.router_sock = make_sock(
            zmq.Context(), zmq.ROUTER, be_addr, bind=True)
        self.dw = DeviceWrapper("zebra2", Counter, be_addr=be_addr, timeout=1)
        self.dw.start()
        self.ready = self.router_sock.recv_multipart()

    def test_initial_ready(self):
        self.assertEqual(self.ready[1], "")
        self.assertEqual(self.ready[2], json.dumps(
            dict(type="ready", device="zebra2")))

    def test_simple_function(self):
        self.expected_reply = json.dumps(
            dict(id=0, type="return", val="world me"))
        self.router_sock.send_multipart(
            [self.ready[0], "", json.dumps(dict(id=0, type="call", method="zebra2.hello", args=dict(who="me")))])
        recv = self.router_sock.recv_multipart()
        self.assertEqual(recv[2], self.expected_reply)

    def test_cothread_working(self):
        time.sleep(0.5)
        self.router_sock.send_multipart(
            [self.ready[0], "", json.dumps(dict(id=0, type="call", method="zebra2.get_count", args={}))])
        recv = self.router_sock.recv_multipart()
        self.assertAlmostEqual(json.loads(recv[2])["val"], 50, delta=1)

    def test_simple_get(self):
        self.expected_reply = json.dumps(
            dict(id=0, type="return", val=dict(message="Message", percent=54.3)))
        self.router_sock.send_multipart(
            [self.ready[0], "", json.dumps(dict(id=0, type="get", param="zebra2.status"))])
        recv = self.router_sock.recv_multipart()
        self.assertEqual(recv[2], self.expected_reply)

    def tearDown(self):
        """
        Sends a kill message to the pp and waits for the process to terminate.

        """
        # Send a stop message to the prong process and wait until it joins
        self.router_sock.send_multipart(
            [self.ready[0], "", json.dumps(dict(id=0, type="call", method="zebra2.pleasestopnow"))])
        self.dw.join()
        self.router_sock.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
