#!/bin/env dls-python
from pkg_resources import require
from malcolm.zmqComms.serialize import serialize_call, serialize_return
from malcolm.devices.dummyDet import DummyDet
require("mock")
require("pyzmq")
require("cothread")
import cothread
import unittest
import sys
import os
import multiprocessing
import json
import zmq
import time
from support import make_sock, decorate

#import logging
#logging.basicConfig(level=logging.DEBUG, format="%(asctime)s;%(levelname)s;%(message)s")
from mock import patch, MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqComms.functionCaller import FunctionCaller
from malcolm.zmqComms.functionRouter import FunctionRouter
from malcolm.zmqComms.deviceWrapper import DeviceWrapper

class Counter(object):

    def __init__(self, name):
        self.counter = 0

    def start_event_loop(self):
        cothread.Spawn(self.do_count)

    def do_count(self):
        while True:
            self.counter += 1
            cothread.Sleep(0.1)

    @decorate
    def get_count(self):
        return self.counter

    @decorate
    def hello(self):
        cothread.Sleep(0.1)
        return "world"
    
    @decorate
    def long_hello(self):
        cothread.Sleep(0.5)
        return "long world"


class ZmqSystemTest(unittest.TestCase):

    def setUp(self):
        """
        Creates and starts a PongProc process and sets up sockets to
        communicate with it.

        """
        self.context = zmq.Context()
        be_addr = "ipc://frbe.ipc"
        fe_addr = "ipc://frfe.ipc"
        self.req_sock = make_sock(self.context, zmq.REQ,
                          connect=fe_addr)
        self.fr = FunctionRouter(fe_addr=fe_addr, be_addr=be_addr)
        self.fr.start()
        self.dw = DeviceWrapper("zebra3", Counter, be_addr)
        self.dw.start()
        self.fc = FunctionCaller("zebra3", fe_addr=fe_addr)
        self.fc2 = FunctionCaller("zebra3", fe_addr=fe_addr)

    def test_simple_function(self):
        time.sleep(0.2)
        self.assertEqual(self.fc.call("get_count"), 2)
        self.assertEqual(self.fc.call("hello"), "world")
        self.assertEqual(self.fc.call("get_count"), 3)
        self.fc.socket.send(serialize_call("zebra3", "long_hello"))
        self.assertEqual(self.fc2.call("get_count"), 3)
        self.assertEqual(self.fc2.call("hello"), "world")
        self.assertEqual(self.fc2.call("get_count"), 5)
        self.assertEqual(self.fc.socket.recv(), serialize_return("long world"))
        self.assertEqual(self.fc.call("get_count"), 8)

    def tearDown(self):
        """
        Sends a kill message to the pp and waits for the process to terminate.

        """
        # Send a stop message to the prong process and wait until it joins
        self.req_sock.send(json.dumps(dict(type="call", device="malcolm", method="stop")))
        self.fr.join()
        self.dw.join()
        self.req_sock.close()

class ZmqDetSystemTest(unittest.TestCase):

    def setUp(self):
        """
        Creates and starts a PongProc process and sets up sockets to
        communicate with it.

        """
        self.context = zmq.Context()
        be_addr = "ipc://frbe.ipc"
        fe_addr = "ipc://frfe.ipc"
        self.req_sock = make_sock(self.context, zmq.REQ,
                          connect=fe_addr)
        self.fr = FunctionRouter(fe_addr=fe_addr, be_addr=be_addr)
        self.fr.start()
        self.dw = DeviceWrapper("det", DummyDet, be_addr)
        self.dw.start()
        self.fc = FunctionCaller("det", fe_addr=fe_addr)

    def test_configure_run(self):
        time.sleep(0.2)
        now = time.time()
        self.fc.call("configure_run", nframes=5, exposure=0.1)
        then = time.time()
        self.assertAlmostEqual(then-now, 0.5, delta=0.08)

    def tearDown(self):
        """
        Sends a kill message to the pp and waits for the process to terminate.

        """
        # Send a stop message to the prong process and wait until it joins
        self.req_sock.send(json.dumps(dict(type="call", device="malcolm", method="stop")))
        self.fr.join()
        self.dw.join()
        self.req_sock.close()

if __name__ == '__main__':
    unittest.main(verbosity=2)
    
    
    