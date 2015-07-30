#!/bin/env dls-python
from pkg_resources import require
from malcolm.devices.dummyDet import DummyDet
from test.zmqComms.support import make_sock
require("mock")
require("pyzmq")
require("cothread")
import unittest
import sys
import os
import multiprocessing
import json
import zmq
import time

#import logging
#logging.basicConfig(level=logging.DEBUG)#,
# format="%(asctime)s;%(levelname)s;%(message)s")
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqComms.functionCaller import FunctionCaller
from malcolm.zmqComms.functionRouter import FunctionRouter
from malcolm.zmqComms.deviceWrapper import DeviceWrapper
import difflib

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
        for x in sys.modules.keys():
            if x.startswith("cothread"):
                del sys.modules[x]        
        self.context = zmq.Context()
        be_addr = "ipc://frbe.ipc"
        fe_addr = "ipc://frfe.ipc"
        self.caller_sock = make_sock(
            self.context, zmq.DEALER, fe_addr, bind=False)
        self.fr = FunctionRouter(fe_addr=fe_addr, be_addr=be_addr, timeout=1)
        self.fr.start()
        self.dw = DeviceWrapper("det", DummyDet, be_addr, timeout=1)
        self.dw.start()
        self.fc = FunctionCaller("det", fe_addr=fe_addr, timeout=1)
        self.fc.run(block=False)

    def test_configure_run(self):
        time.sleep(0.2)
        now = time.time()
        self.fc.call("configure_run", nframes=5, exposure=0.1)
        then = time.time()
        self.assertAlmostEqual(then - now, 0.5, delta=0.08)
        now = time.time()
        self.fc.call("configure_run", nframes=5, exposure=0.1)
        then = time.time()
        self.assertAlmostEqual(then - now, 0.5, delta=0.08)

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
        self.caller_sock.send(
            json.dumps(dict(id=0, type="call", method="malcolm.pleasestopnow")))
        self.fr.join()
        self.dw.join()
        self.caller_sock.close()
        self.fc.wait_loops()

if __name__ == '__main__':
    unittest.main(verbosity=2)
