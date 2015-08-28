#!/bin/env dls-python
from pkg_resources import require
require("mock")
require("pyzmq")
import unittest
import sys
import os
import json

import logging
#logging.basicConfig(level=logging.DEBUG)
from mock import MagicMock, patch
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

    @patch("malcolm.zmqComms.zmqDeviceWrapper.log.exception")
    def test_no_matching_func_error(self, mock_exception):
        self.expected_reply = '{"type": "Error", "id": 0, "message": "Invalid function foo"}'
        client = self.send_request(id=0,
                                   type="Call", method="zebra1.foo", args=dict(bar="bat"))
        self.dw.be_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])
        self.assertEqual(mock_exception.call_count, 1)

    @patch("malcolm.zmqComms.zmqDeviceWrapper.log.exception")
    def test_wrong_device_name_error(self, mock_exception):
        self.expected_reply = '{"type": "Error", "id": 0, "message": "Wrong device name thing"}'
        client = self.send_request(id=0,
                                   type="Call", method="thing.foo", args=dict(bar="bat"))
        self.dw.be_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])
        self.assertEqual(mock_exception.call_count, 1)

    def test_simple_function(self):
        def func():
            return "done"
        self.dw.device.methods = dict(func=func)
        self.expected_reply = json.dumps(
            dict(id=0, type="Return", val="done"))
        client = self.send_request(id=0,
                                   type="Call", method="zebra1.func", args={})
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
            dict(id=0, type="Return", val=dict(status=dict(message="boo"), attributes={})))
        client = self.send_request(id=0,
                                   type="Get", param="zebra1")
        self.dw.be_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])

    def test_parameter_get(self):
        class dev:

            def to_dict(self):
                return dict(status=dict(message="boo"), attributes={})
        self.dw.device = dev()
        self.expected_reply = json.dumps(
            dict(id=0, type="Return", val="boo"))
        client = self.send_request(id=0,
                                   type="Get", param="zebra1.status.message")
        self.dw.be_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])

    def test_status_function(self):
        def add_listener(send_status, prefix, changes):
            self.send_status = send_status
        self.dw.device.add_listener.side_effect = add_listener

        def func():
            for i in range(10):
                self.send_status(dict(i=i), changes=[])
            return "done"
        self.dw.device.methods = dict(func=func)
        client = self.send_request(id=0,
                                   type="Call", method="zebra1.func", args={})
        # running this directly, not under the ioloop, so get to yield manually
        import cothread
        cothread.Yield()
        cuuids = [a[0][0][0]
                  for a in self.dw.be_stream.send_multipart.call_args_list]
        expected = ["CUUID"] * 11
        self.assertEqual(cuuids, expected)
        messages = [a[0][0][1]
                    for a in self.dw.be_stream.send_multipart.call_args_list]
        expected = [json.dumps(dict(id=0, type="Value", val=dict(i=i))) for i in range(10)] + \
            [json.dumps(dict(id=0, type="Return", val="done"))]
        self.assertEqual(messages, expected)
        self.dw.device.remove_listener.assert_called_once_with(
            self.send_status)

    def test_subscription(self):
        class dev:
            def add_listener(self, callback, prefix="status", changes=False):
                self.callback = callback
            def remove_listener(self, callback):
                self.callback = None
            def to_dict(self):
                return dict(status=dict(message="boo"), attributes={})                
        self.dw.device = dev()
        self.expected_reply = json.dumps(
            dict(id=0, type="Value", val="boo"))
        client = self.send_request(id=0,
                                   type="Subscribe", param="zebra1.status.message")
        self.dw.be_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])
        self.dw.be_stream.send_multipart.reset_mock()
        self.dw.device.callback("boom")
        self.expected_reply = json.dumps(
            dict(id=0, type="Value", val="boom"))
        self.dw.be_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])
        self.dw.be_stream.send_multipart.reset_mock()
        client = self.send_request(id=0, type="Unsubscribe")
        self.expected_reply = json.dumps(
            dict(id=0, type="Return"))
        self.dw.be_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])
        
        
if __name__ == '__main__':
    unittest.main(verbosity=2)
