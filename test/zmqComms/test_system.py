#!/bin/env dls-python
from pkg_resources import require
from malcolm.zmqComms.serialize import serialize_call, serialize_return
from malcolm.devices.dummyDet import DummyDet
from malcolm.core.device import Device, DState
from malcolm.core.method import wrap_method
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
#logging.basicConfig(level=logging.DEBUG)#, format="%(asctime)s;%(levelname)s;%(message)s")
from mock import patch, MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqComms.functionCaller import FunctionCaller
from malcolm.zmqComms.functionRouter import FunctionRouter
from malcolm.zmqComms.deviceWrapper import DeviceWrapper
import difflib

class Counter(Device):

    def __init__(self, name):
        super(Counter, self).__init__(name)
        self.counter = 0

    def start_event_loop(self):
        cothread.Spawn(self.do_count)

    def do_count(self):
        while True:
            self.counter += 1
            cothread.Sleep(0.01)

    @wrap_method(DState)
    def get_count(self):
        return self.counter

    @wrap_method(DState)
    def hello(self):
        cothread.Sleep(0.1)
        return "world"
    
    @wrap_method(DState)
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
        self.dealer_sock = make_sock(self.context, zmq.REQ,
                          connect=fe_addr)
        self.fr = FunctionRouter(fe_addr=fe_addr, be_addr=be_addr)
        self.fr.start()
        self.dw = DeviceWrapper("zebra3", Counter, be_addr)
        self.dw.start()
        self.fc = FunctionCaller("zebra3", fe_addr=fe_addr)
        self.fc2 = FunctionCaller("zebra3", fe_addr=fe_addr)

    def test_simple_function(self):
        time.sleep(0.2)
        # Start time
        self.assertAlmostEqual(self.fc.call("get_count"), 20, delta=1)
        self.assertEqual(self.fc.call("hello"), "world")
        # Hello world takes about 10 ticks
        self.assertAlmostEqual(self.fc.call("get_count"), 30, delta=1)
        # Do a long running call
        self.fc.socket.send(serialize_call("zebra3", "long_hello"))
        # Check it returns immediately
        self.assertAlmostEqual(self.fc2.call("get_count"), 30, delta=1)
        self.assertEqual(self.fc2.call("hello"), "world")
        # Hello world takes 10 ticks
        self.assertAlmostEqual(self.fc2.call("get_count"), 40, delta=1)
        self.assertEqual(self.fc.socket.recv(), serialize_return("long world"))
        # Long hello takes about 50 ticks from send
        self.assertAlmostEqual(self.fc.call("get_count"), 80, delta=1)

    def tearDown(self):
        """
        Sends a kill message to the pp and waits for the process to terminate.

        """
        # Send a stop message to the prong process and wait until it joins
        self.dealer_sock.send(json.dumps(dict(type="call", device="malcolm", method="pleasestopnow")))
        self.fr.join()
        self.dw.join()
        self.dealer_sock.close()

class ZmqDetSystemTest(unittest.TestCase):
    def assertStringsEqual(self, first, second):
        """Assert that two multi-line strings are equal.
        If they aren't, show a nice diff.
        """
        self.assertTrue(isinstance(first, str), 'First arg is not a string')
        self.assertTrue(isinstance(second, str), 'Second arg is not a string')

        if first != second:
            message = ''.join(difflib.unified_diff(
                    first.splitlines(True), second.splitlines(True)))
            self.fail("Multi-line strings are unequal: %s\n" % message) 
    def setUp(self):
        """
        Creates and starts a PongProc process and sets up sockets to
        communicate with it.

        """
        self.context = zmq.Context()
        be_addr = "ipc://frbe.ipc"
        fe_addr = "ipc://frfe.ipc"
        self.dealer_sock = make_sock(self.context, zmq.REQ,
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

    def test_get(self):
        time.sleep(0.2)
        ret = self.fc.get()
        pretty = json.dumps(ret, indent=2)
        expected = r'''{
  "status": {
    "timeStamp": null, 
    "state": {
      "index": 1, 
      "choices": [
        "Fault", 
        "Idle", 
        "Configuring", 
        "Ready", 
        "Running", 
        "Pausing", 
        "Paused", 
        "Aborting", 
        "Aborted"
      ]
    }, 
    "message": ""
  }, 
  "attributes": {
    "nframes": {
      "descriptor": "Number of frames", 
      "type": "int", 
      "value": null
    }, 
    "exposure": {
      "descriptor": "Detector exposure", 
      "type": "float", 
      "value": null
    }
  }, 
  "methods": {
    "reset": {
      "descriptor": "Try and reset the device into DState.Idle. It blocks until the \n        device is in a rest state:\n         * Normally it will return a DState.Idle Status\n         * If something goes wrong it will return a DState.Fault Status\n        ", 
      "args": {}, 
      "valid_states": [
        "Fault", 
        "Aborted"
      ]
    }, 
    "pause": {
      "descriptor": "Pause a run so that it can be resumed later. It blocks until the\n        device is in a rest state:\n         * Normally it will return a DState.Paused Status\n         * If the user aborts then it will return a DState.Aborted Status\n         * If something goes wrong it will return a DState.Fault Status\n        ", 
      "args": {}, 
      "valid_states": [
        "Running"
      ]
    }, 
    "run": {
      "descriptor": "Start a configured device running. It blocks until the device is in a\n        rest state:\n         * Normally it will return a DState.Idle Status\n         * If the device allows many runs from a single configure the it\n           will return a DState.Ready Status\n         * If the user aborts then it will return a DState.Aborted Status\n         * If something goes wrong it will return a DState.Fault Status\n        ", 
      "args": {}, 
      "valid_states": [
        "Ready", 
        "Paused"
      ]
    }, 
    "configure": {
      "descriptor": "Assert params are valid, then use them to configure a device for a run.\n        It blocks until the device is in a rest state:\n         * Normally it will return a DState.Configured Status\n         * If the user aborts then it will return a DState.Aborted Status\n         * If something goes wrong it will return a DState.Fault Status\n        ", 
      "args": {}, 
      "valid_states": [
        "Idle", 
        "Ready"
      ]
    }, 
    "assert_valid": {
      "descriptor": "Check whether the configuration parameters are valid or not. This set\n        of parameters are checked in isolation, no device state is taken into\n        account. It raises an error if the set of configuration parameters is\n        invalid.\n        ", 
      "args": {}, 
      "valid_states": [
        "Fault", 
        "Idle", 
        "Configuring", 
        "Ready", 
        "Running", 
        "Pausing", 
        "Paused", 
        "Aborting", 
        "Aborted"
      ]
    }, 
    "abort": {
      "descriptor": "Abort configuration or abandon the current run whether it is\n        running or paused. It blocks until the device is in a rest state:\n         * Normally it will return a DState.Aborted Status\n         * If something goes wrong it will return a DState.Fault Status\n        ", 
      "args": {}, 
      "valid_states": [
        "Configuring", 
        "Ready", 
        "Running", 
        "Pausing", 
        "Paused"
      ]
    }, 
    "configure_run": {
      "descriptor": "Try and configure and run a device in one step. It blocks until the\n        device is in a rest state:\n         * Normally it will return a DState.Idle Status\n         * If the device allows many runs from a single configure then it\n           will return a DState.Ready Status\n         * If the user aborts then it will return a DState.Aborted Status\n         * If something goes wrong it will return a DState.Fault Status\n        ", 
      "args": {}, 
      "valid_states": [
        "Fault", 
        "Idle", 
        "Configuring", 
        "Ready", 
        "Running", 
        "Pausing", 
        "Paused", 
        "Aborting", 
        "Aborted"
      ]
    }
  }
}'''
        self.assertStringsEqual(pretty, expected)

    def tearDown(self):
        """
        Sends a kill message to the pp and waits for the process to terminate.

        """
        # Send a stop message to the prong process and wait until it joins
        self.dealer_sock.send(json.dumps(dict(type="call", device="malcolm", method="pleasestopnow")))
        self.fr.join()
        self.dw.join()
        self.dealer_sock.close()

if __name__ == '__main__':
    unittest.main(verbosity=2)
    
    
    