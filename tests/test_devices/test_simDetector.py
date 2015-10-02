#!/bin/env dls-python
from pkg_resources import require
from malcolm.core.runnableDevice import DState
require("mock")
require("pyzmq")
import unittest
import sys
import os
import cothread

import logging
# logging.basicConfig()
#logging.basicConfig(level=logging.DEBUG)
from mock import MagicMock, patch
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.devices.simDetector import SimDetector
from malcolm.core.pvattribute import PVAttribute
from malcolm.core import Attribute


class DummyPVAttribute(PVAttribute):

    def make_pvs(self):
        self.pv = MagicMock()
        self.rbv = MagicMock()


class SimDetectorTest(unittest.TestCase):

    @patch("malcolm.devices.simDetector.PVAttribute", DummyPVAttribute)
    def setUp(self):
        self.s = SimDetector("S", "PRE")
        self.s.loop_run()
        self.in_params = dict(numImages=2, exposure=0.1)
        self.valid_params = dict(
            numImages=2, exposure=0.1, period=0.1, runTime=0.2)
        self.send_params = {'imageMode': "Multiple", 'exposure':
                            0.1, 'arrayCounter': 0, 'arrayCallbacks': 1,
                            'period': 0.1, 'numImages': 2}

    def test_init(self):
        base = ['prefix', 'uptime', 'timeout']
        pvs = ['acquire', 'arrayCallbacks', 'arrayCounter', 'exposure',
               'imageMode', 'numImages', 'period']
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
        val, cb = call_args[0][0], call_args[1]["callback"]
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
        self.assertEqual(self.s.stateMachine.state, DState.Configuring)
        for attr in sorted(self.send_params):
            self.check_set(attr, self.send_params[attr])
        spawned.Wait(1)
        self.assertEqual(self.s.stateMachine.state, DState.Ready)

    def set_configured(self):
        # Set all the pvs to the right value
        for attr in sorted(self.send_params):
            self.s.attributes[attr]._value = self.send_params[attr]
        self.s.configure(timeout=1, **self.in_params)
        self.assertEqual(self.s.stateMachine.state, DState.Ready)

    def test_run(self):
        self.set_configured()
        # Do a run
        spawned = cothread.Spawn(self.s.run)
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Running)
        self.check_set("acquire", 1)
        self.assertEqual(self.s.acquire, 1)
        Attribute.update(self.s.attributes["acquire"], False)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Idle)
        spawned.Wait(1)
        self.assertEqual(self.s.stateMachine.state, DState.Idle)

    def test_abort(self):
        self.set_configured()
        spawned = cothread.Spawn(self.s.run, timeout=1)
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Running)
        self.check_set("acquire", 1)
        self.assertEqual(self.s.acquire, 1)
        aspawned = cothread.Spawn(self.s.abort, timeout=1)
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Aborting)
        self.check_set("acquire", 0)
        Attribute.update(self.s.attributes["acquire"], False)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Aborted)
        spawned.Wait(1)
        aspawned.Wait(1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
