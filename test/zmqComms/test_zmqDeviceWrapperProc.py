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
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqComms.zmqDeviceWrapper import ZmqDeviceWrapper


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

    def exit(self):
        pass

class ZmqDeviceWrapperProcTest(unittest.TestCase):

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
        self.dw = ZmqDeviceWrapper("zebra2", Counter, be_addr=be_addr, timeout=1)
        self.dw.start()
        self.ready = self.router_sock.recv_multipart()

    def test_initial_ready(self):
        self.assertEqual(self.ready[1], "")
        self.assertEqual(self.ready[2], json.dumps(
            dict(type="Ready", device="zebra2")))

    def test_simple_function(self):
        self.expected_reply = json.dumps(
            dict(id=0, type="Return", val="world me"))
        self.router_sock.send_multipart(
            [self.ready[0], "", json.dumps(dict(id=0, type="Call", method="zebra2.hello", args=dict(who="me")))])
        recv = self.router_sock.recv_multipart()
        self.assertEqual(recv[2], self.expected_reply)

    def test_cothread_working(self):
        time.sleep(0.5)
        self.router_sock.send_multipart(
            [self.ready[0], "", json.dumps(dict(id=0, type="Call", method="zebra2.get_count", args={}))])
        recv = self.router_sock.recv_multipart()
        self.assertAlmostEqual(json.loads(recv[2])["val"], 50, delta=1)

    def test_simple_get(self):
        self.expected_reply = json.dumps(
            dict(id=0, type="Return", val=dict(message="Message", percent=54.3)))
        self.router_sock.send_multipart(
            [self.ready[0], "", json.dumps(dict(id=0, type="Get", param="zebra2.status"))])
        recv = self.router_sock.recv_multipart()
        self.assertEqual(recv[2], self.expected_reply)

    def tearDown(self):
        """
        Sends a kill message to the pp and waits for the process to terminate.

        """
        # Send a stop message to the prong process and wait until it joins
        self.router_sock.send_multipart(
            [self.ready[0], "", json.dumps(dict(id=0, type="Call", method="zebra2.exit"))])
        self.dw.join()
        self.router_sock.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
