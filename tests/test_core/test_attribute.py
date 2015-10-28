#!/bin/env dls-python
import unittest
import sys
import os
import time
import logging
import numpy
from mock import MagicMock
# logging.basicConfig(level=logging.DEBUG)
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.attribute import Attribute, HasAttributes
from malcolm.core.alarm import Alarm, AlarmSeverity, AlarmStatus
from malcolm.core.vtype import VString, VInt, VStringArray, VTable, VLong


class Container(HasAttributes):

    def __init__(self, name):
        super(Container, self).__init__(name)
        self.add_attributes(s=Attribute(VString, "The String"),
                            i=Attribute(VInt, "The Int"))


class AttributeTest(unittest.TestCase):

    def setUp(self):
        self.c = Container("The Container")
        self.s = self.c.attributes["s"]
        self.i = self.c.attributes["i"]

    def test_init(self):
        self.assertEqual(self.s.value, None)
        self.assertEqual(self.s.typ, VString())

    def test_set(self):
        self.s.update("32")
        self.assertEqual(self.s.value, "32")
        self.assertAlmostEqual(self.s.timeStamp, time.time(), delta=0.01)

    def test_set_from_container(self):
        self.c.s = "94"
        self.assertEqual(self.s.value, "94")

    def test_wrong_type(self):
        self.assertRaises(AssertionError, self.i.update, 32.5)

    def test_monitors(self):
        self.changes = []

        def cb(value, changes):
            self.changes.append(changes)
        self.c.i = 42
        self.c.add_listener(cb)
        self.assertEqual(len(self.changes), 0)
        self.c.i = 32
        self.assertEqual(len(self.changes), 1)
        items = sorted(self.changes.pop().items())
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0][0], "attributes.i.timeStamp")
        self.assertAlmostEqual(items[0][1], time.time(), delta=0.01)
        self.assertEqual(items[1][0], "attributes.i.value")
        self.assertEqual(items[1][1], 32)
        major_alarm = Alarm(AlarmSeverity.majorAlarm,
                            AlarmStatus.Read,
                            "In error")
        self.s.update("bing", major_alarm)
        self.assertEqual(len(self.changes), 1)
        items = sorted(self.changes.pop().items())
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0][0], "attributes.s.alarm")
        self.assertEqual(items[0][1], major_alarm)
        self.assertEqual(items[1][0], "attributes.s.timeStamp")
        self.assertAlmostEqual(items[1][1], time.time(), delta=0.01)
        self.assertEqual(items[2][0], "attributes.s.value")
        self.assertEqual(items[2][1], "bing")

    def test_to_dict(self):
        d = self.s.to_dict()
        self.assertEqual(d.keys(), ['type', 'descriptor'])
        self.assertEqual(d.values(), [VString(), 'The String'])
        self.s.update("wow", timeStamp=3.2)
        d = self.s.to_dict()
        self.assertEqual(
            d.keys(), ['value', 'type', 'descriptor', 'alarm', 'timeStamp'])
        self.assertEqual(
            d.values(), ['wow', VString(), 'The String', Alarm.ok(), 3.2])

    def test_lists(self):
        a = Attribute(VStringArray, "List of strings")
        a.update(["c", "b"])
        self.assertEqual(a.value, ["c", "b"])
        self.assertRaises(AssertionError, a.update, "c")

    def test_compare_vtables(self):
        a = Attribute(VTable, "Positions")
        a.notify_listeners = MagicMock()
        t1 = [("x", VLong, numpy.arange(5, dtype=numpy.int64), ''), 
              ("y", VLong, numpy.arange(5, dtype=numpy.int64) + 2, 'mm')]
        a.update(t1, None, 1.0)
        a.notify_listeners.assert_called_with(
            dict(value=t1, alarm=Alarm.ok(), timeStamp=1.0))
        a.update(t1, None, 1.0)
        a.notify_listeners.assert_called_with(dict())
        t2 = [("x", VLong, numpy.arange(5, dtype=numpy.int64) + 3, ''),
              ("y", VLong, numpy.arange(5, dtype=numpy.int64) + 2, '')]
        a.update(t2, None, 1.0)
        a.notify_listeners.assert_called_with(dict(value=t2))


if __name__ == '__main__':
    unittest.main(verbosity=2)
