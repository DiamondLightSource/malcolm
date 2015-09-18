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
import gc
# logging.basicConfig(level=logging.DEBUG)
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.base import weak_method


class Loop(object):

    def __init__(self, outs):
        self.outs = outs
        self.i = 0
        self.stop_requested = cothread.Event(auto_reset=False)
        self.proc = cothread.Spawn(weak_method(self.event_loop))
        self.status = 0

    def loop_event(self):
        if self.stop_requested:
            raise StopIteration
        cothread.Sleep(0.01)
        self.outs.append(self.i)
        self.i += 1

    def event_loop(self):
        while True:
            try:
                weak_method(self.loop_event)()
            except ReferenceError:
                return
        self.status = 1

    def __del__(self):
        self.stop_requested.Signal()
        self.proc.Wait()


class T(object):

    def t1(self, name):
        try:
            raise Exception
        except Exception as e:
            print 't %s caught' % name

        cothread.Yield()


class LoopTest(unittest.TestCase):

    def test_loop_del_called_when_out_of_scope(self):
        self.outs = []
        l = Loop(self.outs)
        cothread.Sleep(0.1)
        self.assertEqual(self.outs, [0, 1, 2, 3, 4, 5, 6, 7, 8])
        l = None
        cothread.Sleep(0.1)
        self.assertEqual(self.outs, [0, 1, 2, 3, 4, 5, 6, 7, 8])

    def test_exception_referrers(self):
        fg = T()
        bg = T()
        cothread.Spawn(bg.t1, 'background')
        fg.t1('foreground')
        self.assertEqual(sys.getrefcount(fg), 2)

if __name__ == '__main__':
    unittest.main(verbosity=2)
