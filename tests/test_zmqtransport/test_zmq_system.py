#!/bin/env dls-python
from pkg_resources import require
import subprocess
require("mock")
require("pyzmq")
require("cothread")
import unittest
import os
import sys

import logging
#logging.basicConfig()
# logging.basicConfig(level=logging.DEBUG)
# format="%(asctime)s;%(levelname)s;%(message)s")
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.process import Process


from malcolm.core.directoryservice import DirectoryService
from malcolm.core.loop import TimerLoop
from malcolm.core import Device, wrap_method


class Counter(Device):

    def __init__(self, name, timeout=None):
        super(Counter, self).__init__(name, timeout)
        self.counter = 0
        self.add_loop(TimerLoop("timer", self.do_count, 0.01))

    def do_count(self):
        self.counter += 1

    @wrap_method()
    def getCount(self):
        return self.counter

    @wrap_method()
    def hello(self):
        self.cothread.Sleep(0.1)
        return "world"

    @wrap_method()
    def longHello(self):
        self.cothread.Sleep(0.5)
        return "long world"

    def exit(self):
        pass


class ZmqSystemTest(unittest.TestCase):
    # class ZmqSystemTest(object):

    def setUp(self):
        # Spawn ds under cothread
        self.ds = DirectoryService(["zmq://ipc:///tmp/sock.ipc"])
        self.ds.run(block=False)
        self.lp = Process(
            [], "Local Process", ds_string="zmq://ipc:///tmp/sock.ipc")
        self.lp.run(block=False)
        self.lp.ds.createCounter(name="The Counter")
        self.c = self.lp.get_device("The Counter")

    def test_simple_function(self):
        import cothread
        cothread.Sleep(0.2)
        start = self.c.getCount()
        self.assertEqual(self.c.hello(), "world")
        # Hello world takes about 10 ticks
        self.assertAlmostEqual(self.c.getCount(), start + 10, delta=3)
        # Do a long running call
        s = cothread.Spawn(self.c.longHello)
        # Check it returns immediately
        self.assertAlmostEqual(self.c.getCount(), start + 10, delta=3)
        self.assertEqual(self.c.hello(), "world")
        # Hello world takes 10 ticks
        self.assertAlmostEqual(self.c.getCount(), start + 20, delta=3)
        self.assertEqual(s.Wait(), "long world")
        # Long hello takes about 50 ticks from send
        self.assertAlmostEqual(self.c.getCount(), start + 60, delta=8)
        s.Wait()

    def tearDown(self):
        self.c = None
        self.lp.ds.exit()
        self.lp.exit()
        self.lp = None
        self.ds.loop_wait()
        self.ds = None

if __name__ == '__main__':
    unittest.main(verbosity=2)
