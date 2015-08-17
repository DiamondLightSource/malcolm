#!/bin/env dls-python
from pkg_resources import require
require("mock")
require("traits")
import unittest
import sys
import os
#import logging
# logging.basicConfig(level=logging.DEBUG)
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.traitsapi import HasTraits, Int, Dict, Str, Enum


class Attribute(HasTraits):
    value = Int
    timestamp = Int

    def __init__(self, value):
        self.value = value


class Status(HasTraits):
    message = Str
    state = Int


class Device(HasTraits):
    attributes = Dict(Str, Attribute)
    status = Status


class TraitsTest(unittest.TestCase):

    def setUp(self):
        self.d = Device()
        self.d.status = Status()
        self.d.attributes["a"] = Attribute(1)
        self.d.attributes["b"] = Attribute(2)

    def test_notifications(self):
        self.changes = []

        def handler(object, name, new):
            self.changes.append((object, name, new))
        self.d.on_trait_change(handler, "status., attributes.")
        self.d.attributes["a"].value = 32
        self.d.attributes["b"].value = 33
        self.d.attributes["b"].value = 33
        self.d.status.state = 34
        self.assertEqual(
            self.changes[0], (self.d.attributes["a"], "value", 32))
        self.assertEqual(
            self.changes[1], (self.d.attributes["b"], "value", 33))
        self.assertEqual(self.changes[2], (self.d.status, "state", 34))

if __name__ == '__main__':
    unittest.main(verbosity=2)
