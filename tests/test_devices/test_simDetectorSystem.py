#!/bin/env dls-python
from pkg_resources import require
from collections import OrderedDict
require("mock")
require("pyzmq")
import unittest
import sys
import os
import random
os.environ["EPICS_CA_SERVER_PORT"] = "6064"

import cothread
import time
import subprocess

import logging
#logging.basicConfig()
#logging.basicConfig(level=logging.DEBUG)
from mock import MagicMock, patch
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.devices.simDetector import SimDetector
from malcolm.core.runnableDevice import DState


class SimDetectorTest(unittest.TestCase):

    def setUp(self):
        # Start the GDA SWMR demo
        ioc = "/dls_sw/work/R3.14.12.3/support/mapping/iocs/TS-EA-IOC-02/bin/linux-x86_64/stTS-EA-IOC-02.sh"
        #self.ioc = subprocess.Popen([ioc, "512", "512"], stdin=subprocess.PIPE)
        #cothread.Sleep(5)
        from socket import gethostname
        hostname = gethostname().split(".")[0]
        pre = "{}-AD-SIM-01:CAM:".format(hostname)
        self.s = SimDetector("S", pre)
        self.s.loop_run()
        self.in_params = dict(numImages=5, exposure=0.1)
        self.runtime = self.in_params["numImages"] * self.in_params["exposure"]
        self.send_params = {'imageMode': 'Multiple', 'exposure':
                            0.1, 'arrayCounter': 0, 'period': 0.1, 'numImages': 5}

    def test_100_sequences(self):
        for i in range(100):
            self.test_sequence()
            cothread.Sleep(random.random())

    def test_sequence(self):
        start = time.time()
        self.s.configure(**self.in_params)
        end = time.time()
        self.assertAlmostEqual(end - start, 0.05, delta=0.05)
        for attr, val in self.send_params.items():
            actual = self.s.attributes[attr].value
            self.assertEqual(actual, val, "Attr {} = {} not {}".format(attr, actual, val))
        self.assertEqual(self.s.stateMachine.state, DState.Ready)
        self.assertEqual(self.s.arrayCounter, 0)
        # Do a run
        start = time.time()
        self.s.run()
        end = time.time()
        self.assertAlmostEqual(end - start, self.runtime, delta=0.05)
        self.assertEqual(self.s.stateMachine.state, DState.Idle)
        # Allow numImages to update
        cothread.Yield()
        self.assertEqual(self.s.arrayCounter, self.in_params["numImages"])

    def tearDown(self):
        #self.ioc.stdin.close()
        #self.ioc.wait()
        pass

if __name__ == '__main__':
    unittest.main(verbosity=2)
