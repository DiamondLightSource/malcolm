#!/bin/env dls-python
from pkg_resources import require
require("mock")
require("pyzmq")
import unittest
import sys
import os
import multiprocessing
import json
import zmq
import time
import cothread

#import logging
#logging.basicConfig(level=logging.DEBUG)
from mock import patch, MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqComms.functionCaller import FunctionCaller
from malcolm.zmqComms.zmqProcess import ZmqProcess, CoStream

class DummyFunctionCaller(FunctionCaller):
    def setup(self):
        self.fe_stream = MagicMock()
        self.cothread = cothread

class FunctionCallerTest(unittest.TestCase):

    def setUp(self):
        self.fc = DummyFunctionCaller("mydevice")
        self.fc.run(block=False)
        
    def test_call_single_return(self):
        def do_response():
            self.fc.handle_fe([json.dumps(
                dict(id=0, type="return", val="return val"))])

        cothread.Spawn(do_response)
        self.assertEqual(self.fc.call("myfunc", bar="bat"), "return val")
        self.fc.fe_stream.send.assert_called_once_with(
            json.dumps(dict(id=0, type="call", method="mydevice.myfunc", args=dict(bar="bat"))))

    def test_error_call(self):
        def do_response():
            self.fc.handle_fe([json.dumps(
                dict(id=0, type="error", name="NameError", message="bad"))])

        cothread.Spawn(do_response)
        self.assertRaises(NameError, self.fc.call, "myfunc", bar="bat")
        self.fc.fe_stream.send.assert_called_once_with(
            json.dumps(dict(id=0, type="call",  method="mydevice.myfunc", args=dict(bar="bat"))))

    def test_call_single_get(self):
        def do_response():
            self.fc.handle_fe([json.dumps(
                dict(id=0, type="return", val="return val"))])

        cothread.Spawn(do_response)
        self.assertEqual(self.fc.get("myparam"), "return val")
        self.fc.fe_stream.send.assert_called_once_with(
            json.dumps(dict(id=0, type="get", param="mydevice.myparam")))

    def test_error_get(self):
        def do_response():
            self.fc.handle_fe([json.dumps(
                dict(id=0, type="error", name="NameError", message="bad"))])

        cothread.Spawn(do_response)
        self.assertRaises(NameError, self.fc.get, "myparam")
        self.fc.fe_stream.send.assert_called_once_with(
            json.dumps(dict(id=0, type="get", param="mydevice.myparam")))


if __name__ == '__main__':
    unittest.main(verbosity=2)
