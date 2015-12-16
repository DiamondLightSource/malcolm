#!/bin/env dls-python
from pkg_resources import require
from malcolm.core.runnabledevice import DState
import time
require("mock")
require("pyzmq")
import unittest
import sys
import os
import cothread

import logging
logging.basicConfig()
# logging.basicConfig(level=logging.DEBUG)#, format='%(asctime)s
# %(name)-12s %(levelname)-8s %(message)s')
from mock import MagicMock, patch
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.devices import ProgScan
from malcolm.core import Attribute, PvAttribute


class DummyPVAttribute(PvAttribute):

    def make_pvs(self):
        self.pv = MagicMock()
        self.rbv = MagicMock()


class ProgScanTest(unittest.TestCase):

    @patch("malcolm.devices.progscan.PvAttribute", DummyPVAttribute)
    def setUp(self):
        self.s = ProgScan("S", "PRE")
        self.s.loop_run()
        self.in_params = dict(dwell=1000,
                              xStart=1, xStep=0.1, xNumPoints=10, xDwell=0)
        self.valid_params = {
            'dwell': 1000,
            'xNumPoints': 10, 'yStep': 0.0, 'zNumPoints': 0, 'xStart': 1.0,
            'xDwell': 0, 'yAlternate': False, 'yStart': 0.0,
            'runTimeout': 1, 'zAlternate': False, 'xOrder': 3, 'yOrder': 2,
            'resetTimeout': 1, 'zOrder': 1, 'xStep': 0.10000000000000001,
            'zDwell': 0, 'abortTimeout': 1, 'yDwell': 0, 'yNumPoints': 0,
            'zStart': 0.0, 'runTime': 20.0, 'configureTimeout': 1,
            'xAlternate': False, 'zStep': 0.0, 'startPoint': 1}
        self.send_params = {
            'dwell': 1000,
            'xNumPoints': 10, 'yStep': 0.0, 'zNumPoints': 0, 'xStart': 1.0,
            'xDwell': 0, 'yAlternate': False, 'yStart': 0.0,
            'zAlternate': False, 'xOrder': 3, 'yOrder': 2,
            'zOrder': 1, 'xStep': 0.10000000000000001,
            'zDwell': 0, 'yDwell': 0, 'yNumPoints': 0,
            'zStart': 0.0,
            'xAlternate': False, 'zStep': 0.0, 'startPoint': 1}

    def test_init(self):
        base = ['prefix', 'uptime']
        pvs = ['dwell', 'nPoints',
               'progState',
               'progress',
               'scanAbort',
               'scanStart',
               'startPoint',
               'xStart', 'xStep',
               'xNumPoints', 'xDwell', 'xAlternate', 'xOrder',
               'yStart', 'yStep',
               'yNumPoints', 'yDwell', 'yAlternate', 'yOrder',
               'zStart', 'zStep',
               'zNumPoints', 'zDwell', 'zAlternate', 'zOrder']
        self.assertEqual(self.s.attributes.keys(), base + pvs)
        self.assertEqual(self.s.prefix, "PRE")
        for attr in pvs:
            self.assertEqual(self.s.attributes[attr].value, None)
            self.assertEqual(self.s.attributes[attr].pv.call_args, None)

    def test_validate(self):
        actual = self.s.validate(**self.in_params)
        self.assertEqual(actual, self.valid_params)

    def check_set(self, attr, expected):
        self.assertEqual(self.s.attributes[attr].pv.caput.call_count, 1)
        call_args = self.s.attributes[attr].pv.caput.call_args
        val = call_args[0][0]
        self.assertEquals(
            val, expected, "{}: expected {} got {}".format(attr, expected, val))
        Attribute.update(self.s.attributes[attr], val)
        self.s.attributes[attr].pv.reset_mock()

    def test_configure(self):
        spawned = cothread.Spawn(self.s.configure, **self.in_params)
        # Yield to let configure run
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Idle)
        # Yield to let do_config and first do_configsta run
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Configuring)
        for attr in sorted(self.send_params):
            self.check_set(attr, self.send_params[attr])
        spawned.Wait(1)
        self.assertEqual(self.s.stateMachine.state, DState.Ready)

    def set_configured(self):
        # Set all the pvs to the right value
        for attr in sorted(self.send_params):
            self.s.attributes[attr]._value = self.send_params[attr]
        self.s.configure(block=False, **self.in_params)
        cothread.Yield()
        self.assertEqual(self.s.state, DState.Ready)

    def test_mismatch(self):
        self.set_configured()
        Attribute.update(self.s.attributes["xNumPoints"], 2)
        self.assertEqual(self.s.stateMachine.state, DState.Ready)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Idle)

    def test_run(self):
        self.set_configured()
        # Do a run
        spawned = cothread.Spawn(self.s.run)
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Running)
        self.check_set("scanStart", 1)
        self.assertEqual(self.s.scanStart, 1)
        Attribute.update(self.s.attributes["progState"], "Scanning")
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Running)
        Attribute.update(self.s.attributes["scanStart"], False)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Idle)
        spawned.Wait(1)
        self.assertEqual(self.s.stateMachine.state, DState.Idle)

    def test_abort(self):
        self.set_configured()
        spawned = cothread.Spawn(self.s.run)
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Running)
        self.check_set("scanStart", 1)
        self.assertEqual(self.s.scanStart, 1)
        Attribute.update(self.s.attributes["progState"], "Scanning")
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Running)
        aspawned = cothread.Spawn(self.s.abort)
        cothread.Yield()
        Attribute.update(self.s.attributes["progState"], "Idle")
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Aborted)
        spawned.Wait(1)
        aspawned.Wait(1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
