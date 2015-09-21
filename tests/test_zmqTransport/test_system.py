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
# logging.basicConfig()
# logging.basicConfig(level=logging.DEBUG)
# format="%(asctime)s;%(levelname)s;%(message)s")
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.process import Process


class ZmqSystemTest(unittest.TestCase):
    # class ZmqSystemTest(object):

    def setUp(self):
        """
        Creates and starts a PongProc process and sets up sockets to
        communicate with it.

        """
        test_counter = os.path.join(
            os.path.dirname(__file__), "..", "util", "counter_server.py")
        self.ds = subprocess.Popen([sys.executable, test_counter])
        self.lp = Process(
            [], "Local Process", ds_string="zmq://ipc:///tmp/sock.ipc")
        self.lp.run(block=False)
        self.lp.ds.create_Counter(name="The Counter")
        self.c = self.lp.get_device("The Counter")

    def test_simple_function(self):
        import cothread
        cothread.Sleep(0.2)
        start = self.c.get_count()
        self.assertEqual(self.c.hello(), "world")
        # Hello world takes about 10 ticks
        self.assertAlmostEqual(self.c.get_count(), start + 10, delta=3)
        # Do a long running call
        s = cothread.Spawn(self.c.long_hello)
        # Check it returns immediately
        self.assertAlmostEqual(self.c.get_count(), start + 10, delta=3)
        self.assertEqual(self.c.hello(), "world")
        # Hello world takes 10 ticks
        self.assertAlmostEqual(self.c.get_count(), start + 20, delta=3)
        self.assertEqual(s.Wait(), "long world")
        # Long hello takes about 50 ticks from send
        self.assertAlmostEqual(self.c.get_count(), start + 60, delta=5)
        s.Wait()

    def tearDown(self):
        self.c = None
        self.lp.ds.exit()
        self.lp.exit()
        self.lp = None
        self.ds.wait()
        self.ds = None

if __name__ == '__main__':
    unittest.main(verbosity=2)
