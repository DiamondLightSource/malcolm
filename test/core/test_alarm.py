#!/bin/env dls-python
import unittest
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.alarm import Alarm, AlarmSeverity, AlarmStatus


class AlarmTest(unittest.TestCase):

    def test_ok(self):
        ok = Alarm.ok()
        self.assertEqual(ok.status, AlarmStatus.noStatus)
        self.assertEqual(ok.severity, AlarmSeverity.noAlarm)
        self.assertEqual(ok.message, "No alarm")

    def test_eq(self):
        ok = Alarm.ok()
        also_ok = Alarm(
            AlarmSeverity.noAlarm, AlarmStatus.noStatus, "No alarm")
        self.assertEqual(ok, also_ok)

if __name__ == '__main__':
    unittest.main(verbosity=2)
