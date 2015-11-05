#!/bin/env dls-python
from pkg_resources import require
from malcolm.core.runnabledevice import DState
import time
from xml.dom import minidom
import difflib
require("mock")
require("pyzmq")
import unittest
import sys
import os
import cothread

import logging
logging.basicConfig()
#logging.basicConfig(level=logging.DEBUG)
from mock import MagicMock, patch
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.devices import Hdf5Writer
from malcolm.core import Attribute, PvAttribute


class DummyPVAttribute(PvAttribute):

    def make_pvs(self):
        self.pv = MagicMock()
        self.rbv = MagicMock()


class HdfWriterTest(unittest.TestCase):

    @patch("malcolm.devices.hdf5writer.PvAttribute", DummyPVAttribute)
    def setUp(self):
        self.s = Hdf5Writer("S", "PRE")
        self.s.loop_run()
        self.in_params = dict(filePath="/tmp", fileName="demo.hdf5",
                              dimNames=["x", "y"], dimSizes=[5, 3])
        self.valid_params = dict(
            filePath="/tmp/", fileName="demo.hdf5",
            dimNames=["x", "y"], dimSizes=[5, 3], dimUnits=["mm", "mm"],
            resetTimeout=1, runTime=None, runTimeout=1,
            abortTimeout=1, configureTimeout=1, arrayPort=None)
        self.send_params = {
            'ndAttributeChunk': True, 'swmrMode': True, 'extraDimSizeX': 3,
            'extraDimSizeY': 1, 'filePath': '/tmp/', 'posNameDimN': 'x_index',
            'fileWriteMode': 'Stream', 'numExtraDims': 1,
            'extraDimSizeN': 5, 'enableCallbacks': True,
            'dimAttDatasets': True, 'lazyOpen': True,
            'fileTemplate': '%s%s', 'fileName': 'demo.hdf5',
            'posNameDimX': 'y_index', 'posNameDimY': '', 'xml': 'something',
            "numCapture": 0
        }

    def test_init(self):
        base = ['prefix', 'readbacks', 'uptime']
        pvs = ['arrayPort', 'capture', 'dimAttDatasets',
               'dimNames', 'dimSizes', 'dimUnits', 
               'enableCallbacks', 'extraDimSizeN',
               'extraDimSizeX', 'extraDimSizeY', 'fileName', 'filePath',
               'fileTemplate', 'fileWriteMode', 'lazyOpen', 'ndAttributeChunk',
               'numCapture', 'numExtraDims', 'portName', 'posNameDimN', 'posNameDimX',
               'posNameDimY', 'positionMode', 'swmrMode', 'uniqueId',
               'writeMessage', 'writeStatus', 'xml']
        self.assertEqual(self.s.attributes.keys(), base + pvs)
        self.assertEqual(self.s.prefix, "PRE")
        for attr in pvs:
            self.assertEqual(self.s.attributes[attr].value, None)
            if hasattr(self.s.attributes[attr], "pv"):
                self.assertEqual(self.s.attributes[attr].pv.call_args, None)

    def test_validate(self):
        actual = self.s.validate(**self.in_params)
        for param in set(list(self.valid_params) + list(actual)):
            equal = actual[param] == self.valid_params[param]
            if hasattr(equal, "all"):
                equal = equal.all()
            self.assertTrue(equal, param)

    def check_set(self, attr, expected):
        self.assertEqual(self.s.attributes[attr].pv.caput.call_count, 1, attr)
        call_args = self.s.attributes[attr].pv.caput.call_args
        val = call_args[0][0]
        if attr != "xml":
            self.assertEquals(
                val, expected, "{}: expected {} got {}".format(attr, expected, val))
        Attribute.update(self.s.attributes[attr], val)
        self.s.attributes[attr].pv.reset_mock()

    def assert_xml(self, xml, expected):
        pretty = minidom.parseString(xml).toprettyxml(indent="  ")
        if expected != pretty:
            print
            print pretty
            message = ''.join(difflib.unified_diff(
                expected.splitlines(True), pretty.splitlines(True)))
            self.fail("Output doesn't match expected: %s\n" % message)

    def test_configure(self):
        spawned = cothread.Spawn(self.s.configure, **self.in_params)
        # Yield to let configure run
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Idle)
        # Yield to let do_config and _sconfig
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Configuring)
        self.check_set("positionMode", True)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Configuring parameters")
        for attr in sorted(self.send_params):
            self.check_set(attr, self.send_params[attr])
        spawned.Wait(1)
        expected = """<?xml version="1.0" ?>
<hdf5_layout>
  <group name="entry">
    <attribute name="NX_class" source="constant" type="string" value="NXentry"/>
    <group name="data">
      <attribute name="signal" source="constant" type="string" value="det1"/>
      <attribute name="axes" source="constant" type="string" value="x_demand,y_demand,.,.,."/>
      <attribute name="NX_class" source="constant" type="string" value="NXdata"/>
      <attribute name="x_demand_indices" source="constant" type="string" value="0"/>
      <attribute name="y_demand_indices" source="constant" type="string" value="1"/>
      <dataset name="x_demand" ndattribute="x" source="ndattribute">
        <attribute name="units" source="constant" type="string" value="mm"/>
      </dataset>
      <dataset name="y_demand" ndattribute="y" source="ndattribute">
        <attribute name="units" source="constant" type="string" value="mm"/>
      </dataset>
      <dataset det_default="true" name="det1" source="detector">
        <attribute name="NX_class" source="constant" type="string" value="SDS"/>
      </dataset>
    </group>
    <group name="NDAttributes" ndattr_default="true">
      <attribute name="NX_class" source="constant" type="string" value="NXcollection"/>
    </group>
  </group>
</hdf5_layout>
"""
        """
    <group name="sum">
      <attribute name="signal" source="constant" type="string" value="sum"/>
      <attribute name="NX_class" source="constant" type="string" value="NXdata"/>
      <dataset name="sum" ndattribute="sum" source="ndattribute"/>
      <hardlink name="x_demand" target="/entry/data/x_demand"/>
      <hardlink name="y_demand" target="/entry/data/y_demand"/>
    </group>
        """

        self.assert_xml(self.s.xml, expected)
        # check that it validates
        self.assertEqual(self.s.stateMachine.state, DState.Ready)

    def set_configured(self):
        # Set all the pvs to the right value
        for attr in sorted(self.send_params):
            self.s.attributes[attr]._value = self.send_params[attr]
        self.s.configure(block=False, **self.in_params)
        cothread.Yield()
        self.check_set("positionMode", True)
        Attribute.update(self.s.attributes["xml"], self.s._sconfig.seq_items[1].seq_params["xml"])
        cothread.Yield()
        self.assertEqual(self.s.state, DState.Ready)

    def test_run(self):
        self.set_configured()
        # Do a run
        spawned = cothread.Spawn(self.s.run)
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Running)
        self.check_set("capture", 1)
        self.assertEqual(self.s.capture, 1)
        Attribute.update(self.s.attributes["capture"], False)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Idle)
        spawned.Wait(1)
        self.assertEqual(self.s.stateMachine.state, DState.Idle)

    def test_mismatch(self):
        self.set_configured()
        Attribute.update(self.s.attributes["extraDimSizeN"], 2)
        self.assertEqual(self.s.stateMachine.state, DState.Ready)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Idle)

    def test_abort(self):
        self.set_configured()
        spawned = cothread.Spawn(self.s.run)
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Running)
        self.check_set("capture", 1)
        self.assertEqual(self.s.capture, 1)
        aspawned = cothread.Spawn(self.s.abort)
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Aborting)
        self.check_set("capture", 0)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Aborted)
        spawned.Wait(1)
        aspawned.Wait(1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
