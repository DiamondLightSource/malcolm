#!/bin/env dls-python
from pkg_resources import require
from collections import OrderedDict
import numpy
from malcolm.core.vtype import VDouble
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
logging.basicConfig()
#logging.basicConfig(level=logging.INFO)
#logging.basicConfig(level=logging.DEBUG)
#logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')

from mock import MagicMock, patch
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.devices import SimDetector
from malcolm.core.runnabledevice import DState
from malcolm.devices.positionplugin import PositionPlugin
from malcolm.devices.hdf5writer import Hdf5Writer
from malcolm.personalities.simdetectorpersonality import SimDetectorPersonality


class SimDetectorPersonalityTest(unittest.TestCase):

    def setUp(self):
        # Start the GDA SWMR demo
        #ioc = "/dls_sw/work/R3.14.12.3/support/mapping/iocs/TS-EA-IOC-02/bin/linux-x86_64/stTS-EA-IOC-02.sh"
        #self.ioc = subprocess.Popen([ioc, "512", "512"], stdin=subprocess.PIPE)
        #cothread.Sleep(5)
        from socket import gethostname
        hostname = gethostname().split(".")[0]
        pre = "{}-AD-SIM-01:".format(hostname)
        self.s = SimDetector("S", pre + "CAM:")
        self.s.loop_run()
        self.p = PositionPlugin("P", pre + "POS:")
        self.p.loop_run()
        self.h = Hdf5Writer("H", pre + "HDF5:")
        self.h.loop_run()
        # Wait for things to get their portName
        cothread.Sleep(0.5)
        self.assertNotEqual(self.s.portName, None)
        self.assertNotEqual(self.p.portName, None)
        self.assertNotEqual(self.h.portName, None)
        self.sp = SimDetectorPersonality("SP", self.s, self.p, self.h)
        self.sp.loop_run()
        self.positions = [
            ("y", VDouble, numpy.repeat(numpy.arange(6, 9), 5) * 0.1, 'mm'),
            ("x", VDouble, numpy.tile(numpy.arange(5), 3) * 0.1, 'mm'),
        ]
        self.in_params = dict(exposure=0.1, positions=self.positions, 
                              hdf5File="/tmp/demo2.hdf5")
        self.numImages = len(self.positions[0][2])
        self.runtime = self.numImages * 0.1

    def test_100_sequences(self):
        for i in range(100):
            print i
            self.do_sequence()
            cothread.Sleep(random.random())

    def do_sequence(self):
        start = time.time()
        self.sp.configure(**self.in_params)
        end = time.time()
        self.assertAlmostEqual(end - start, 0.0, delta=0.2)
        self.assertEqual(self.sp.state, DState.Ready)
        self.assertEqual(self.s.state, DState.Ready)
        self.assertEqual(self.p.state, DState.Ready)
        self.assertEqual(self.h.state, DState.Ready)
        self.assertEqual(self.s.arrayCounter, 0)
        # Do a run
        start = time.time()
        self.sp.run()
        end = time.time()
        self.assertAlmostEqual(end - start, self.runtime, delta=0.05)
        self.assertEqual(self.s.stateMachine.state, DState.Idle)
        # Allow numImages to update
        cothread.Sleep(0.05)
        self.assertEqual(self.s.arrayCounter, self.numImages)

    def tearDown(self):
        #self.ioc.stdin.close()
        #self.ioc.wait()
        pass
    

if __name__ == '__main__':
    unittest.main(verbosity=2)
