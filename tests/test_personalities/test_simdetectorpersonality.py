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
import numpy

import logging
logging.basicConfig()
# logging.basicConfig(level=logging.DEBUG)  # , format='%(asctime)s
# %(name)-12s %(levelname)-8s %(message)s')
from mock import MagicMock, patch
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.personalities import SimDetectorPersonality
from malcolm.core import VDouble


class boolean_ndarray(numpy.ndarray):

    def __eq__(self, other):
        return numpy.array_equal(self, other)


class SimDetectorPersonalityTest(unittest.TestCase):

    def setUp(self):
        self.simDetector = MagicMock()
        self.simDetector.stateMachine.name = "simDetector.sm"
        self.positionPlugin = MagicMock()
        self.positionPlugin.stateMachine.name = "positionPlugin.sm"
        self.hdf5Writer = MagicMock()
        self.hdf5Writer.stateMachine.name = "hdfWriter.sm"
        self.s = SimDetectorPersonality("S", self.simDetector,
                                        self.positionPlugin, self.hdf5Writer)
        self.s.loop_run()
        self.positions = [
            ("y", VDouble, numpy.repeat(numpy.arange(6, 9), 5) * 0.1, 'mm'),
            ("x", VDouble, numpy.tile(numpy.arange(5), 3) * 0.1, 'mm'),
        ]
        self.in_params = dict(exposure=0.1, positions=self.positions,
                              hdf5File="/tmp/demo.hdf5")
        self.numImages = len(self.positions[0][2])
        self.valid_params = dict(abortTimeout=1,
                                 configureTimeout=1,
                                 dimensions=[3, 5],
                                 exposure=0.1,
                                 hdf5File='/tmp/demo.hdf5',
                                 pauseTimeout=1,
                                 period=0.1,
                                 positions=self.positions,
                                 resetTimeout=1,
                                 resumeTimeout=1,
                                 rewindTimeout=1,
                                 runTime=self.numImages * 0.1,
                                 runTimeout=(self.numImages + 1) * 0.1,
                                 totalSteps=15)
        self.maxDiff = None
        self.simDetector.validate.return_value = dict(
            runTime=self.numImages * 0.1, runTimeout=(self.numImages + 1) * 0.1,
            period=0.1)
        self.positionPlugin.validate.return_value = dict(
            dimensions=[3, 5])
        self.hdf5Writer.validate.return_value = dict(
            filePath='/tmp', fileName='demo.hdf5',
            dimNames=['y_index', 'x_index'], dimSizes=[3, 5],
            dimUnits=['mm', 'mm'])
        self.hdf5Writer.configure.arguments = self.hdf5Writer.validate.return_value

    def test_init(self):
        base = ['hdf5Writer', 'positionPlugin',
                'simDetector', 'uptime']
        pause = ['currentStep', 'stepsPerRun', 'totalSteps']
        config = ['dimensions', 'exposure', 'hdf5File', 'period', 'positions']
        self.assertEqual(self.s.attributes.keys(), base + pause + config)
        self.assertEqual(self.s.hdf5Writer, self.hdf5Writer)
        self.assertEqual(self.s.positionPlugin, self.positionPlugin)
        self.assertEqual(self.s.simDetector, self.simDetector)

    def test_validate(self):
        actual = self.s.validate(**self.in_params)
        self.assertEqual(actual, self.valid_params)
        self.simDetector.validate.assert_called_once_with(
            0.1, self.numImages, None)
        self.positionPlugin.validate.assert_called_once_with(self.positions)
        self.hdf5Writer.validate.assert_called_once_with(
            '/tmp', 'demo.hdf5', ['y_index', 'x_index'], [3, 5], ['mm', 'mm'])

    def set_state(self, child, state):
        child.state = state
        child.stateMachine.state = state
        child.stateMachine.timeStamp = time.time()
        changes = dict(state=state, timeStamp=child.stateMachine.timeStamp)
        self.s.post_changes(child.stateMachine, changes)

    def set_attribute(self, child, attr, value):
        child.attributes[attr].value = value
        child.attributes[attr].timeStamp = time.time()
        changes = dict(value=value, timeStamp=child.stateMachine.timeStamp)
        self.s.post_changes(child.attributes[attr], changes)

    def test_configure(self):
        self.set_state(self.simDetector, DState.Idle)
        self.set_state(self.positionPlugin, DState.Idle)
        self.set_state(self.hdf5Writer, DState.Idle)
        spawned = cothread.Spawn(self.s.configure, **self.in_params)
        # Yield to let configure run
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Idle)
        # Yield to let do_config and first do_configsta run
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.state, DState.Configuring)
        # Yield to let Config state machine process
        cothread.Yield()
        self.simDetector.configure.assert_called_once_with(
            0.1, self.numImages, 0.1, 0, block=False)
        self.positionPlugin.configure.assert_called_once_with(
            self.positions, 1, self.simDetector.portName, block=False)
        self.hdf5Writer.configure.assert_called_once_with(
            filePath='/tmp', fileName='demo.hdf5',
            dimNames=['y_index', 'x_index'], dimSizes=[3, 5],
            dimUnits=['mm', 'mm'],
            arrayPort=self.positionPlugin.portName, block=False)
        # Now simulate some plugins ready
        self.set_state(self.positionPlugin, DState.Configuring)
        self.set_state(self.simDetector, DState.Ready)
        self.set_state(self.hdf5Writer, DState.Ready)
        cothread.Yield()
        self.assertEqual(
            self.s.stateMachine.message, "Wait for plugins to configure")
        # simulate positionPlugin ready
        self.set_state(self.positionPlugin, DState.Ready)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, 'Configuring done')
        self.assertEqual(self.s.stateMachine.state, DState.Ready)
        now = time.time()
        spawned.Wait(1)
        then = time.time()
        self.assertLess(then - now, 0.5)

    def set_configured(self):
        self.set_state(self.simDetector, DState.Idle)
        self.set_state(self.positionPlugin, DState.Idle)
        self.set_state(self.hdf5Writer, DState.Idle)
        self.s.configure(block=False, **self.in_params)
        cothread.Yield()
        self.set_state(self.positionPlugin, DState.Ready)
        self.positionPlugin.dimensions = [3, 5]
        cothread.Yield()
        self.set_state(self.simDetector, DState.Ready)
        self.set_state(self.hdf5Writer, DState.Ready)
        cothread.Yield()
        self.assertEqual(self.s.state, DState.Ready)
        self.hdf5Writer.configure.reset_mock()
        self.simDetector.configure.reset_mock()
        self.positionPlugin.configure.reset_mock()

    def test_mismatches(self):
        self.set_configured()
        self.set_state(self.simDetector, DState.Idle)
        self.assertEqual(self.s.state, DState.Ready)
        cothread.Yield()
        self.assertEqual(self.s.state, DState.Idle)

    def test_run(self):
        self.set_configured()
        # Do a run
        spawned = cothread.Spawn(self.s.run)
        # let run() go
        cothread.Yield()
        self.assertEqual(self.s.state, DState.Ready)
        # let do_run go
        cothread.Yield()
        self.assertEqual(self.s.state, DState.Running)
        # Yield to let Config state machine process
        cothread.Yield()
        self.hdf5Writer.run.assert_called_once_with(block=False)
        self.positionPlugin.run.assert_called_once_with(block=False)
        self.assertEqual(
            self.s.stateMachine.message, "Wait for hdf5Writer to run")
        # Now simulate some started
        self.set_attribute(self.positionPlugin, "running", False)
        self.set_attribute(self.hdf5Writer, "capture", True)
        self.set_state(self.hdf5Writer, DState.Running)
        cothread.Yield()
        self.assertEqual(
            self.s.stateMachine.message, 'Wait for positionPlugin to run')
        # And a bit more
        self.set_attribute(self.positionPlugin, "running", True)
        self.set_state(self.positionPlugin, DState.Running)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Wait for run to finish")
        # Now start simDetector
        self.set_state(self.simDetector, DState.Running)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Wait for run to finish")
        # Now let them all finish except 1
        self.set_state(self.simDetector, DState.Idle)
        self.set_state(self.hdf5Writer, DState.Idle)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Wait for run to finish")
        # and done
        self.set_state(self.positionPlugin, DState.Idle)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Running done")
        self.assertEqual(self.s.state, DState.Idle)
        now = time.time()
        spawned.Wait(1)
        then = time.time()
        self.assertLess(then - now, 0.5)

    def test_pause(self):
        self.set_configured()
        # Do a run
        spawned = cothread.Spawn(self.s.run)
        # let run() go
        cothread.Yield()
        self.assertEqual(self.s.state, DState.Ready)
        # let do_run go
        cothread.Yield()
        self.assertEqual(self.s.state, DState.Running)
        # Set everything going
        self.set_state(self.hdf5Writer, DState.Running)
        self.set_attribute(self.hdf5Writer, "capture", True)
        cothread.Yield()
        self.assertEqual(
            self.s.stateMachine.message, 'Wait for positionPlugin to run')
        self.set_state(self.positionPlugin, DState.Running)
        self.set_attribute(self.positionPlugin, "running", True)
        self.set_state(self.simDetector, DState.Running)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Wait for run to finish")
        # Now do a few frames
        currentstep = 5
        self.set_attribute(self.hdf5Writer, "uniqueId", currentstep)
        cothread.Yield()
        self.assertEqual(self.s.currentStep, 5)
        self.assertEqual(self.s.totalSteps, 15)
        self.do_pause(currentstep, self.s.pause)
        # now retrace a bit
        rewind = 3
        self.do_pause(currentstep - rewind, self.s.rewind, rewind)
        self.assertEqual(self.s.currentStep, currentstep - rewind)
        # now continue
        rspawned = cothread.Spawn(self.s.resume)
        # let run() go
        cothread.Yield()
        self.assertEqual(self.s.state, DState.Paused)
        # let do_run go
        cothread.Yield()
        self.assertEqual(self.s.state, DState.Running)
        # Set everything going
        self.set_state(self.hdf5Writer, DState.Running)
        self.set_attribute(self.hdf5Writer, "capture", True)
        cothread.Yield()
        self.assertEqual(
            self.s.stateMachine.message, 'Wait for positionPlugin to run')
        self.set_state(self.positionPlugin, DState.Running)
        self.set_attribute(self.positionPlugin, "running", True)
        self.set_state(self.simDetector, DState.Running)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Wait for run to finish")
        # Now do a few frames
        currentstep = 15
        self.set_attribute(self.hdf5Writer, "uniqueId", currentstep)
        cothread.Yield()
        self.assertEqual(self.s.currentStep, 15)
        self.assertEqual(self.s.totalSteps, 15)
        # Now finish
        self.set_state(self.simDetector, DState.Idle)
        self.set_state(self.hdf5Writer, DState.Idle)
        self.set_state(self.positionPlugin, DState.Idle)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Running done")
        self.assertEqual(self.s.state, DState.Idle)
        now = time.time()
        spawned.Wait(1)
        then = time.time()
        self.assertLess(then - now, 0.5)

    def do_pause(self, currentstep, func, *args):
        # now pause
        pspawn = cothread.Spawn(func, *args)
        # let pause() go
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.state, DState.Rewinding)
        if not args:
            # check we've stopped the plugins
            self.simDetector.abort.assert_called_once_with(block=False)
            self.simDetector.abort.reset_mock()
            self.positionPlugin.abort.assert_called_once_with(block=False)
            self.positionPlugin.abort.reset_mock()
            self.assertEqual(
                self.s.stateMachine.message, "Wait for plugins to stop")
            # Respond
            self.set_state(self.simDetector, DState.Aborted)
            self.set_state(self.positionPlugin, DState.Aborted)
            cothread.Yield()
            # Reset
            self.simDetector.reset.assert_called_once_with(block=False)
            self.simDetector.reset.reset_mock()
            self.positionPlugin.reset.assert_called_once_with(block=False)
            self.positionPlugin.reset.reset_mock()
            self.assertEqual(
                self.s.stateMachine.message, "Wait for plugins to reset")
            # Respond
            self.set_state(self.simDetector, DState.Idle)
            self.set_state(self.positionPlugin, DState.Idle)
            cothread.Yield()

        # check we've reconfigured
        self.simDetector.configure.assert_called_once_with(
            0.1, self.numImages - currentstep, 0.1, currentstep, block=False)
        self.simDetector.configure.reset_mock()
        positions = []
        for n, t, d, u in self.positions:
            positions.append([n, t, d[currentstep:].view(boolean_ndarray), u])
        self.positionPlugin.configure.assert_called_once_with(
            positions, currentstep + 1, self.simDetector.portName, block=False)
        self.positionPlugin.configure.reset_mock()
        self.assertEqual(
            self.s.stateMachine.message, "Wait for plugins to configure")
        # Respond
        self.set_state(self.simDetector, DState.Ready)
        self.set_state(self.positionPlugin, DState.Ready)
        cothread.Yield()
        # Check we're finished
        self.assertEqual(self.s.stateMachine.message, "Rewinding done")
        now = time.time()
        pspawn.Wait(1)
        then = time.time()
        self.assertLess(then - now, 0.05)


if __name__ == '__main__':
    unittest.main(verbosity=2)
