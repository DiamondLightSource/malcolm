#!/bin/env dls-python
from pkg_resources import require
from malcolm.core.runnabledevice import DState
import time
import difflib
require("mock")
require("pyzmq")
import unittest
import numpy
import sys
import re
import os
import cothread
import numpy as np
from xml.dom import minidom
from xml.etree import ElementTree as ET

import logging
logging.basicConfig()
#logging.basicConfig(level=logging.DEBUG)
from mock import MagicMock, patch
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.devices import PositionPlugin
from malcolm.core import Attribute, PvAttribute, VDouble, VInt


class DummyPVAttribute(PvAttribute):

    def make_pvs(self):
        self.pv = MagicMock()
        self.rbv = MagicMock()


class PositionPluginTest(unittest.TestCase):

    @patch("malcolm.devices.positionplugin.PvAttribute", DummyPVAttribute)
    def setUp(self):
        self.s = PositionPlugin("S", "PRE")
        self.s.loop_run()
        self.positions = [
            ("y", VDouble, np.repeat(np.arange(6, 9), 5) * 0.1, 'mm'),
            ("x", VDouble, np.tile(np.arange(5), 3) * 0.1, 'mm'),
            ("y_index", VInt, np.repeat(np.arange(3, dtype=numpy.int32), 5), ''),
            ("x_index", VInt, np.tile(np.arange(5, dtype=numpy.int32), 3), '')
        ]
        self.in_params = dict(positions=self.positions)
        self.valid_params = dict(
            positions=self.positions, idStart=1,
            resetTimeout=1, runTime=None, runTimeout=1,
            abortTimeout=1, configureTimeout=1, arrayPort=None)
        self.send_params = dict(
            enableCallbacks=1,
            idStart=1, xml="something")
        self.maxDiff = 3000

    def test_init(self):
        base = ['prefix', 'uptime']
        pvs = ['arrayPort','delete', 'enableCallbacks', 'idStart', 'portName','positions',
               'running', 'uniqueId', 'xml']
        self.assertEqual(self.s.attributes.keys(), base + pvs)
        self.assertEqual(self.s.prefix, "PRE")
        for attr in pvs:
            self.assertEqual(self.s.attributes[attr].value, None)
            if hasattr(self.s.attributes[attr], "pv"):
                self.assertEqual(self.s.attributes[attr].pv.call_args, None)

    def test_validate(self):
        actual = self.s.validate(**self.in_params)
        self.assertEqual(actual, self.valid_params)

    def set_configured(self):
        # Set all the pvs to the right value
        for attr in sorted(self.send_params):
            self.s.attributes[attr]._value = self.send_params[attr]
        self.s.configure(block=False, **self.in_params)
        Attribute.update(self.s.attributes["delete"], True)
        cothread.Yield()
        Attribute.update(self.s.attributes["xml"], self.s._sconfig.seq_items[1].seq_params["xml"])
        cothread.Yield()
        self.assertEqual(self.s.state, DState.Ready)

    def check_set(self, attr, expected):
        self.assertEqual(self.s.attributes[attr].pv.caput.call_count, 1, attr)
        call_args = self.s.attributes[attr].pv.caput.call_args
        val = call_args[0][0]
        if attr != "xml":
            self.assertEquals(
                val, expected, "{}: expected {} got {}".format(attr, expected, val))
        Attribute.update(self.s.attributes[attr], val)
        self.s.attributes[attr].pv.reset_mock()

    def test_configure(self):
        spawned = cothread.Spawn(self.s.configure, **self.in_params)
        # Yield to let configure run
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Idle)
        # Yield to let do_config run
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Configuring)
        self.assertEqual(self.s.stateMachine.message, "Deleting old positions")
        self.check_set("delete", True)
        # Yield to let this post and then once to let the sm process
        cothread.Yield()
        for attr in sorted(self.send_params):
            self.check_set(attr, self.send_params[attr])
        spawned.Wait(1)
        expected = """<?xml version="1.0" ?>
<pos_layout>
  <dimensions>
    <dimension name="y"/>
    <dimension name="x"/>
    <dimension name="y_index"/>
    <dimension name="x_index"/>
    <dimension name="FilePluginClose"/>
  </dimensions>
  <positions>
    <position FilePluginClose="0" x="0.0" x_index="0" y="0.6" y_index="0"/>
    <position FilePluginClose="0" x="0.1" x_index="1" y="0.6" y_index="0"/>
    <position FilePluginClose="0" x="0.2" x_index="2" y="0.6" y_index="0"/>
    <position FilePluginClose="0" x="0.3" x_index="3" y="0.6" y_index="0"/>
    <position FilePluginClose="0" x="0.4" x_index="4" y="0.6" y_index="0"/>
    <position FilePluginClose="0" x="0.0" x_index="0" y="0.7" y_index="1"/>
    <position FilePluginClose="0" x="0.1" x_index="1" y="0.7" y_index="1"/>
    <position FilePluginClose="0" x="0.2" x_index="2" y="0.7" y_index="1"/>
    <position FilePluginClose="0" x="0.3" x_index="3" y="0.7" y_index="1"/>
    <position FilePluginClose="0" x="0.4" x_index="4" y="0.7" y_index="1"/>
    <position FilePluginClose="0" x="0.0" x_index="0" y="0.8" y_index="2"/>
    <position FilePluginClose="0" x="0.1" x_index="1" y="0.8" y_index="2"/>
    <position FilePluginClose="0" x="0.2" x_index="2" y="0.8" y_index="2"/>
    <position FilePluginClose="0" x="0.3" x_index="3" y="0.8" y_index="2"/>
    <position FilePluginClose="1" x="0.4" x_index="4" y="0.8" y_index="2"/>
  </positions>
</pos_layout>
"""
        self.assert_xml(self.s.xml, expected)
        self.assertEqual(self.s.stateMachine.state, DState.Ready)

    def assert_xml(self, xml, expected):
        pretty = minidom.parseString(xml).toprettyxml(indent="  ")
        if expected != pretty:
            print
            print pretty
            message = ''.join(difflib.unified_diff(
                expected.splitlines(True), pretty.splitlines(True)))
            self.fail("Output doesn't match expected: %s\n" % message)

    def test_run(self):
        self.set_configured()
        # Do a run
        spawned = cothread.Spawn(self.s.run)
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Running)
        self.check_set("running", 1)
        self.assertEqual(self.s.running, 1)
        Attribute.update(self.s.attributes["running"], False)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Idle)
        spawned.Wait(1)
        self.assertEqual(self.s.stateMachine.state, DState.Idle)

    def test_mismatch(self):
        self.set_configured()
        Attribute.update(self.s.attributes["enableCallbacks"], False)
        self.assertEqual(self.s.stateMachine.state, DState.Ready)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Idle)

    def test_abort(self):
        self.set_configured()
        spawned = cothread.Spawn(self.s.run)
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Running)
        self.check_set("running", 1)
        self.assertEqual(self.s.running, 1)
        aspawned = cothread.Spawn(self.s.abort)
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Aborting)
        self.check_set("running", 0)
        Attribute.update(self.s.attributes["running"], False)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Aborted)
        spawned.Wait(1)
        aspawned.Wait(1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
