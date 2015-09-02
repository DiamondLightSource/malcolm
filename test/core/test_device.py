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
# logging.basicConfig(level=logging.DEBUG)

# logging.basicConfig()
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

    def callback(self, changes):
        old_state, old_message = None, None
        if self.states:
            old_state = self.states[-1]
        if self.messages:
            old_message = self.messages[-1]
        self.states.append(changes.get("state", old_state))
        self.messages.append(changes.get("message", old_message))
        self.timeStamps.append(changes["timeStamp"])

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
        self.assertLess(end - start, 0.005)
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
        self.d.configure(nframes=10, exposure=0.01)
        self.d.add_listener(self.callback, "stateMachine")

        def pause():
            cothread.Sleep(0.06)
            pstart = time.time()
            self.d.pause()
            self.ptime = time.time() - pstart
            self.pstate = self.d.stateMachine.state
            self.pframes = self.d.sim.nframes
            cothread.Sleep(0.06)
            rstart = time.time()
            self.d.resume()
            self.rtime = time.time() - rstart
            self.rstate = self.d.stateMachine.state
            self.rframes = self.d.sim.nframes

        t = cothread.Spawn(pause)
        start = time.time()
        self.d.run()
        end = time.time()
        self.assertAlmostEqual(end - start, 0.17, delta=0.02)
        # let the pause and resumetask finish
        t.Wait()
        self.assertLess(self.ptime, 0.01)
        self.assertEqual(self.pstate, DState.Paused)
        self.assertEqual(self.pframes, 5)
        self.assertLess(self.rtime, 0.01)
        self.assertEqual(self.rstate, DState.Running)
        self.assertEqual(self.rframes, 5)
        expected = [DState.Running] * 7 + \
            [DState.Pausing] * 3 + [DState.Paused] + \
            [DState.Running] * 6 + [DState.Idle]
        self.assertEqual(self.states, expected)
        expected = ["Starting run"] + ["Running in progress {}% done".format(i * 100 / 10) for i in range(6)] + \
            ["Pausing started", "Waiting for detector to stop",
                "Reconfiguring detector for 5 frames", "Pausing finished"] + ["Starting run"] + \
            ["Running in progress {}% done".format(
                i * 100 / 10) for i in range(5, 11)]
        self.assertEqual(self.messages, expected)
        self.assertEqual(self.d.sim.nframes, 0)

    def test_run_from_idle_not_allowed(self):
        self.assertRaises(AssertionError, self.d.run)

    def test_configure_with_wrong_params_raises(self):
        self.assertRaises(TypeError, self.d.configure)

    def test_aborting_works(self):
        self.d.configure(nframes=10, exposure=0.05)
        self.d.add_listener(self.callback, "stateMachine")

        def abort():
            cothread.Sleep(0.26)
            pstart = time.time()
            self.pret = self.d.abort()
            self.ptime = time.time() - pstart
        cothread.Spawn(abort)
        start = time.time()
        self.d.run()
        end = time.time()
        self.assertAlmostEqual(end - start, 0.3, delta=0.005)
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
            self.assertAlmostEqual(e, a - start, delta=0.005)

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
        self.assertEqual(len(self.d.attributes), 7)
        items = [(k, v.value) for k, v in self.d.attributes.items()]
        self.assertEqual(items, [('single', False), ('timeout', None), ('current_step', None), (
            'retrace_steps', None), ('total_steps', None), ('exposure', None), ('nframes', 3)])

    def test_del_called_when_out_of_scope(self):
        self.d.add_listener(self.callback, "stateMachine")
        self.d.configure(nframes=10, exposure=0.05)
        expected = [DState.Configuring, DState.Ready]
        self.assertEqual(self.states, expected)
        self.states = []
        self.d.stateMachine.post(DEvent.Run)
        cothread.Sleep(0.3)
        self.assertEqual(len(self.states), 7)
        self.d = None
        cothread.Sleep(0.3)
        self.assertEqual(len(self.states), 7)

if __name__ == '__main__':
    unittest.main(verbosity=2)
