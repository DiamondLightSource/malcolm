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
# logging.basicConfig()
# logging.basicConfig(level=logging.DEBUG)
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
        expected = ['Z:TTLIN1', 'Z:TTLIN2', 'Z:TTLIN3', 'Z:TTLIN4', 'Z:TTLIN5', 'Z:TTLIN6', 'Z:OUTENC1', 'Z:OUTENC2', 'Z:OUTENC3', 'Z:OUTENC4', 'Z:PCAP', 'Z:PCOMP1', 'Z:PCOMP2', 'Z:PCOMP3', 'Z:PCOMP4', 'Z:TTLOUT1', 'Z:TTLOUT2', 'Z:TTLOUT3', 'Z:TTLOUT4', 'Z:TTLOUT5', 'Z:TTLOUT6', 'Z:TTLOUT7', 'Z:TTLOUT8', 'Z:TTLOUT9', 'Z:TTLOUT10', 'Z:ADC1', 'Z:ADC2', 'Z:ADC3', 'Z:ADC4', 'Z:ADC5', 'Z:ADC6', 'Z:ADC7', 'Z:ADC8', 'Z:DIV1', 'Z:DIV2', 'Z:DIV3', 'Z:DIV4', 'Z:INENC1', 'Z:INENC2', 'Z:INENC3', 'Z:INENC4', 'Z:PGEN1', 'Z:PGEN2', 'Z:LVDSIN1', 'Z:LVDSIN2', 'Z:POSITIONS', 'Z:POSENC1', 'Z:POSENC2', 'Z:POSENC3', 'Z:POSENC4', 'Z:SEQ1', 'Z:SEQ2', 'Z:SEQ3', 'Z:SEQ4', 'Z:PULSE1', 'Z:PULSE2', 'Z:PULSE3', 'Z:PULSE4', 'Z:SRGATE1', 'Z:SRGATE2', 'Z:SRGATE3', 'Z:SRGATE4', 'Z:LUT1', 'Z:LUT2', 'Z:LUT3', 'Z:LUT4', 'Z:LUT5', 'Z:LUT6', 'Z:LUT7', 'Z:LUT8', 'Z:CALC1', 'Z:CALC2', 'Z:LVDSOUT1', 'Z:LVDSOUT2', 'Z:COUNTER1', 'Z:COUNTER2', 'Z:COUNTER3', 'Z:COUNTER4', 'Z:COUNTER5', 'Z:COUNTER6', 'Z:COUNTER7', 'Z:COUNTER8', 'Z:ADDER', 'Z:CLOCKS', 'Z:BITS', 'Z:QDEC1', 'Z:QDEC2', 'Z:QDEC3', 'Z:QDEC4']
        self.assertEqual(self.z.blocks, expected)
        adder = self.z._blocks["ADDER"]
        expected = ['uptime',
                    'RESULT',
                    'RESULT:UNITS',
                    'RESULT:SCALE',
                    'RESULT:OFFSET',
                    'RESULT:CAPTURE',
                    'MASK',
                    'OUTSCALE']
        self.assertEqual(adder.attributes.keys(), expected)

    def test_poll(self):
        pulse1 = self.z._blocks["PULSE1"]
        self.assertEqual(pulse1.WIDTH, None)
        m = MagicMock()
        pulse1.add_listener(m, "attributes.WIDTH:UNITS")
        cothread.Sleep(0.2)
        self.assertEqual(m.call_args[0][0], pulse1.attributes["WIDTH:UNITS"])
        self.assertEqual(m.call_args[0][1]["value"], "s")

if __name__ == '__main__':
    unittest.main(verbosity=2)
