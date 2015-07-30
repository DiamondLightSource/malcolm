#!/bin/env dls-python
from pkg_resources import require
require("mock")
require("cothread")
import unittest
import sys
import os
import time
import cothread
#import logging
# logging.basicConfig(level=logging.DEBUG)
# logging.basicConfig()
from mock import MagicMock, patch
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.devices.dummyDet import DummyDet, DState


class DeviceTest(unittest.TestCase):

    def setUp(self):
        self.d = DummyDet("D")

    def test_starts_in_correct_state(self):
        self.assertEqual(self.d.state, DState.Idle)

    def test_enum_classes(self):
        self.assertIn(DState.Idle, DState.configurable())

    def test_setting_up_calls_back_correct_methods(self):
        callback = MagicMock()
        self.d.add_listener(callback)
        start = time.time()
        ret = self.d.configure(nframes=10, exposure=0.01)
        end = time.time()
        self.d.remove_listener(callback)
        self.assertLess(end - start, 0.005)
        states = [a[1]["state"] for a in callback.call_args_list]
        expected = [DState.Configuring] * 1 + [DState.Ready]
        self.assertEqual(states, expected)
        messages = [a[1]["message"] for a in callback.call_args_list]
        expected = ["Configuring started", "Configuring finished"]
        self.assertEqual(messages, expected)
        self.assertEqual(self.d.sim.nframes, 10)
        self.assertEqual(self.d.sim.exposure, 0.01)
        self.assertEqual(ret.to_dict(), callback.call_args_list[-1][1])

    def test_running_calls_back_correct_methods(self):
        self.d.configure(nframes=3, exposure=0.01)
        callback = MagicMock()
        self.d.add_listener(callback)
        start = time.time()
        ret = self.d.run()
        end = time.time()
        self.d.remove_listener(callback)
        self.assertAlmostEqual(
            end - start, 0.03, delta=0.05)
        states = [a[1]["state"] for a in callback.call_args_list]
        expected = [DState.Running] * 4 + [DState.Idle]
        self.assertEqual(states, expected)
        messages = [a[1]["message"] for a in callback.call_args_list]
        expected = ["Starting run"] + \
            ["Running in progress {}% done".format(
                i * 100 / 3) for i in range(4)]
        self.assertEqual(messages, expected)
        self.assertEqual(ret.to_dict(), callback.call_args_list[-1][1])

    def test_pausing_calls_back_correct_methods(self):
        self.d.configure(nframes=10, exposure=0.01)
        callback = MagicMock()
        self.d.add_listener(callback)

        def pause():
            cothread.Sleep(0.06)
            pstart = time.time()
            self.pret = self.d.pause()
            self.ptime = time.time() - pstart
        cothread.Spawn(pause)
        start = time.time()
        self.d.run()
        end = time.time()
        self.assertAlmostEqual(end - start, 0.06, delta=0.01)
        # let the pause task finish
        cothread.Yield()
        self.assertEqual(self.pret.to_dict(), callback.call_args_list[-1][1])
        self.assertLess(self.ptime, 0.01)
        self.assertEqual(self.d.sim.nframes, 4)
        states = [a[1]["state"] for a in callback.call_args_list]
        expected = [DState.Running] * 7 + \
            [DState.Pausing] * 3 + [DState.Paused]
        self.assertEqual(states, expected)
        messages = [a[1]["message"] for a in callback.call_args_list]
        expected = ["Starting run"] + ["Running in progress {}% done".format(i * 100 / 10) for i in range(6)] + \
            ["Pausing started", "Waiting for detector to stop",
                "Reconfiguring detector", "Pausing finished"]
        self.assertEqual(messages, expected)
        # Now paused, so resume and get the last 4 frames
        callback.reset_mock()
        start = time.time()
        ret = self.d.run()
        end = time.time()
        self.assertAlmostEqual(end - start, 0.04, delta=0.01)
        self.assertEqual(self.d.sim.nframes, 0)
        states = [a[1]["state"] for a in callback.call_args_list]
        expected = [DState.Running] * 5 + [DState.Idle]
        self.assertEqual(states, expected)
        messages = [a[1]["message"] for a in callback.call_args_list]
        expected = ["Starting run"] + \
            ["Running in progress {}% done".format(
                i * 100 / 10) for i in range(6, 11)]
        self.assertEqual(messages, expected)
        self.assertEqual(ret.to_dict(), callback.call_args_list[-1][1])

    def test_run_from_idle_not_allowed(self):
        self.assertRaises(AssertionError, self.d.run)

    def test_configure_with_wrong_params_raises(self):
        self.assertRaises(TypeError, self.d.configure)

    def test_attribute_settings_and_locals(self):
        self.assertEqual(self.d.nframes, None)
        self.d.nframes = 32
        self.assertEqual(self.d.nframes, 32)
        self.assertEqual(self.d.attributes.nframes, 32)
        self.d.foo = 45
        self.assertEqual(self.d.foo, 45)
        self.assertRaises(KeyError, lambda: self.d.attributes.foo)


if __name__ == '__main__':
    unittest.main(verbosity=2)
