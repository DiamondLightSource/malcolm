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
from malcolm.devices import ArpesScan
from malcolm.core import VDouble, VInt


class boolean_ndarray(np.ndarray):

    def __eq__(self, other):
        return np.allclose(self, other)


class ArpesScanTest(unittest.TestCase):

    def setUp(self):
        self.simDetector = MagicMock()
        self.simDetector.stateMachine.name = "simDetector.sm"
        self.progScan = MagicMock()
        self.progScan.stateMachine.name = "progScan.sm"
        self.s = ArpesScan("S", self.simDetector, self.progScan)
        self.s.loop_run()
        xPoints = [1.0, 1.5, 2.0, 2.5, 2.5, 2.0, 1.5, 1.0, 1.0, 1.5, 2.0, 2.5]
        yPoints = [3.0, 3.0, 3.0, 3.0, 3.2, 3.2, 3.2, 3.2, 3.4, 3.4, 3.4, 3.4]
        self.valid_positions = [
            ("y", VDouble, np.array(yPoints, dtype=np.float64).view(
                boolean_ndarray), 'mm'),
            ("x", VDouble, np.array(xPoints, dtype=np.float64).view(
                boolean_ndarray), 'mm'),
        ]
        self.in_params = dict(xStart=1.0, xStop=2.5, xStep=0.5,
                              yStart=3.0, yStop=3.411, yStep=0.2,
                              exposure=0.1, hdf5File="/tmp/demo.hdf5")
        self.numImages = len(self.valid_positions[0][2])
        self.valid_params = dict(abortTimeout=1,
                                 configureTimeout=1,
                                 exposure=0.1,
                                 hdf5File='/tmp/demo.hdf5',
                                 pauseTimeout=1,
                                 positions=self.valid_positions,
                                 resetTimeout=1,
                                 resumeTimeout=1,
                                 rewindTimeout=1,
                                 runTime=self.numImages * 1.1,
                                 runTimeout=(self.numImages + 1) * 1.1,
                                 totalSteps=12,
                                 xStart=1.0,
                                 xStep=0.5,
                                 xStop=2.5,
                                 yStart=3.0,
                                 yStep=0.2,
                                 yStop=3.4,
                                 )
        self.maxDiff = None
        self.simDetector.validate.return_value = dict(
            runTime=self.numImages * 0.1, runTimeout=(self.numImages + 1) * 0.1)
        self.progScan.validate.return_value = dict(
            runTime=self.numImages * 1.1, runTimeout=(self.numImages + 1) * 1.1)

    def test_npoints_arange(self):
        inp = [0.0, 1.0, 0.1]
        # should give 11 points
        self.assertEqual(self.s._npoints(*inp), 11)
        self.assertEqual(len(self.s._arange(*inp)), 11)
        inp = [0.0, 1.01, 0.1]
        # this should also give 11 points
        self.assertEqual(self.s._npoints(*inp), 11)
        self.assertEqual(len(self.s._arange(*inp)), 11)
        inp = [0.0, 0.99, 0.1]
        # this should give 10 points
        self.assertEqual(self.s._npoints(*inp), 10)
        self.assertEqual(len(self.s._arange(*inp)), 10)

    def test_init(self):
        base = ['progScan', 'simDetector', 'uptime']
        pause = ['currentStep', 'stepsPerRun', 'totalSteps']
        config = ['exposure', 'hdf5File', 'positions', 'xStart',
                  'xStep',
                  'xStop',
                  'yStart',
                  'yStep',
                  'yStop']
        self.assertEqual(self.s.attributes.keys(), base + pause + config)
        self.assertEqual(self.s.progScan, self.progScan)
        self.assertEqual(self.s.simDetector, self.simDetector)

    def test_validate(self):
        actual = self.s.validate(**self.in_params)
        self.assertEqual(actual, self.valid_params)
        self.simDetector.validate.assert_called_once_with(
            "/tmp/demo.hdf5", 0.1, self.valid_positions)
        self.progScan.validate.assert_called_once_with(
            100,
            1.0, 0.5, 4, 0, True, 3,
            3.0, 0.2, 3, -1, False, 2,
        )

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
        self.set_state(self.progScan, DState.Idle)
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
            "/tmp/demo.hdf5", 0.1, self.valid_positions, block=False)
        self.progScan.configure.assert_called_once_with(
            100,
            1.0, 0.5, 4, 0, True, 3,
            3.0, 0.2, 3, -1, False, 2,
            startPoint=1, block=False)
        # Now simulate some plugins ready
        self.set_state(self.simDetector, DState.Ready)
        cothread.Yield()
        self.assertEqual(
            self.s.stateMachine.message, "Wait for plugins to configure")
        # simulate progScan ready
        self.set_state(self.progScan, DState.Ready)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, 'Configuring done')
        self.assertEqual(self.s.stateMachine.state, DState.Ready)
        now = time.time()
        spawned.Wait(1)
        then = time.time()
        self.assertLess(then - now, 0.5)

    def set_configured(self):
        self.set_state(self.simDetector, DState.Idle)
        self.set_state(self.progScan, DState.Idle)
        self.s.configure(block=False, **self.in_params)
        cothread.Yield()
        self.set_state(self.simDetector, DState.Ready)
        self.set_state(self.progScan, DState.Ready)
        cothread.Yield()
        self.assertEqual(self.s.state, DState.Ready)
        self.simDetector.configure.reset_mock()
        self.progScan.configure.reset_mock()

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
        self.simDetector.run.assert_called_once_with(block=False)
        self.assertEqual(
            self.s.stateMachine.message, "Wait for simDetector to run")
        # Now simulate some started
        self.set_attribute(self.simDetector, "running", True)
        self.set_state(self.simDetector, DState.Running)
        cothread.Yield()
        self.progScan.run.assert_called_once_with(block=False)
        self.assertEqual(self.s.stateMachine.message, "Wait for run to finish")
        # Now let simDetector finish
        self.set_state(self.simDetector, DState.Idle)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Wait for run to finish")
        # and done
        self.set_state(self.progScan, DState.Idle)
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
        self.set_state(self.simDetector, DState.Running)
        cothread.Yield()
        self.assertEqual(
            self.s.stateMachine.message, "Wait for simDetector to run")
        self.set_attribute(self.simDetector, "running", True)
        self.set_state(self.progScan, DState.Running)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Wait for run to finish")
        # Now do a few frames
        currentstep = 5
        self.set_attribute(self.simDetector, "currentStep", currentstep)
        cothread.Yield()
        self.assertEqual(self.s.currentStep, currentstep)
        self.assertEqual(self.s.totalSteps, self.numImages)
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
        self.set_state(self.simDetector, DState.Running)
        cothread.Yield()
        self.assertEqual(
            self.s.stateMachine.message, "Wait for simDetector to run")
        self.set_attribute(self.simDetector, "running", True)
        self.set_state(self.progScan, DState.Running)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Wait for run to finish")
        # Now do a few frames
        currentstep = self.numImages
        self.set_attribute(self.simDetector, "currentStep", currentstep)
        cothread.Yield()
        self.assertEqual(self.s.currentStep, currentstep)
        self.assertEqual(self.s.totalSteps, self.numImages)
        # Now finish
        self.set_state(self.simDetector, DState.Idle)
        self.set_state(self.progScan, DState.Idle)
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
            # check we've stopped the progScan
            self.progScan.abort.assert_called_once_with(block=False)
            self.progScan.abort.reset_mock()
            # check we've paused the simDetector
            self.simDetector.pause.assert_called_once_with(block=False)
            self.simDetector.pause.reset_mock()
            self.assertEqual(
                self.s.stateMachine.message, "Wait for progScan to stop")
            # Respond
            self.set_state(self.progScan, DState.Aborted)
            cothread.Yield()
            # Reset
            self.progScan.reset.assert_called_once_with(block=False)
            self.progScan.reset.reset_mock()
            self.assertEqual(
                self.s.stateMachine.message, "Wait for progScan to reset")
            # Respond
            self.set_state(self.progScan, DState.Idle)
            cothread.Yield()
        else:
            rewind = args[0]
            # check we've rewound the simDetector
            self.simDetector.rewind.assert_called_once_with(steps=rewind, block=False)
            self.simDetector.rewind.reset_mock()
        # Check we're waiting for simDetector to finish rewinding
        self.assertEqual(
            self.s.stateMachine.message, 'Wait for simDetector to rewind')
        # Respond
        self.set_state(self.simDetector, DState.Paused)
        cothread.Yield()
        # Check we're reconfiguring progScan
        self.progScan.configure.assert_called_once_with(
            100,
            1.0, 0.5, 4, 0, True, 3,
            3.0, 0.2, 3, -1, False, 2,
            startPoint=currentstep + 1, block=False)
        self.progScan.configure.reset_mock()
        self.assertEqual(
            self.s.stateMachine.message, "Wait for progScan to configure")        
        # Respond
        self.set_state(self.progScan, DState.Ready)
        cothread.Yield()
        # Check we're finished
        self.assertEqual(self.s.stateMachine.message, "Rewinding done")
        now = time.time()
        pspawn.Wait(1)
        then = time.time()
        self.assertLess(then - now, 0.05)


if __name__ == '__main__':
    unittest.main(verbosity=2)
