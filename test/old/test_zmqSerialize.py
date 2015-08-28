#!/bin/env dls-python
from pkg_resources import require
from malcolm.core.status import Status
from malcolm.core.device import DState
from malcolm.core.alarm import Alarm, AlarmSeverity, AlarmStatus
from collections import OrderedDict
from IPython.core.display import Pretty
require("mock")
import unittest
import sys
import os
import json
#import logging
# logging.basicConfig(level=logging.DEBUG)
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqComms.zmqSerialize import serialize_return, serialize_call, serialize_get,\
    serialize_error, serialize_ready, serialize_value, serialize_subscribe,\
    serialize_unsubscribe
from malcolm.core.method import Method, wrap_method
from malcolm.core.attribute import Attribute
from malcolm.core.attributes import Attributes
from malcolm.core.timeStamp import TimeStamp
from malcolm.core.traitsapi import Int, Str
import difflib


class DummyDevice(object):
    attributes = Attributes(
        foo=Attribute(Int, "foodesc")
    )
    attributes.add_attributes(bar=Attribute(Str, "bardesc"))


class DummyZebra(object):
    attributes = Attributes(
        PC_BIT_CAP=Attribute(Int, "Which encoders to capture"),
        PC_TSPRE=Attribute(Str, "What time units for capture"),
        CONNECTED=Attribute(Int, "Is zebra connected"),
    )
    status = Status(DState.Configuring)

    @wrap_method(DState.configurable())
    def configure(self, PC_BIT_CAP, PC_TSPRE="ms"):
        "Configure the device"
        pass

    @wrap_method(DState.runnable())
    def run(self):
        "Start a scan running"
        pass
    methods = OrderedDict(configure=configure)
    methods.update(run=run)

    def to_dict(self):
        d = OrderedDict(methods=self.methods)
        d.update(status=self.status)
        d.update(attributes=self.attributes)
        return d


class ZmqSerializeTest(unittest.TestCase):

    def assertStringsEqual(self, first, second):
        """Assert that two multi-line strings are equal.
        If they aren't, show a nice diff.
        """
        self.assertTrue(isinstance(first, str), 'First arg is not a string')
        self.assertTrue(isinstance(second, str), 'Second arg is not a string')

        if first != second:
            message = ''.join(difflib.unified_diff(
                first.splitlines(True), second.splitlines(True)))
            self.fail("Multi-line strings are unequal: %s\n" % message)

    def prettify(self, s):
        pretty = json.dumps(
            json.loads(s, object_pairs_hook=OrderedDict), indent=2)
        return pretty

    def test_serialize_function_call(self):
        s = serialize_call(0, "zebra1.configure", PC_BIT_CAP=1, PC_TSPRE="ms")
        pretty = self.prettify(s)
        expected = '''{
  "type": "Call", 
  "id": 0, 
  "method": "zebra1.configure", 
  "args": {
    "PC_BIT_CAP": 1, 
    "PC_TSPRE": "ms"
  }
}'''
        self.assertStringsEqual(pretty, expected)

    def test_serialize_malcolm_function_call(self):
        s = serialize_call(0, "malcolm.devices")
        pretty = self.prettify(s)
#        print pretty
        expected = '''{
  "type": "Call", 
  "id": 0, 
  "method": "malcolm.devices"
}'''
        self.assertStringsEqual(pretty, expected)

    def test_serialize_get(self):
        s = serialize_get(0, "zebra1.status")
        pretty = self.prettify(s)
        expected = '''{
  "type": "Get", 
  "id": 0, 
  "param": "zebra1.status"
}'''
        self.assertStringsEqual(pretty, expected)

    def test_device_ready(self):
        s = serialize_ready("zebra1")
        pretty = self.prettify(s)
        expected = """{
  "type": "Ready", 
  "device": "zebra1"
}"""
        self.assertStringsEqual(pretty, expected)

    def test_serialize_method_return(self):
        def f(foo, bar="bat"):
            "Hello"
            pass
        method = Method(f)
        method.describe(DummyDevice)
        s = serialize_return(0, method)
        pretty = self.prettify(s)
        expected = '''{
  "type": "Return", 
  "id": 0, 
  "val": {
    "descriptor": "Hello", 
    "args": {
      "foo": {
        "value": null, 
        "type": "Int", 
        "tags": [
          "required"
        ], 
        "descriptor": "foodesc"
      }, 
      "bar": {
        "value": "bat", 
        "type": "Str", 
        "descriptor": "bardesc"
      }
    }
  }
}'''
        self.assertStringsEqual(pretty, expected)

    def test_serialize_status_return(self):
        status = Status(DState.Idle)
        status.update(
            "message", DState.Idle, timeStamp=TimeStamp.from_time(1437663079.853469))
        s = serialize_return(0, status)
        pretty = self.prettify(s)
        expected = '''{
  "type": "Return", 
  "id": 0, 
  "val": {
    "message": "message", 
    "state": {
      "index": 1, 
      "choices": [
        "Fault", 
        "Idle", 
        "Configuring", 
        "Ready", 
        "Running", 
        "Pausing", 
        "Paused", 
        "Aborting", 
        "Aborted", 
        "Resetting"
      ]
    }, 
    "timeStamp": {
      "secondsPastEpoch": 1437663079, 
      "nanoseconds": 853468894, 
      "userTag": 0
    }
  }
}'''
        self.assertStringsEqual(pretty, expected)

    def test_serialize_attributes_return(self):
        DummyDevice.attributes.update(
            "foo", 3, timeStamp=TimeStamp.from_time(1437663842.11881113))
        DummyDevice.attributes.update(
            "bar", "bat", timeStamp=TimeStamp.from_time(1437663842.11881113))
        s = serialize_return(0, DummyDevice.attributes)
        pretty = self.prettify(s)
        expected = '''{
  "type": "Return", 
  "id": 0, 
  "val": {
    "foo": {
      "value": 3, 
      "type": "Int", 
      "descriptor": "foodesc", 
      "alarm": {
        "severity": 0, 
        "status": 0, 
        "message": "No alarm"
      }, 
      "timeStamp": {
        "secondsPastEpoch": 1437663842, 
        "nanoseconds": 118811130, 
        "userTag": 0
      }
    }, 
    "bar": {
      "value": "bat", 
      "type": "Str", 
      "descriptor": "bardesc", 
      "alarm": {
        "severity": 0, 
        "status": 0, 
        "message": "No alarm"
      }, 
      "timeStamp": {
        "secondsPastEpoch": 1437663842, 
        "nanoseconds": 118811130, 
        "userTag": 0
      }
    }
  }
}'''
        self.assertStringsEqual(pretty, expected)

    def test_serialize_zebra_return(self):
        z = DummyZebra()
        for method in z.methods.values():
            method.describe(z)
        z.status.update(
            "Configuring...", DState.Configuring, TimeStamp.from_time(1437663079.853469))
        z.attributes.update(
            "PC_BIT_CAP", 5, timeStamp=TimeStamp.from_time(1437663842.11881113))
        z.attributes.update(
            "PC_TSPRE", "ms", timeStamp=TimeStamp.from_time(1437663842.11881113))
        z.attributes.update("CONNECTED", 0, alarm=Alarm(AlarmSeverity.invalidAlarm, AlarmStatus.deviceStatus,
                                                        message="Communication problem"), timeStamp=TimeStamp.from_time(1437663842.11881113))
        s = serialize_return(0, z)
        pretty = self.prettify(s)
        expected = '''{
  "type": "Return", 
  "id": 0, 
  "val": {
    "methods": {
      "configure": {
        "descriptor": "Configure the device", 
        "args": {
          "PC_BIT_CAP": {
            "value": null, 
            "type": "Int", 
            "tags": [
              "required"
            ], 
            "descriptor": "Which encoders to capture"
          }, 
          "PC_TSPRE": {
            "value": "ms", 
            "type": "Str", 
            "descriptor": "What time units for capture"
          }
        }, 
        "valid_states": [
          "Idle", 
          "Ready"
        ]
      }, 
      "run": {
        "descriptor": "Start a scan running", 
        "args": {}, 
        "valid_states": [
          "Ready", 
          "Paused"
        ]
      }
    }, 
    "status": {
      "message": "Configuring...", 
      "state": {
        "index": 2, 
        "choices": [
          "Fault", 
          "Idle", 
          "Configuring", 
          "Ready", 
          "Running", 
          "Pausing", 
          "Paused", 
          "Aborting", 
          "Aborted", 
          "Resetting"
        ]
      }, 
      "timeStamp": {
        "secondsPastEpoch": 1437663079, 
        "nanoseconds": 853468894, 
        "userTag": 0
      }
    }, 
    "attributes": {
      "CONNECTED": {
        "value": 0, 
        "type": "Int", 
        "descriptor": "Is zebra connected", 
        "alarm": {
          "severity": 3, 
          "status": 1, 
          "message": "Communication problem"
        }, 
        "timeStamp": {
          "secondsPastEpoch": 1437663842, 
          "nanoseconds": 118811130, 
          "userTag": 0
        }
      }, 
      "PC_BIT_CAP": {
        "value": 5, 
        "type": "Int", 
        "tags": [
          "configure"
        ], 
        "descriptor": "Which encoders to capture", 
        "alarm": {
          "severity": 0, 
          "status": 0, 
          "message": "No alarm"
        }, 
        "timeStamp": {
          "secondsPastEpoch": 1437663842, 
          "nanoseconds": 118811130, 
          "userTag": 0
        }
      }, 
      "PC_TSPRE": {
        "value": "ms", 
        "type": "Str", 
        "tags": [
          "configure"
        ], 
        "descriptor": "What time units for capture", 
        "alarm": {
          "severity": 0, 
          "status": 0, 
          "message": "No alarm"
        }, 
        "timeStamp": {
          "secondsPastEpoch": 1437663842, 
          "nanoseconds": 118811130, 
          "userTag": 0
        }
      }
    }
  }
}'''
        self.assertStringsEqual(pretty, expected)
        s = serialize_value(0, z.status)
        pretty = self.prettify(s)
        expected = '''{
  "type": "Value", 
  "id": 0, 
  "val": {
    "message": "Configuring...", 
    "state": {
      "index": 2, 
      "choices": [
        "Fault", 
        "Idle", 
        "Configuring", 
        "Ready", 
        "Running", 
        "Pausing", 
        "Paused", 
        "Aborting", 
        "Aborted", 
        "Resetting"
      ]
    }, 
    "timeStamp": {
      "secondsPastEpoch": 1437663079, 
      "nanoseconds": 853468894, 
      "userTag": 0
    }
  }
}'''
        self.assertStringsEqual(pretty, expected)

    def test_serialize_error(self):
        s = serialize_error(
            0, AssertionError("No device named foo registered"))
        pretty = self.prettify(s)
        expected = '''{
  "type": "Error", 
  "id": 0, 
  "message": "No device named foo registered"
}'''
        self.assertStringsEqual(pretty, expected)

    def test_serialize_subscribe(self):
        s = serialize_subscribe(0, "zebra1.status")
        pretty = self.prettify(s)
        expected = '''{
  "type": "Subscribe", 
  "id": 0, 
  "param": "zebra1.status"
}'''
        self.assertStringsEqual(pretty, expected)

    def test_serialize_unsubscribe(self):
        s = serialize_unsubscribe(0)
        pretty = self.prettify(s)
        expected = '''{
  "type": "Unsubscribe", 
  "id": 0
}'''
        self.assertStringsEqual(pretty, expected)

if __name__ == '__main__':
    unittest.main(verbosity=2)
