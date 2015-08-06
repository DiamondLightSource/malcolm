#!/bin/env dls-python
from pkg_resources import require
from malcolm.core.device import Device, DState
from malcolm.core.method import wrap_method
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
# logging.basicConfig(level=logging.DEBUG)#,
# format="%(asctime)s;%(levelname)s;%(message)s")
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqComms.zmqDeviceClient import ZmqDeviceClient
from malcolm.zmqComms.zmqMalcolmRouter import ZmqMalcolmRouter
from malcolm.zmqComms.zmqDeviceWrapper import ZmqDeviceWrapper


class Counter(Device):

    def __init__(self, name):
        super(Counter, self).__init__(name)
        self.counter = 0

    def start_event_loop(self):
        import cothread
        self.cothread = cothread
        cothread.Spawn(self.do_count)

    def do_count(self):
        while True:
            self.counter += 1
            self.cothread.Sleep(0.01)

    @wrap_method(DState)
    def get_count(self):
        return self.counter

    @wrap_method(DState)
    def hello(self):
        self.cothread.Sleep(0.1)
        return "world"

    @wrap_method(DState)
    def long_hello(self):
        self.cothread.Sleep(0.5)
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
        self.caller_sock = make_sock(
            self.context, zmq.DEALER, fe_addr, bind=False)
        self.fr = ZmqMalcolmRouter(fe_addr=fe_addr, be_addr=be_addr, timeout=1)
        self.fr.start()
        self.dw = ZmqDeviceWrapper("zebra3", Counter, be_addr, timeout=1)
        self.dw.start()
        self.fc = ZmqDeviceClient("zebra3", fe_addr=fe_addr, timeout=1)
        self.fc.run(block=False)

    def test_simple_function(self):
        time.sleep(0.2)
        # Start time

        def g():
            return self.fc.call("long_hello")
        self.assertAlmostEqual(self.fc.call("get_count"), 20, delta=1)
        self.assertEqual(self.fc.call("hello"), "world")
        # Hello world takes about 10 ticks
        self.assertAlmostEqual(self.fc.call("get_count"), 30, delta=1)
        # Do a long running call
        import cothread
        s = cothread.Spawn(g)
        # Check it returns immediately
        self.assertAlmostEqual(self.fc.call("get_count"), 30, delta=1)
        self.assertEqual(self.fc.call("hello"), "world")
        # Hello world takes 10 ticks
        self.assertAlmostEqual(self.fc.call("get_count"), 40, delta=1)
        self.assertEqual(s.Wait(), "long world")
        # Long hello takes about 50 ticks from send
        self.assertAlmostEqual(self.fc.call("get_count"), 80, delta=1)

    def tearDown(self):
        """
        Sends a kill message to the pp and waits for the process to terminate.

        """
        # Send a stop message to the prong process and wait until it joins
        self.caller_sock.send(
            json.dumps(dict(id=0, type="Call", method="malcolm.pleasestopnow")))
        self.fr.join()
        self.dw.join()
        self.caller_sock.close()
        self.fc.wait_loops()


if __name__ == '__main__':
    unittest.main(verbosity=2)
