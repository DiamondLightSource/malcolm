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
import numpy

import logging
#logging.basicConfig()
#logging.basicConfig(level=logging.DEBUG) #, format='%(asctime)s
# %(name)-12s %(levelname)-8s %(message)s')
from mock import MagicMock, patch
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.personalities import SimDetectorPersonality
from malcolm.core import VDouble


class SimDetectorPersonalityTest(unittest.TestCase):

    def setUp(self):
        self.simDetector = MagicMock()
        self.positionPlugin = MagicMock()
        self.hdf5Writer = MagicMock()
        self.s = SimDetectorPersonality("S", self.simDetector, 
                                        self.positionPlugin, self.hdf5Writer)
        self.s.loop_run()
        self.positions = [
            ("y", VDouble, numpy.repeat(numpy.arange(6, 9), 5) * 0.1),
            ("x", VDouble, numpy.tile(numpy.arange(5), 3) * 0.1),
        ]
        self.in_params = dict(exposure=0.1, positions=self.positions,
                              hdf5File="/tmp/demo.hdf5")
        self.numImages = len(self.positions[0][2])
        self.valid_params = {'abortTimeout': 1,
                             'configureTimeout': 1,
                             'exposure': 0.1,
                             'hdf5File': '/tmp/demo.hdf5',
                             'pauseTimeout': 1,
                             'period': 0.1,
                             'positions': self.positions,
                             'resetTimeout': 1,
                             'resumeTimeout': 1,
                             'retraceTimeout': 1,
                             'runTime': self.numImages * 0.1,
                             'runTimeout': 1}
        self.maxDiff = None
        self.simDetector.validate.return_value = dict(
            runTime=self.numImages * 0.1,
            period=0.1)

    def test_init(self):
        base = ['hdf5Writer', 'positionPlugin',
                'simDetector', 'uptime', 'block']
        pause = ['currentStep', 'retraceSteps', 'stepsPerRun', 'totalSteps']
        config = ['exposure', 'hdf5File', 'period', 'positions']
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
        self.hdf5Writer.validate.assert_called_once_with('/tmp', 'demo.hdf5')

    def test_configure(self):
        self.simDetector.state = DState.Idle
        self.positionPlugin.state = DState.Idle
        self.hdf5Writer.state = DState.Idle
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
            self.positions, 1, block=False)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, 'Wait for positionPlugin to configure')
        # Now simulate simDetector ready
        self.positionPlugin.state = DState.Configuring
        self.simDetector.state = DState.Ready
        self.simDetector.stateMachine.timeStamp = time.time()
        self.s._sconfig.on_change(None, None)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, 'Wait for positionPlugin to configure')
        # Now simulate pos plugin ready
        self.positionPlugin.state = DState.Ready
        self.positionPlugin.dimensions = [3, 5]
        self.s._sconfig.on_change(None, None)
        cothread.Yield()
        self.hdf5Writer.configure.assert_called_once_with(
            '/tmp', 'demo.hdf5', 1, 'y_index', 'x_index', '', 3, 5, 1, block=False)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Wait for hdf5Writer to configure")
        # simulate hdfwriter configuring
        self.hdf5Writer.state = DState.Configuring
        self.s._sconfig.on_change(None, None)
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Wait for hdf5Writer to configure")
        # simulate hdfwriter ready
        self.hdf5Writer.state = DState.Ready
        self.s._sconfig.on_change(None, None)
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, 'Done')
        self.assertEqual(self.s.stateMachine.state, DState.Ready)
        now = time.time()
        spawned.Wait(1)
        then = time.time()
        self.assertLess(then - now, 0.5)

    def set_configured(self):
        self.hdf5Writer.state = DState.Ready
        self.simDetector.state = DState.Ready
        self.positionPlugin.state = DState.Ready
        self.s.stateMachine.state = DState.Ready

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
        cothread.Yield()
        cothread.Yield()
        self.hdf5Writer.run.assert_called_once_with(block=False)
        self.positionPlugin.run.assert_called_once_with(block=False)
        self.assertEqual(self.s.stateMachine.message, "Wait for hdf5Writer to run")
        # Now simulate some started
        self.simDetector.acquire = False
        self.positionPlugin.attributes["running"].value = False
        self.hdf5Writer.attributes["capture"].value = True
        self.hdf5Writer.state = DState.Running
        self.hdf5Writer.stateMachine.timeStamp = time.time()
        self.s._srun.on_change(None, None)
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, 'Wait for positionPlugin to run')
        # And a bit more
        self.positionPlugin.attributes["running"].value = True
        self.positionPlugin.state = DState.Running
        self.s._srun.on_change(None, None)
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Wait for simDetector to finish")
        # Now start simDetector
        self.simDetector.state = DState.Running
        self.s._srun.on_change(None, None)
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Wait for simDetector to finish")
        # Now let them all finish except 1
        self.hdf5Writer.state = DState.Idle
        self.simDetector.state = DState.Idle
        self.s._srun.on_change(None, None)
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, 'Wait for positionPlugin to finish')
        # and done
        self.positionPlugin.state = DState.Idle
        self.s._srun.on_change(None, None)
        cothread.Yield()
        cothread.Yield()
        self.assertEqual(self.s.stateMachine.message, "Done")
        self.assertEqual(self.s.state, DState.Idle)
        now = time.time()
        spawned.Wait(1)
        then = time.time()
        self.assertLess(then - now, 0.5)


if __name__ == '__main__':
    unittest.main(verbosity=2)
