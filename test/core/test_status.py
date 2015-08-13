#!/bin/env dls-python
from pkg_resources import require
from enum import Enum
require("mock")
require("traits")
import unittest
import sys
import os
import time
#import logging
# logging.basicConfig(level=logging.DEBUG)
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.status import Status


class DState(Enum):
    One, Two = range(2)


class StatusTest(unittest.TestCase):

    def setUp(self):
        self.status = Status(DState.One)

    def test_init(self):
        self.assertEqual(self.status.message, "")
        self.assertEqual(self.status.timeStamp, None)
        self.assertEqual(self.status.state, DState.One)

    def test_update(self):
        self.status.update("Being two", DState.Two)
        self.assertEqual(self.status.message, "Being two")
        self.assertAlmostEqual(
            self.status.timeStamp.to_time(), time.time(), delta=0.01)

    def test_listener(self):
        self.values = []

        def cb(name, value):
            self.values.append((name, value))
        self.status.on_trait_change(cb)
        self.status.update("Being two", DState.Two)
        self.status.update("Being three", DState.Two)
        self.assertEqual(len(self.values), 5)
        self.assertEqual(self.values[0], ("state", DState.Two))
        self.assertEqual(self.values[1], ("message", "Being two"))
        self.assertEqual(self.values[2][0], "timeStamp")
        self.assertAlmostEqual(
            self.values[2][1].to_time(), time.time(), delta=0.01)
        self.assertEqual(self.values[3], ("message", "Being three"))
        self.assertEqual(self.values[4][0], "timeStamp")
        self.assertAlmostEqual(
            self.values[4][1].to_time(), time.time(), delta=0.01)
        self.values = []
        self.status.on_trait_change(cb, remove=True)
        self.status.update("Being four", DState.Two)
        self.assertEqual(self.values, [])

    def test_serialize(self):
        self.status.update("Being two", DState.Two)
        d = self.status.to_dict()
        self.assertEqual(d.keys(), ['message', 'state', 'timeStamp'])
        self.assertEqual(d.values()[:2], ['Being two', DState.Two])
        
if __name__ == '__main__':
    unittest.main(verbosity=2)
