#!/bin/env dls-python
from pkg_resources import require
import malcolm
require("mock")
require("cothread")
import unittest
import sys
import weakref
import os
import gc
from enum import Enum
import inspect
import cothread
import logging
logging.basicConfig(level=logging.DEBUG)
from mock import patch, MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.loop import ILoop, EventLoop, LState


class PulseLoop(ILoop):

    def __init__(self, name, outs):
        super(PulseLoop, self).__init__(name)
        self.outs = outs

    def loop_run(self):
        """Start the event loop running"""
        super(PulseLoop, self).loop_run()
        self.stop_requested = self.cothread.Event(auto_reset=False)
        self.proc = self.spawn(self.event_loop)

    def event_loop(self):
        i = 0
        while not self.stop_requested:
            cothread.Sleep(0.01)
            self.outs.append(i)
            i += 1
        self.loop_confirm_stopped()

    def loop_stop(self):
        """Signal the event loop to stop running and wait for it to finish"""
        super(PulseLoop, self).loop_stop()
        self.stop_requested.Signal()

    def loop_wait(self):
        """Wait for a loop to finish"""
        self.proc.Wait()


class OutEventLoop(EventLoop):

    def __init__(self, name, outs, timeout=None):
        super(OutEventLoop, self).__init__(name, timeout)
        self.outs = outs
        self.i = 0
        self.add_event_handler(None, self.do_anything)

    def do_anything(self):
        self.outs.append(self.i)
        self.i += 1


class LoopTest(unittest.TestCase):

    def make_pulse(self):
        self.outs = []
        l = PulseLoop("Loop", self.outs)
        l.loop_run()
        cothread.Sleep(0.1)

    def test_loop_del_called_when_out_of_scope(self):
        self.make_pulse()
        self.assertEqual(self.outs, [0, 1, 2, 3, 4, 5, 6, 7, 8])
        cothread.Sleep(0.1)
        self.assertEqual(self.outs, [0, 1, 2, 3, 4, 5, 6, 7, 8])

    def make_event_loop(self):
        self.outs = []
        l = OutEventLoop("OutLoop", self.outs)
        l.loop_run()

        def poster(l=weakref.proxy(l)):
            for _ in range(20):
                try:
                    l.post(None)
                except ReferenceError:
                    break
                cothread.Sleep(0.01)

        cothread.Spawn(poster)
        cothread.Sleep(0.1)

    def test_event_loop_del_called_when_out_of_scope(self):
        self.make_event_loop()
        self.assertEqual(self.outs, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        cothread.Sleep(0.1)
        self.assertEqual(self.outs, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])

if __name__ == '__main__':
    unittest.main(verbosity=2)
