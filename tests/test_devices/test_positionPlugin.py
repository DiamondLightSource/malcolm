#!/bin/env dls-python
from pkg_resources import require
from malcolm.core.runnableDevice import DState
import time
import difflib
require("mock")
require("pyzmq")
import unittest
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
from malcolm.core import Attribute, PvAttribute, VDouble


class DummyPVAttribute(PvAttribute):

    def make_pvs(self):
        self.pv = MagicMock()
        self.rbv = MagicMock()


class PositionPluginTest(unittest.TestCase):

    @patch("malcolm.devices.positionPlugin.PvAttribute", DummyPVAttribute)
    def setUp(self):
        self.s = PositionPlugin("S", "PRE")
        self.s.loop_run()
        self.positions = [
            ("y", VDouble, np.repeat(np.arange(6, 9), 5) * 0.1),
            ("x", VDouble, np.tile(np.arange(5), 3) * 0.1),
        ]
        self.in_params = dict(positions=self.positions)
        self.valid_params = dict(
            positions=self.positions, idStart=1,
            resetTimeout=1, runTime=None, runTimeout=1,
            abortTimeout=1, configureTimeout=1)
        self.send_params = dict(
            enableCallbacks=1,
            idStart=1, xml="something")
        self.maxDiff = 1000

    def test_init(self):
        base = ['prefix', 'uptime', 'block']
        pvs = ['delete', 'dimensions', 'enableCallbacks', 'idStart', 'positions',
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
        # Yield to let do_config and first do_configsta run
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Configuring)
        # Yield to let Config state machine process
        cothread.Yield()
        self.assertEqual(self.s._pconfig.state, self.s._pconfig.PvState.SeqSet1)
        # Yield to let main statemachine process
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Deleting old positions")
        self.check_set("delete", True)
        # Yield to let this post and then once to let the sm process
        cothread.Yield()
        self.assertEqual(self.s._pconfig.state, self.s._pconfig.PvState.SeqSet2)
        for attr in sorted(self.send_params):
            self.check_set(attr, self.send_params[attr])
        spawned.Wait(1)
        expected = """<?xml version="1.0" ?>
<pos_layout>
  <dimensions>
    <dimension name="y"/>
    <dimension name="y_index"/>
    <dimension name="x"/>
    <dimension name="x_index"/>
    <dimension name="filePluginClose"/>
  </dimensions>
  <positions>
    <position filePluginClose="0" x="0.0" x_index="0" y="0.6" y_index="0"/>
    <position filePluginClose="0" x="0.1" x_index="1" y="0.6" y_index="0"/>
    <position filePluginClose="0" x="0.2" x_index="2" y="0.6" y_index="0"/>
    <position filePluginClose="0" x="0.3" x_index="3" y="0.6" y_index="0"/>
    <position filePluginClose="0" x="0.4" x_index="4" y="0.6" y_index="0"/>
    <position filePluginClose="0" x="0.0" x_index="0" y="0.7" y_index="1"/>
    <position filePluginClose="0" x="0.1" x_index="1" y="0.7" y_index="1"/>
    <position filePluginClose="0" x="0.2" x_index="2" y="0.7" y_index="1"/>
    <position filePluginClose="0" x="0.3" x_index="3" y="0.7" y_index="1"/>
    <position filePluginClose="0" x="0.4" x_index="4" y="0.7" y_index="1"/>
    <position filePluginClose="0" x="0.0" x_index="0" y="0.8" y_index="2"/>
    <position filePluginClose="0" x="0.1" x_index="1" y="0.8" y_index="2"/>
    <position filePluginClose="0" x="0.2" x_index="2" y="0.8" y_index="2"/>
    <position filePluginClose="0" x="0.3" x_index="3" y="0.8" y_index="2"/>
    <position filePluginClose="1" x="0.4" x_index="4" y="0.8" y_index="2"/>
  </positions>
</pos_layout>
"""
        self.assert_xml(self.s.xml, expected)
        self.assertEqual(self.s._pconfig.state, self.s._pconfig.PvState.Ready)
        self.assertEqual(self.s.stateMachine.state, DState.Ready)
        self.assertTrue(all(self.s.dimensions == [3, 5]))

    def assert_xml(self, xml, expected):
        pretty = minidom.parseString(xml).toprettyxml(indent="  ")
        if expected != pretty:
            print
            print pretty
            message = ''.join(difflib.unified_diff(
                expected.splitlines(True), pretty.splitlines(True)))
            self.fail("Output doesn't match expected: %s\n" % message)

    def set_configured(self):
        # Set all the pvs to the right value
        self.s._pconfig.config_params = self.send_params.copy()
        for attr in sorted(self.send_params):
            self.s.attributes[attr]._value = self.send_params[attr]
        self.s.stateMachine.state = DState.Ready
        self.s._pconfig.stateMachine.state = self.s._pconfig.PvState.Ready

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
        self.assertEqual(self.s._pconfig.state, self.s._pconfig.PvState.Ready)
        cothread.Yield()
        self.assertEqual(self.s._pconfig.state, self.s._pconfig.PvState.Idle)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Fault)

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

    def test_non_square(self):
        xs = []
        ys = []
        v = 2.0  # velocity in units/s
        period = 1.0  # time between points in s
        revs = 3  # number of revolutions in spiral
        r = 2.0  # radius increase for one turn
        # start from the outside and work inwards as it gives
        # us a better speed approximation
        theta = revs * 2 * np.pi
        while theta > 0:
            xs.append(r * theta * np.cos(theta) / 2 / np.pi)
            ys.append(r * theta * np.sin(theta) / 2 / np.pi)
            # This is the speed in radians/s
            w = v * 2 * np.pi / (theta * r)
            # Increments by next v
            theta -= w * period
        xs = np.array(xs)
        ys = np.array(ys)
        # These are the points zipped together
        pts = np.array((xs, ys)).T
        # Diff between successive points
        d = np.diff(pts, axis=0)
        # Euclidean difference between points
        segdists = np.sqrt((d ** 2).sum(axis=1))
        #from pkg_resources import require
        # require("matplotlib")
        #import pylab
        #pylab.plot(xs, ys, ".")
        # pylab.show()
        # pylab.plot(segdists)
        # pylab.show()
        # make a table of positions from it
        positions = [
            ("x", VDouble, xs),
            ("y", VDouble, ys),
        ]
        config_params = dict(positions=positions)
        self.s._make_xml(config_params)
        self.assertEqual(self.s.dimensions, len(xs))
        expected = """<?xml version="1.0" ?>
<pos_layout>
  <dimensions>
    <dimension name="x"/>
    <dimension name="y"/>
    <dimension name="filePluginClose"/>
  </dimensions>
  <positions>
    <position filePluginClose="0" x="6.0" y="-4.40872847693e-15"/>
    <position filePluginClose="0" x="5.56947863188" y="-1.92845174521"/>
    <position filePluginClose="0" x="4.525500695" y="-3.6050366395"/>
    <position filePluginClose="0" x="2.97859060897" y="-4.83149156225"/>
    <position filePluginClose="0" x="1.10582592989" y="-5.45268765837"/>
    <position filePluginClose="0" x="-0.864850809899" y="-5.38019888777"/>
    <position filePluginClose="0" x="-2.67917049232" y="-4.61052723651"/>
    <position filePluginClose="0" x="-4.08827862096" y="-3.23448718721"/>
    <position filePluginClose="0" x="-4.88460514111" y="-1.43465532069"/>
    <position filePluginClose="0" x="-4.93738839002" y="0.531222219213"/>
    <position filePluginClose="0" x="-4.22223426636" y="2.36134163529"/>
    <position filePluginClose="0" x="-2.8384907795" y="3.7536974523"/>
    <position filePluginClose="0" x="-1.00848655147" y="4.4581710746"/>
    <position filePluginClose="0" x="0.945855846735" y="4.32941686101"/>
    <position filePluginClose="0" x="2.65060608551" y="3.3704864242"/>
    <position filePluginClose="0" x="3.74872171667" y="1.75550008515"/>
    <position filePluginClose="0" x="3.98154214242" y="-0.180084848187"/>
    <position filePluginClose="0" x="3.26763577747" y="-1.98995948875"/>
    <position filePluginClose="0" x="1.75778060225" y="-3.20967887567"/>
    <position filePluginClose="0" x="-0.158493951645" y="-3.48191539698"/>
    <position filePluginClose="0" x="-1.91717711416" y="-2.68949947839"/>
    <position filePluginClose="0" x="-2.92583905984" y="-1.05468159941"/>
    <position filePluginClose="0" x="-2.77815591363" y="0.85052730623"/>
    <position filePluginClose="0" x="-1.48415333532" y="2.23910853466"/>
    <position filePluginClose="0" x="0.388215253431" y="2.41837337579"/>
    <position filePluginClose="0" x="1.81306792059" y="1.22733126801"/>
    <position filePluginClose="0" x="1.80321424653" y="-0.594376954658"/>
    <position filePluginClose="0" x="0.309071746704" y="-1.53249072941"/>
    <position filePluginClose="0" x="-1.01982033588" y="-0.544614506768"/>
    <position filePluginClose="1" x="-0.196997591065" y="0.572540665964"/>
  </positions>
</pos_layout>
"""
        self.assert_xml(config_params["xml"], expected)

if __name__ == '__main__':
    unittest.main(verbosity=2)
