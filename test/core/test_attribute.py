#!/bin/env dls-python
from pkg_resources import require

require("mock")
import unittest
import sys
import os
import time
#import logging
# logging.basicConfig(level=logging.DEBUG)
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.attribute import Attribute
from malcolm.core.alarm import Alarm, AlarmSeverity, AlarmStatus
from malcolm.core.traitsapi import Undefined, Str, TraitError


class AttributeTest(unittest.TestCase):

    def setUp(self):
        self.a = Attribute(Str, "The string")

    def test_init(self):
        self.assertEqual(self.a.value, Undefined)
        self.assertEqual(self.a.typ, Str)

    def test_set(self):
        self.a.update("32")
        self.assertEqual(self.a.value, "32")
        self.assertAlmostEqual(self.a.timeStamp.to_time(), time.time(), delta=0.01)

    def test_wrong_type(self):
        self.assertRaises(TraitError, self.a.update, 32)

    def test_monitors(self):
        self.c = []
        def cb(name, value):
            self.c.append((name, value))
        self.a.on_trait_change(cb)
        self.a.value = "boo"
        self.a.value = "44"
        self.a.update("bing", Alarm(AlarmSeverity.majorAlarm, AlarmStatus.deviceStatus, "In error"))
        self.assertEqual(self.c[0], ("value", "boo"))
        self.assertEqual(self.c[1], ("value", "44"))
        self.assertEqual(self.c[2], ("value", "bing"))
        self.assertEqual(self.c[3][0], "alarm")
        self.assertEqual(self.c[3][1].status, AlarmStatus.deviceStatus)
        self.assertEqual(self.c[3][1].severity, AlarmSeverity.majorAlarm)
        self.assertEqual(self.c[3][1].message, "In error")
        self.assertEqual(self.c[4][0], "timeStamp")
        self.assertAlmostEqual(self.c[4][1].to_time(), time.time(), delta=0.01)

    def test_value_update(self):
        alarm = Alarm(AlarmSeverity.majorAlarm, AlarmStatus.deviceStatus, "In error")
        self.a.value.update("bing", alarm)
        self.assertEqual(self.a.value, "bing")
        self.assertEqual(self.a.alarm, alarm)

if __name__ == '__main__':
    unittest.main(verbosity=2)
