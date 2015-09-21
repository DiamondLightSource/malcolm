#!/bin/env dls-python
from pkg_resources import require
require("mock")
require("cothread")
import unittest
import sys
import weakref
import os
import cothread
import logging
#logging.basicConfig(level=logging.DEBUG)
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.loop import ILoop, EventLoop, HasLoops


class PulseLoop(ILoop):

    def __init__(self, name, outs):
        super(PulseLoop, self).__init__(name)
        self.outs = outs
        self.i = 0

    def loop_event(self):
        if self.stop_requested:
            raise StopIteration
        cothread.Sleep(0.01)
        self.outs.append(self.i)
        self.i += 1

    def loop_run(self):
        """Start the event loop running"""
        super(PulseLoop, self).loop_run()
        self.stop_requested = self.cothread.Event(auto_reset=False)

    def loop_stop(self):
        """Signal the event loop to stop running and wait for it to finish"""
        super(PulseLoop, self).loop_stop()
        self.stop_requested.Signal()


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

    def assert_gc(self):
        msgs = []

        def log_debug(msg):
            msgs.append(msg)

        self.l.log_debug = log_debug
        self.l = None
        self.assertEqual(msgs, ['Garbage collecting loop', 'Stopping loop',
                                'Waiting for loop to finish', 'Loop finished',
                                'Loop garbage collected'])

    def test_loop_del_called_when_out_of_scope(self):
        self.outs = []
        self.l = PulseLoop("Loop", self.outs)
        self.l.loop_run()
        cothread.Sleep(0.1)
        self.assertEqual(self.outs, [0, 1, 2, 3, 4, 5, 6, 7, 8])
        self.assert_gc()
        cothread.Sleep(0.1)
        self.assertEqual(self.outs, [0, 1, 2, 3, 4, 5, 6, 7, 8])

    def test_event_loop_del_called_when_out_of_scope(self):
        self.outs = []
        self.l = OutEventLoop("OutLoop", self.outs)
        self.l.loop_run()

        def poster(l=weakref.proxy(self.l)):
            for _ in range(15):
                try:
                    l.post(None)
                except ReferenceError:
                    break
                cothread.Sleep(0.01)

        cothread.Spawn(poster)
        cothread.Sleep(0.1)
        self.assertEqual(self.outs, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
        self.assert_gc()
        cothread.Sleep(0.1)
        self.assertEqual(self.outs, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])

    def test_self_stopping_loop_gc(self):
        c = HasLoops("thing")
        l = EventLoop("el")
        l.add_event_handler(None, l.loop_stop)
        c.add_loop(l)
        self.assertEqual(c._loops, [l])
        c.loop_run()
        l.post(None)
        l = None
        cothread.Yield()
        self.assertEqual(c._loops, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
