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
import numpy as np

import logging
logging.basicConfig()
# logging.basicConfig(level=logging.DEBUG)  # , format='%(asctime)s
# %(name)-12s %(levelname)-8s %(message)s')
from mock import MagicMock, patch
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.devices import SimDetector
from malcolm.core import VDouble, VInt


class boolean_ndarray(np.ndarray):

    def __eq__(self, other):
        return np.array_equal(self, other)


class SimDetectorTest(unittest.TestCase):

    def setUp(self):
        self.simDetectorDriver = MagicMock()
        self.simDetectorDriver.stateMachine.name = "simDetectorDriver.sm"
        self.positionPlugin = MagicMock()
        self.positionPlugin.stateMachine.name = "positionPlugin.sm"
        self.hdf5Writer = MagicMock()
        self.hdf5Writer.stateMachine.name = "hdfWriter.sm"
        self.s = SimDetector("S", self.simDetectorDriver,
                                        self.positionPlugin, self.hdf5Writer)
        self.s.loop_run()
        self.positions = [
            ("y", VDouble, np.repeat(np.arange(6, 9), 5) * 0.1, 'mm'),
            ("x", VDouble, np.tile(np.arange(5), 3) * 0.1, 'mm'),
        ]
        self.valid_positions = self.positions + [
            ("y_index", VInt, np.repeat(np.arange(3, dtype=np.int32), 5).view(boolean_ndarray), ''),
            ("x_index", VInt, np.tile(np.arange(5, dtype=np.int32), 3).view(boolean_ndarray), '')
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
                                 positions=self.valid_positions,
                                 resetTimeout=1,
                                 resumeTimeout=1,
                                 rewindTimeout=1,
                                 runTime=self.numImages * 0.1,
                                 runTimeout=(self.numImages + 1) * 0.1,
                                 totalSteps=15)
        self.maxDiff = None
        self.simDetectorDriver.validate.return_value = dict(
            runTime=self.numImages * 0.1, runTimeout=(self.numImages + 1) * 0.1,
            period=0.1)
        #self.positionPlugin.validate.return_value = dict(
        #    dimensions=[3, 5])
        self.hdf5Writer.validate.return_value = dict(
            filePath='/tmp', fileName='demo.hdf5',
            dimNames=['y_index', 'x_index'], dimSizes=[3, 5],
            dimUnits=['mm', 'mm'])
        self.hdf5Writer.configure.arguments = self.hdf5Writer.validate.return_value

    def test_init(self):
        base = ['hdf5Writer', 'positionPlugin',
                'simDetectorDriver', 'uptime']
        pause = ['currentStep', 'stepsPerRun', 'totalSteps']
        config = ['dimensions', 'exposure', 'hdf5File', 'period', 'positions', 'running']
        self.assertEqual(self.s.attributes.keys(), base + pause + config)
        self.assertEqual(self.s.hdf5Writer, self.hdf5Writer)
        self.assertEqual(self.s.positionPlugin, self.positionPlugin)
        self.assertEqual(self.s.simDetectorDriver, self.simDetectorDriver)

    def test_validate(self):
        actual = self.s.validate(**self.in_params)
        self.assertEqual(actual, self.valid_params)
        self.simDetectorDriver.validate.assert_called_once_with(
            0.1, self.numImages, None)
        self.positionPlugin.validate.assert_called_once_with(self.valid_positions)
        self.hdf5Writer.validate.assert_called_once_with(
            '/tmp', 'demo.hdf5', ['y', 'x'], ['mm', 'mm'], ['y_index', 'x_index'], [3, 5])

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
        self.set_state(self.simDetectorDriver, DState.Idle)
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
        self.simDetectorDriver.configure.assert_called_once_with(
            0.1, self.numImages, 0.1, 0, block=False)
        self.positionPlugin.configure.assert_called_once_with(
            self.valid_positions, 1, self.simDetectorDriver.portName, block=False)
        self.hdf5Writer.configure.assert_called_once_with(
            filePath='/tmp', fileName='demo.hdf5',
            dimNames=['y_index', 'x_index'], dimSizes=[3, 5],
            dimUnits=['mm', 'mm'],
            arrayPort=self.positionPlugin.portName, block=False)
        # Now simulate some plugins ready
        self.set_state(self.positionPlugin, DState.Configuring)
        self.set_state(self.simDetectorDriver, DState.Ready)
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
        self.set_state(self.simDetectorDriver, DState.Idle)
        self.set_state(self.positionPlugin, DState.Idle)
        self.set_state(self.hdf5Writer, DState.Idle)
        self.s.configure(block=False, **self.in_params)
        cothread.Yield()
        self.set_state(self.positionPlugin, DState.Ready)
        self.positionPlugin.dimensions = [3, 5]
        cothread.Yield()
        self.set_state(self.simDetectorDriver, DState.Ready)
        self.set_state(self.hdf5Writer, DState.Ready)
        cothread.Yield()
        self.assertEqual(self.s.state, DState.Ready)
        self.hdf5Writer.configure.reset_mock()
        self.simDetectorDriver.configure.reset_mock()
        self.positionPlugin.configure.reset_mock()

    def test_mismatches(self):
        self.set_configured()
        self.set_state(self.simDetectorDriver, DState.Idle)
        self.assertEqual(self.s.state, DState.Ready)
        cothread.Yield()
        self.assertEqual(self.s.state, DState.Idle)

    def test_run(self):
        self.set_configured()
        # Do a run
        self.assertEqual(self.s.running, False)
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
        self.assertEqual(self.s.running, False)
        # Now start simDetectorDriver
        self.set_state(self.simDetectorDriver, DState.Running)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Wait for run to finish")
        self.assertEqual(self.s.running, True)
        # Now let them all finish except 1
        self.set_state(self.simDetectorDriver, DState.Idle)
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
        self.set_state(self.simDetectorDriver, DState.Running)
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
        self.set_state(self.simDetectorDriver, DState.Running)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Wait for run to finish")
        # Now do a few frames
        currentstep = 15
        self.set_attribute(self.hdf5Writer, "uniqueId", currentstep)
        cothread.Yield()
        self.assertEqual(self.s.currentStep, 15)
        self.assertEqual(self.s.totalSteps, 15)
        # Now finish
        self.set_state(self.simDetectorDriver, DState.Idle)
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
            self.simDetectorDriver.abort.assert_called_once_with(block=False)
            self.simDetectorDriver.abort.reset_mock()
            self.positionPlugin.abort.assert_called_once_with(block=False)
            self.positionPlugin.abort.reset_mock()
            self.assertEqual(
                self.s.stateMachine.message, "Wait for plugins to stop")
            # Respond
            self.set_state(self.simDetectorDriver, DState.Aborted)
            self.set_state(self.positionPlugin, DState.Aborted)
            cothread.Yield()
            # Reset
            self.simDetectorDriver.reset.assert_called_once_with(block=False)
            self.simDetectorDriver.reset.reset_mock()
            self.positionPlugin.reset.assert_called_once_with(block=False)
            self.positionPlugin.reset.reset_mock()
            self.assertEqual(
                self.s.stateMachine.message, "Wait for plugins to reset")
            # Respond
            self.set_state(self.simDetectorDriver, DState.Idle)
            self.set_state(self.positionPlugin, DState.Idle)
            cothread.Yield()

        # check we've reconfigured
        self.simDetectorDriver.configure.assert_called_once_with(
            0.1, self.numImages - currentstep, 0.1, currentstep, block=False)
        self.simDetectorDriver.configure.reset_mock()
        positions = []
        for n, t, d, u in self.valid_positions:
            positions.append([n, t, d[currentstep:].view(boolean_ndarray), u])
        self.positionPlugin.configure.assert_called_once_with(
            positions, currentstep + 1, self.simDetectorDriver.portName, block=False)
        self.positionPlugin.configure.reset_mock()
        self.assertEqual(
            self.s.stateMachine.message, "Wait for plugins to configure")
        # Respond
        self.set_state(self.simDetectorDriver, DState.Ready)
        self.set_state(self.positionPlugin, DState.Ready)
        cothread.Yield()
        # Check we're finished
        self.assertEqual(self.s.stateMachine.message, "Rewinding done")
        now = time.time()
        pspawn.Wait(1)
        then = time.time()
        self.assertLess(then - now, 0.05)

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
            ("x", VDouble, xs, 'mm'),
            ("y", VDouble, ys, 'mm'),
        ]
        dimensions, valid_positions = self.s._add_position_indexes(positions)
        self.assertEqual(dimensions, [len(xs)])
        self.assertEqual(len(valid_positions), 3)
        self.assertEqual(valid_positions[2][0], "n_index")
        self.assertTrue(np.array_equal(valid_positions[2][2], np.arange(len(xs), dtype=np.int32)))

if __name__ == '__main__':
    unittest.main(verbosity=2)
