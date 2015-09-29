#!/bin/env dls-python
from pkg_resources import require
require("mock")
require("cothread")
import unittest
import sys
import os
import time
import cothread
import logging
from mock import MagicMock
#logging.basicConfig(level=logging.DEBUG)

logging.basicConfig()
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.devices.dummyDet import DummyDet, DState, SState, DEvent


class DeviceTest(unittest.TestCase):

    def setUp(self):
        self.d = DummyDet("D", timeout=1)
        self.d.loop_run()
        self.reset_cb_lists()

    def reset_cb_lists(self):
        self.states = []
        self.timeStamps = []
        self.messages = []

    def callback(self, value, changes):
        self.states.append(value.state)
        self.messages.append(value.message)
        self.timeStamps.append(value.timeStamp)

    def test_starts_in_correct_state(self):
        self.assertEqual(self.d.stateMachine.state, DState.Idle)

    def test_enum_classes(self):
        self.assertIn(DState.Idle, DState.configurable())

    def test_setting_up_calls_back_correct_methods(self):
        self.d.add_listener(self.callback, "stateMachine")
        start = time.time()
        ret = self.d.configure(nframes=10, exposure=0.01)
        end = time.time()
        self.d.remove_listener(self.callback)
        self.assertLess(end - start, 0.008)
        expected = [DState.Configuring, DState.Ready]
        self.assertEqual(self.states, expected)
        expected = ["Configuring started", "Configuring finished"]
        self.assertEqual(self.messages, expected)
        self.assertEqual(self.d.sim.nframes, 10)
        self.assertEqual(self.d.sim.exposure, 0.01)

    def test_running_calls_back_correct_methods(self):
        self.d.configure(nframes=3, exposure=0.01)
        self.d.add_listener(self.callback, "stateMachine")
        start = time.time()
        ret = self.d.run()
        end = time.time()
        self.d.remove_listener(self.callback)
        self.assertAlmostEqual(
            end - start, 0.03, delta=0.05)
        expected = [DState.Running] * 4 + [DState.Idle]
        self.assertEqual(self.states, expected)
        expected = ["Starting run"] + \
            ["Running in progress {}% done".format(
                i * 100 / 3) for i in range(4)]
        self.assertEqual(self.messages, expected)

    def test_pausing_calls_back_correct_methods(self):
        exposure = 0.1
        nframes = 5
        npause = 2
        rdelay = 0.1
        self.d.configure(nframes=nframes, exposure=exposure)
        self.d.add_listener(self.callback, "stateMachine")

        def pause():
            cothread.Sleep((npause+0.5)*exposure)
            pstart = time.time()
            self.d.pause()
            self.ptime = time.time() - pstart
            self.pstate = self.d.stateMachine.state
            self.pframes = self.d.sim.nframes
            cothread.Sleep(rdelay)
            rstart = time.time()
            self.d.resume()
            self.rtime = time.time() - rstart
            self.rstate = self.d.stateMachine.state
            self.rframes = self.d.sim.nframes

        t = cothread.Spawn(pause)
        start = time.time()
        self.d.run()
        end = time.time()
        self.assertAlmostEqual(end - start, exposure*(nframes+1) + rdelay, delta=exposure/2)
        # let the pause and resumetask finish
        t.Wait()
        self.assertLess(self.ptime, exposure)
        self.assertEqual(self.pstate, DState.Paused)
        self.assertEqual(self.pframes, nframes - npause)
        self.assertLess(self.rtime, exposure/2)
        self.assertEqual(self.rstate, DState.Running)
        self.assertEqual(self.rframes, nframes-npause)
        expected = [DState.Running] * (npause + 2) + \
            [DState.Pausing] * 3 + [DState.Paused] + \
            [DState.Running] * (self.rframes + 1) + [DState.Idle]
        self.assertEqual(self.states, expected)
        expected = ["Starting run"] + ["Running in progress {}% done".format(i * 100 / nframes) for i in range(npause+1)] + \
            ["Pausing started", "Waiting for detector to stop",
                "Reconfiguring detector for {} frames".format(self.rframes), "Pausing finished"] + ["Starting run"] + \
            ["Running in progress {}% done".format(
                i * 100 / nframes) for i in range(self.rframes-1, nframes+1)]
        self.assertEqual(self.messages, expected)
        self.assertEqual(self.d.sim.nframes, 0)

    def test_run_from_idle_not_allowed(self):
        self.assertRaises(AssertionError, self.d.run)

    def test_configure_with_wrong_params_raises(self):
        self.assertRaises(AssertionError, self.d.configure)

    def test_aborting_works(self):
        self.d.configure(nframes=10, exposure=0.05)
        self.d.add_listener(self.callback, "stateMachine")

        def abort():
            cothread.Sleep(0.27)
            pstart = time.time()
            self.pret = self.d.abort()
            self.ptime = time.time() - pstart
        cothread.Spawn(abort)
        start = time.time()
        self.d.run()
        end = time.time()
        self.assertAlmostEqual(end - start, 0.3, delta=0.02)
        # let the abort task finish
        cothread.Yield()
        self.assertLess(self.ptime, 0.05)
        self.assertEqual(self.d.sim.nframes, 4)
        self.assertEqual(self.d.sim.state, SState.Idle)
        expected = [DState.Running] * 7 + \
            [DState.Aborting] * 2 + [DState.Aborted]
        self.assertEqual(self.states, expected)
        expected = ["Starting run"] + ["Running in progress {}% done".format(i * 100 / 10) for i in range(6)] + \
            ["Aborting", 'Waiting for detector to stop', "Aborted"]
        self.assertEqual(self.messages, expected)
        expected = [0] + [0.05 * i for i in range(6)] + [0.26, 0.26, 0.3]
        self.assertEqual(len(expected), len(self.timeStamps))
        for e, a in zip(expected, self.timeStamps):
            self.assertAlmostEqual(e, a - start, delta=0.02)

    def test_attribute_settings_and_locals(self):
        self.assertEqual(self.d.nframes, None)
        self.d.nframes = 32
        self.assertEqual(self.d.nframes, 32)
        self.assertEqual(self.d.attributes["nframes"].value, 32)
        self.d.foo = 45
        self.assertEqual(self.d.foo, 45)
        self.assertRaises(KeyError, lambda: self.d.attributes["foo"])

    def test_class_attributes(self):
        self.d.nframes = 3
        self.assertEqual(len(self.d.attributes), 9)
        items = [(k, v.value) for k, v in self.d.attributes.items()]
        self.assertEqual(items, [('single', False), ('uptime', None), ('timeout', None), ('currentStep', None), (
            'retraceSteps', None), ('totalSteps', None), ('configureSleep', None), ('exposure', None), ('nframes', 3)])

    def test_uptime(self):
        self.assertEqual(self.d.uptime, None)
        cothread.Sleep(1.1)
        self.assertEqual(self.d.uptime, 1)

    def test_error_message(self):
        self.assertRaisesRegexp(AssertionError, "Arguments not supplied: \['exposure'\]", self.d.configure, nframes=10)
        self.assertRaisesRegexp(AssertionError, "Unknown arguments supplied: \['foo'\]", self.d.configure, nframes=10, exposure=0.1, foo="bar")        

    def test_del_called_when_out_of_scope(self):
        exc = MagicMock()
        self.d.sim.log_exception = exc
        self.d.add_listener(self.callback, "stateMachine")
        self.d.configure(nframes=10, exposure=0.05)
        expected = [DState.Configuring, DState.Ready]
        self.assertEqual(self.states, expected)
        self.states = []
        self.d.stateMachine.post(DEvent.Run)
        cothread.Sleep(0.3)
        self.assertEqual(len(self.states), 7)
        self.assertEqual(exc.call_count, 0)
        self.d = None
        cothread.Sleep(0.3)
        self.assertEqual(len(self.states), 7)
        self.assertEqual(exc.call_count, 5)

if __name__ == '__main__':
    unittest.main(verbosity=2)
