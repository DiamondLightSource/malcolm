#!/bin/env dls-python
from pkg_resources import require
from collections import OrderedDict
from malcolm.devices.zebra2.zebra2 import Zebra2
require("mock")
require("pyzmq")
import unittest
import sys
import os
import random

import cothread
import time
import subprocess
import signal

import logging
#logging.basicConfig()
logging.basicConfig(level=logging.DEBUG)
from mock import MagicMock, patch
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.devices.simdetector import SimDetector
from malcolm.core.runnabledevice import DState


class Zebra2SystemTest(unittest.TestCase):

    def setUp(self):
        # simserver = "/home/tmc43/common/zebra2-server/simserver"
        # self.server = subprocess.Popen(simserver, stdin=subprocess.PIPE)
        # cothread.Sleep(2)
        self.z = Zebra2("Z", "localhost", 8888)
        self.z.loop_run()

    def test_blocks(self):
        expected = ['Z:TTLIN0', 'Z:TTLIN1', 'Z:TTLIN2', 'Z:TTLIN3', 'Z:TTLIN4', 'Z:TTLIN5', 'Z:OUTENC0', 'Z:OUTENC1', 'Z:OUTENC2', 'Z:OUTENC3', 'Z:CALC0', 'Z:CALC1', 'Z:SRGATE0', 'Z:SRGATE1', 'Z:SRGATE2', 'Z:SRGATE3', 'Z:PCOMP0', 'Z:PCOMP1', 'Z:PCOMP2', 'Z:PCOMP3', 'Z:LUT0', 'Z:LUT1', 'Z:LUT2', 'Z:LUT3', 'Z:LUT4', 'Z:LUT5', 'Z:LUT6', 'Z:LUT7', 'Z:TTLOUT0', 'Z:TTLOUT1', 'Z:TTLOUT2', 'Z:TTLOUT3', 'Z:TTLOUT4', 'Z:TTLOUT5', 'Z:TTLOUT6', 'Z:TTLOUT7', 'Z:TTLOUT8', 'Z:TTLOUT9', 'Z:LVDSOUT0', 'Z:LVDSOUT1', 'Z:ADC0', 'Z:ADC1', 'Z:ADC2', 'Z:ADC3', 'Z:ADC4', 'Z:ADC5', 'Z:ADC6', 'Z:ADC7', 'Z:DIV0', 'Z:DIV1', 'Z:DIV2', 'Z:DIV3', 'Z:INENC0', 'Z:INENC1', 'Z:INENC2', 'Z:INENC3', 'Z:COUNTER0', 'Z:COUNTER1', 'Z:COUNTER2', 'Z:COUNTER3', 'Z:COUNTER4', 'Z:COUNTER5', 'Z:COUNTER6', 'Z:COUNTER7', 'Z:ADDER0', 'Z:PCAP0', 'Z:POSENC0', 'Z:POSENC1', 'Z:POSENC2', 'Z:POSENC3', 'Z:LVDSIN0', 'Z:LVDSIN1', 'Z:PGEN0', 'Z:PGEN1', 'Z:QDEC0', 'Z:QDEC1', 'Z:QDEC2', 'Z:QDEC3', 'Z:SEQ0', 'Z:SEQ1', 'Z:SEQ2', 'Z:SEQ3', 'Z:PULSE0', 'Z:PULSE1', 'Z:PULSE2', 'Z:PULSE3']
        self.assertEqual(self.z.blocks, expected)
        adder = self.z._blocks["ADDER0"]
        self.assertEqual(adder.attributes.keys(), ['uptime', 'RESULT', 'MASK', 'OUTSCALE'])

    def test_poll(self):
        pulse0 = self.z._blocks["PULSE0"]
        self.assertEqual(pulse0.WIDTH, None)
        m = MagicMock()
        pulse0.add_listener(m, "attributes.WIDTH")
        cothread.Sleep(0.2)
        self.assertEqual(m.call_args[0][0], pulse0.attributes["WIDTH"])
        self.assertEqual(m.call_args[0][1]["value"], 1431660000.0)

if __name__ == '__main__':
    unittest.main(verbosity=2)
