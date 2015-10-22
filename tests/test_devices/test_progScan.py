#!/bin/env dls-python
from pkg_resources import require
from malcolm.core.runnableDevice import DState
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

    @patch("malcolm.devices.progScan.PvAttribute", DummyPVAttribute)
    def setUp(self):
        self.s = ProgScan("S", "PRE")
        self.s.loop_run()
        self.in_params = dict(
            m1Start=1, m1Step=0.1, m1NumPoints=10, m1Dwell=1000)
        self.valid_params = {
            'm1NumPoints': 10, 'm2Step': 0.0, 'm3NumPoints': 0, 'm1Start': 1.0,
            'm1Dwell': 1000, 'm2Alternate': False, 'm2Start': 0.0,
            'runTimeout': 1, 'm3Alternate': False, 'm1Order': 3, 'm2Order': 2,
            'resetTimeout': 1, 'm3Order': 1, 'm1Step': 0.10000000000000001,
            'm3Dwell': 0, 'abortTimeout': 1, 'm2Dwell': 0, 'm2NumPoints': 0,
            'm3Start': 0.0, 'runTime': 20.0, 'configureTimeout': 1,
            'm1Alternate': False, 'm3Step': 0.0}
        self.send_params = {
            'm1NumPoints': 10, 'm2Step': 0.0, 'm3NumPoints': 0, 'm1Start': 1.0,
            'm1Dwell': 1000, 'm2Alternate': False, 'm2Start': 0.0,
            'm3Alternate': False, 'm1Order': 3, 'm2Order': 2,
            'm3Order': 1, 'm1Step': 0.10000000000000001,
            'm3Dwell': 0, 'm2Dwell': 0, 'm2NumPoints': 0,
            'm3Start': 0.0, 
            'm1Alternate': False, 'm3Step': 0.0}

    def test_init(self):
        base = ['prefix', 'uptime', 'block']
        pvs = ['progState', 'scanAbort', 'scanStart', 'm1Start', 'm1Step',
               'm1NumPoints', 'm1Dwell', 'm1Alternate', 'm1Order',
               'm1PointsDone', 'm1ScansDone', 'm2Start', 'm2Step',
               'm2NumPoints', 'm2Dwell', 'm2Alternate', 'm2Order',
               'm2PointsDone', 'm2ScansDone', 'm3Start', 'm3Step',
               'm3NumPoints', 'm3Dwell', 'm3Alternate', 'm3Order',
               'm3PointsDone', 'm3ScansDone']
        self.assertEqual(self.s.attributes.keys(), base + pvs)
        self.assertEqual(self.s.prefix, "PRE")
        for attr in pvs:
            self.assertEqual(self.s.attributes[attr].value, None)
            self.assertEqual(self.s.attributes[attr].pv.call_args, None)

    def test_validate(self):
        actual = self.s.validate(**self.in_params)
        self.assertEqual(actual, self.valid_params)

    def test_mismatch(self):
        self.set_configured()
        Attribute.update(self.s.attributes["m1NumPoints"], 2)
        self.assertEqual(self.s.stateMachine.state, DState.Ready)
        self.assertEqual(self.s._sconfig.state, self.s._sconfig.SeqState.Done)
        cothread.Yield()
        self.assertEqual(self.s._sconfig.state, self.s._sconfig.SeqState.Idle)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Fault)

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
        for seq_item in self.s._sconfig.seq_items.values():
            seq_item.check_params = self.send_params.copy()
        for attr in sorted(self.send_params):
            self.s.attributes[attr]._value = self.send_params[attr]
        self.s.stateMachine.state = DState.Ready
        self.s._sconfig.stateMachine.state = self.s._sconfig.SeqState.Done
        Attribute.update(self.s.attributes["progState"], "Idle")

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
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Aborted)
        spawned.Wait(1)
        aspawned.Wait(1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
