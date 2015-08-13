#!/bin/env dls-python
from pkg_resources import require
require("mock")
require("traits")
import unittest
import sys
import os
import time
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.timeStamp import TimeStamp
from malcolm.core.traitsapi import TraitError


class TimeStampTest(unittest.TestCase):

    def test_now(self):
        now = time.time()
        t = TimeStamp.now()
        self.assertAlmostEqual(t.to_time(), now, delta=0.01)

    def test_readonly(self):
        t = TimeStamp.now()

        def f():
            t.userTag = 32

        self.assertRaises(TraitError, f)

if __name__ == '__main__':
    unittest.main(verbosity=2)
