#!/bin/env dls-python
from pkg_resources import require
require("mock")
require("pyzmq")
import unittest
import sys
import os
import json

#import logging
# logging.basicConfig(level=logging.DEBUG)
from mock import MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqComms.zmqDeviceWrapper import ZmqDeviceWrapper


class ZmqDeviceWrapperTest(unittest.TestCase):

    def setUp(self):
        self.dw = ZmqDeviceWrapper("zebra1", object)
        self.dw.device = MagicMock()
        self.dw.be_stream = MagicMock()

    def send_request(self, **args):
        client = "CUUID"
        request = json.dumps(args)
        self.dw.handle_be([client, request])
        return client

    def test_no_matching_func_error(self):
        self.expected_reply = json.dumps(
            dict(id=0, type="error", message="Invalid function foo"))
        client = self.send_request(id=0,
                                   type="call", method="zebra1.foo", args=dict(bar="bat"))
        self.dw.be_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])

    def test_wrong_device_name_error(self):
        self.expected_reply = json.dumps(
            dict(id=0, type="error", message="Wrong device name thing"))
        client = self.send_request(id=0,
                                   type="call", method="thing.foo", args=dict(bar="bat"))
        self.dw.be_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])

    def test_simple_function(self):
        def func():
            return "done"
        self.dw.device.methods = dict(func=func)
        self.expected_reply = json.dumps(
            dict(id=0, type="return", val="done"))
        client = self.send_request(id=0,
                                   type="call", method="zebra1.func", args={})
        # running this directly, not under the ioloop, so get to yield manually
        import cothread
        cothread.Yield()
        self.dw.be_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])

    def test_simple_get(self):
        class dev:

            def to_dict(self):
                return dict(status=dict(message="boo"), attributes={})
        self.dw.device = dev()
        self.expected_reply = json.dumps(
            dict(id=0, type="return", val=dict(status=dict(message="boo"), attributes={})))
        client = self.send_request(id=0,
                                   type="get", param="zebra1")
        self.dw.be_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])

    def test_parameter_get(self):
        class dev:

            def to_dict(self):
                return dict(status=dict(message="boo"), attributes={})
        self.dw.device = dev()
        self.expected_reply = json.dumps(
            dict(id=0, type="return", val="boo"))
        client = self.send_request(id=0,
                                   type="get", param="zebra1.status.message")
        self.dw.be_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])

    def test_status_function(self):
        def add_listener(send_status):
            self.send_status = send_status
        self.dw.device.add_listener.side_effect = add_listener

        def func():
            for i in range(10):
                self.send_status(i=i)
            return "done"
        self.dw.device.methods = dict(func=func)
        client = self.send_request(id=0,
                                   type="call", method="zebra1.func", args={})
        # running this directly, not under the ioloop, so get to yield manually
        import cothread
        cothread.Yield()
        cuuids = [a[0][0][0]
                  for a in self.dw.be_stream.send_multipart.call_args_list]
        expected = ["CUUID"] * 11
        self.assertEqual(cuuids, expected)
        messages = [a[0][0][1]
                    for a in self.dw.be_stream.send_multipart.call_args_list]
        expected = [json.dumps(dict(id=0, type="value", val=dict(i=i))) for i in range(10)] + \
            [json.dumps(dict(id=0, type="return", val="done"))]
        self.assertEqual(messages, expected)
        self.dw.device.remove_listener.assert_called_once_with(
            self.send_status)

if __name__ == '__main__':
    unittest.main(verbosity=2)
