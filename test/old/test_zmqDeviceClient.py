#!/bin/env dls-python
from pkg_resources import require
require("mock")
require("pyzmq")
import unittest
import sys
import os
import json
import cothread

#import logging
# logging.basicConfig(level=logging.DEBUG)
from mock import MagicMock, call
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqComms.zmqDeviceClient import ZmqDeviceClient


class DummyFunctionCaller(ZmqDeviceClient):

    def setup(self):
        self.fe_stream = MagicMock()
        self.cothread = cothread


class ZmqDeviceClientTest(unittest.TestCase):

    def setUp(self):
        self.fc = DummyFunctionCaller("mydevice")
        self.fc.run(block=False)

    def test_call_single_return(self):
        def do_response():
            self.fc.handle_fe([json.dumps(
                dict(id=0, type="Return", val="return val"))])

        cothread.Spawn(do_response)
        self.assertEqual(self.fc.call("myfunc", bar="bat"), "return val")
        self.fc.fe_stream.send.assert_called_once_with(
            '{"type": "Call", "id": 0, "method": "mydevice.myfunc", "args": {"bar": "bat"}}')

    def test_error_call(self):
        def do_response():
            self.fc.handle_fe([json.dumps(
                dict(id=0, type="Error", message="bad"))])

        cothread.Spawn(do_response)
        self.assertRaises(AssertionError, self.fc.call, "myfunc", bar="bat")
        self.fc.fe_stream.send.assert_called_once_with(
            '{"type": "Call", "id": 0, "method": "mydevice.myfunc", "args": {"bar": "bat"}}')

    def test_call_single_get(self):
        def do_response():
            self.fc.handle_fe([json.dumps(
                dict(id=0, type="Return", val="return val"))])

        cothread.Spawn(do_response)
        self.assertEqual(self.fc.get("myparam"), "return val")
        self.fc.fe_stream.send.assert_called_once_with(
            json.dumps(dict(id=0, type="Get", param="mydevice.myparam")))

    def test_error_get(self):
        def do_response():
            self.fc.handle_fe([json.dumps(
                dict(id=0, type="Error", message="bad"))])

        cothread.Spawn(do_response)
        self.assertRaises(AssertionError, self.fc.get, "myparam")
        self.fc.fe_stream.send.assert_called_once_with(
            json.dumps(dict(id=0, type="Get", param="mydevice.myparam")))

    def test_subscribe(self):
        def do_response():
            self.fc.handle_fe([json.dumps(
                dict(id=0, type="Value", val="initial"))])
            self.fc.handle_fe([json.dumps(
                dict(id=0, type="Value", val="subsequent"))])

        cb = MagicMock()
        s = self.fc.subscribe(cb, "myparam")
        cothread.Spawn(do_response)
        # Yield once to allow spawned do_response and _do_process
        cothread.Yield()
        self.fc.fe_stream.send.assert_called_once_with(
            json.dumps(dict(id=0, type="Subscribe", param="mydevice.myparam")))
        self.fc.fe_stream.reset_mock()
        # Yield again to allow subscribe event loop
        cothread.Yield()
        cb.assert_has_calls([call("initial"), call("subsequent")])
        cb.reset_mock()
        # Now unsubcribe
        s.unsubscribe()
        self.fc.fe_stream.send.assert_called_once_with(
            json.dumps(dict(id=0, type="Unsubscribe")))
        # Now check new updates
        cothread.Spawn(do_response)
        cothread.Yield()
        self.assertFalse(cb.called)


if __name__ == '__main__':
    unittest.main(verbosity=2)
