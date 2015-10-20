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
# logging.basicConfig(level=logging.DEBUG)
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

    @patch("malcolm.devices.hdf5Writer.PvAttribute", DummyPVAttribute)
    def setUp(self):
        self.s = Hdf5Writer("S", "PRE")
        self.s.loop_run()
        self.in_params = dict(filePath="/tmp", fileName="demo.hdf5")
        self.valid_params = dict(
            filePath="/tmp/", fileName="demo.hdf5", numExtraDims=0,
            posNameDimN="n", posNameDimX="x", posNameDimY="y",
            extraDimSizeN=1, extraDimSizeX=1, extraDimSizeY=1,
            resetTimeout=1, runTime=None, runTimeout=1,
            abortTimeout=1, configureTimeout=1, arrayPort=None)
        self.send_params = {
            'ndAttributeChunk': True, 'swmrMode': True, 'extraDimSizeX': 1,
            'extraDimSizeY': 1, 'filePath': '/tmp/', 'posNameDimN': 'n',
            'fileWriteMode': 'Stream', 'numExtraDims': 0,
            'extraDimSizeN': 1, 'enableCallbacks': True,
            'dimAttDatasets': True, 'lazyOpen': True, 'positionMode': True,
            'fileTemplate': '%s%s', 'fileName': 'demo.hdf5',
            'posNameDimX': 'x', 'posNameDimY': 'y', 
            #"numCapture": 0
            }

    def test_init(self):
        base = ['prefix', 'uptime', 'block']
        pvs = ['arrayPort','capture', 'dimAttDatasets', 'enableCallbacks', 'extraDimSizeN',
               'extraDimSizeX', 'extraDimSizeY', 'fileName', 'filePath',
               'fileTemplate', 'fileWriteMode', 'lazyOpen', 'ndAttributeChunk',
               'numCapture', 'numExtraDims', 'portName', 'posNameDimN', 'posNameDimX',
               'posNameDimY', 'positionMode', 'swmrMode', 'uniqueId', 
               'writeMessage', 'writeStatus', 'xml']
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
        # Yield to let do_config and _sconfig
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
        self.assertEqual(self.s._sconfig.state, self.s._sconfig.SeqState.Done)
        cothread.Yield()
        self.assertEqual(self.s._sconfig.state, self.s._sconfig.SeqState.Idle)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Fault)

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
        Attribute.update(self.s.attributes["capture"], False)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Aborted)
        spawned.Wait(1)
        aspawned.Wait(1)

if __name__ == '__main__':
    unittest.main(verbosity=2)
