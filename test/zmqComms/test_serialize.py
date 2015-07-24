#!/bin/env dls-python
from pkg_resources import require
from malcolm.core.status import Status
from malcolm.core.device import DState
from malcolm.core.alarm import Alarm, AlarmSeverity, AlarmStatus
from IPython.core.display import Pretty
require("mock")
require("cothread")
import unittest
import sys
import os
from enum import Enum
import json
import inspect
#import logging
# logging.basicConfig(level=logging.DEBUG)
from mock import patch, MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqComms.serialize import serialize_return, serialize_call, serialize_get,\
    serialize_error, serialize_ready
from malcolm.core.method import Method, wrap_method
from malcolm.core.attribute import Attributes
from malcolm.core.timeStamp import TimeStamp
import difflib


class DummyDevice(object):
    attributes = Attributes(foo=(int, "foodesc"), bar=(str, "bardesc"))

class DummyZebra(object):
    attributes = Attributes(
        PC_BIT_CAP=(int, "Which encoders to capture"),
        PC_TSPRE=(str, "What time units for capture"),
        CONNECTED=(int, "Is zebra connected"),
    )
    status = Status("", DState.Configuring)
    @wrap_method(DState.configurable())
    def configure(self, PC_BIT_CAP, PC_TSPRE="ms"):
        "Configure the device"
        pass
    @wrap_method(DState.runnable())
    def run(self):
        "Start a scan running"
        pass
    methods = dict(configure=configure, run=run)
    def to_dict(self):
        return dict(status=self.status, methods=self.methods, attributes=self.attributes)
    
class SerializeTest(unittest.TestCase):
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

    def test_serialize_function_call(self):
        s = serialize_call("zebra1", "configure", PC_BIT_CAP=1, PC_TSPRE="ms")
        pretty = json.dumps(json.loads(s), indent=2)
#        print pretty
        expected = '''{
  "device": "zebra1", 
  "args": {
    "PC_BIT_CAP": 1, 
    "PC_TSPRE": "ms"
  }, 
  "type": "call", 
  "method": "configure"
}'''
        self.assertStringsEqual(pretty, expected)
        
    def test_serialize_get(self):
        s = serialize_get("zebra1", "status")
        pretty = json.dumps(json.loads(s), indent=2)
        expected = '''{
  "device": "zebra1", 
  "type": "get", 
  "param": "status"
}'''
        self.assertStringsEqual(pretty, expected)

    def test_serialize_error(self):
        s = serialize_error(AssertionError("No device named foo registered"))
        pretty = json.dumps(json.loads(s), indent=2)
        expected = '''{
  "message": "No device named foo registered", 
  "type": "error", 
  "name": "AssertionError"
}'''
        self.assertStringsEqual(pretty, expected)
                    
    def test_serialize_method_return(self):
        def f(foo, bar="bat"):
            "Hello"
            pass
        method = Method(f)
        method.describe(DummyDevice)
        s = serialize_return(method)
        pretty = json.dumps(json.loads(s), indent=2)
        expected = '''{
  "type": "return", 
  "val": {
    "descriptor": "Hello", 
    "args": {
      "foo": {
        "descriptor": "foodesc", 
        "type": "int", 
        "value": "arg_required"
      }, 
      "bar": {
        "descriptor": "bardesc", 
        "type": "str", 
        "value": "bat"
      }
    }
  }
}'''
        self.assertStringsEqual(pretty, expected)

    def test_serialize_status_return(self):
        status = Status("", DState.Idle)
        status.update("message", 0.1, timeStamp=TimeStamp.from_time(1437663079.853469))
        s = serialize_return(status)
        pretty = json.dumps(json.loads(s), indent=2)
        expected = '''{
  "type": "return", 
  "val": {
    "timeStamp": {
      "nanoseconds": 853468894, 
      "userTag": 0, 
      "secondsPastEpoch": 1437663079
    }, 
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
        "Aborted"
      ]
    }, 
    "percent": 0.1, 
    "message": "message"
  }
}'''
        self.assertStringsEqual(pretty, expected)        

    def test_serialize_attributes_return(self):
        DummyDevice.attributes.set_value("foo", 3, timeStamp = TimeStamp.from_time(1437663842.11881113))
        DummyDevice.attributes.set_value("bar", "bat", timeStamp = TimeStamp.from_time(1437663842.11881113))
        s = serialize_return(DummyDevice.attributes)
        pretty = json.dumps(json.loads(s), indent=2)
        expected = '''{
  "type": "return", 
  "val": {
    "foo": {
      "descriptor": "foodesc", 
      "alarm": {
        "status": 0, 
        "message": "No alarm", 
        "severity": 0
      }, 
      "type": "int", 
      "value": 3, 
      "timeStamp": {
        "nanoseconds": 118811130, 
        "userTag": 0, 
        "secondsPastEpoch": 1437663842
      }
    }, 
    "bar": {
      "descriptor": "bardesc", 
      "alarm": {
        "status": 0, 
        "message": "No alarm", 
        "severity": 0
      }, 
      "type": "str", 
      "value": "bat", 
      "timeStamp": {
        "nanoseconds": 118811130, 
        "userTag": 0, 
        "secondsPastEpoch": 1437663842
      }
    }
  }
}'''
        self.assertStringsEqual(pretty, expected)

    def test_device_ready(self):
        s = serialize_ready("zebra1", "ipc://zebra1.ipc")
        pretty = json.dumps(json.loads(s), indent=2)
        expected = """{
  "device": "zebra1", 
  "pubsocket": "ipc://zebra1.ipc", 
  "type": "ready"
}"""
        self.assertStringsEqual(pretty, expected)

    def test_serialize_zebra_return(self):
        z = DummyZebra()
        for method in z.methods.values():
            method.describe(z)
        z.status.update("Configuring...", 53.4, DState.Configuring, TimeStamp.from_time(1437663079.853469))
        z.attributes.set_value("PC_BIT_CAP", 5, timeStamp = TimeStamp.from_time(1437663842.11881113))
        z.attributes.set_value("PC_TSPRE", "ms", timeStamp = TimeStamp.from_time(1437663842.11881113))
        z.attributes.set_value("CONNECTED", 0, alarm=Alarm(AlarmSeverity.invalidAlarm, AlarmStatus.deviceStatus, message="Communication problem"), timeStamp = TimeStamp.from_time(1437663842.11881113))
        s = serialize_return(z)
        pretty = json.dumps(json.loads(s), indent=2)
        expected = '''{
  "type": "return", 
  "val": {
    "status": {
      "timeStamp": {
        "nanoseconds": 853468894, 
        "userTag": 0, 
        "secondsPastEpoch": 1437663079
      }, 
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
          "Aborted"
        ]
      }, 
      "percent": 53.4, 
      "message": "Configuring..."
    }, 
    "attributes": {
      "PC_BIT_CAP": {
        "tags": [
          "configure"
        ], 
        "timeStamp": {
          "nanoseconds": 118811130, 
          "userTag": 0, 
          "secondsPastEpoch": 1437663842
        }, 
        "alarm": {
          "status": 0, 
          "message": "No alarm", 
          "severity": 0
        }, 
        "value": 5, 
        "descriptor": "Which encoders to capture", 
        "type": "int"
      }, 
      "CONNECTED": {
        "descriptor": "Is zebra connected", 
        "alarm": {
          "status": 1, 
          "message": "Communication problem", 
          "severity": 3
        }, 
        "type": "int", 
        "value": 0, 
        "timeStamp": {
          "nanoseconds": 118811130, 
          "userTag": 0, 
          "secondsPastEpoch": 1437663842
        }
      }, 
      "PC_TSPRE": {
        "tags": [
          "configure"
        ], 
        "timeStamp": {
          "nanoseconds": 118811130, 
          "userTag": 0, 
          "secondsPastEpoch": 1437663842
        }, 
        "alarm": {
          "status": 0, 
          "message": "No alarm", 
          "severity": 0
        }, 
        "value": "ms", 
        "descriptor": "What time units for capture", 
        "type": "str"
      }
    }, 
    "methods": {
      "run": {
        "descriptor": "Start a scan running", 
        "args": {}, 
        "valid_states": [
          "Ready", 
          "Paused"
        ]
      }, 
      "configure": {
        "descriptor": "Configure the device", 
        "args": {
          "PC_BIT_CAP": {
            "descriptor": "Which encoders to capture", 
            "type": "int", 
            "value": "arg_required"
          }, 
          "PC_TSPRE": {
            "descriptor": "What time units for capture", 
            "type": "str", 
            "value": "ms"
          }
        }, 
        "valid_states": [
          "Idle", 
          "Ready"
        ]
      }
    }
  }
}'''
        self.assertStringsEqual(pretty, expected)
        s = serialize_return(z.status)
        pretty = json.dumps(json.loads(s), indent=2)
        expected = '''{
  "type": "return", 
  "val": {
    "timeStamp": {
      "nanoseconds": 853468894, 
      "userTag": 0, 
      "secondsPastEpoch": 1437663079
    }, 
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
        "Aborted"
      ]
    }, 
    "percent": 53.4, 
    "message": "Configuring..."
  }
}'''
        self.assertStringsEqual(pretty, expected)
        

if __name__ == '__main__':
    unittest.main(verbosity=2)
