#!/bin/env dls-python
from pkg_resources import require
require("mock")
require("pyzmq")
import unittest
import sys
import os
import json

import logging
logging.basicConfig()
# logging.basicConfig(level=logging.DEBUG)
from mock import patch, MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqComms.zmqMalcolmRouter import ZmqMalcolmRouter


class ZmqMalcolmRouterTest(unittest.TestCase):

    def setUp(self):
        self.fr = ZmqMalcolmRouter()
        self.fr.fe_stream = MagicMock()
        self.fr.be_stream = MagicMock()
        self.fr.cs_stream = MagicMock()

    def send_request_check_reply(self, **args):
        client = "CUUID"
        request = json.dumps(args)
        self.fr.handle_fe([client, request])
        self.fr.fe_stream.send_multipart.assert_called_once_with(
            [client, self.expected_reply])

    def test_list_no_devices(self):
        self.expected_reply = json.dumps(dict(id=0, type="Return", val=[]))
        self.send_request_check_reply(
            id=0, type="Call", method="malcolm.devices")

    def test_get_malcolm_returns_devices(self):
        self.expected_reply = '{"type": "Return", "id": 0, "val": {"methods": {"devices": {"descriptor": "List all available malcolm devices", "args": {}}, "exit": {"descriptor": "Stop the router and all of the devices attached to it", "args": {}}}}}'
        self.send_request_check_reply(id=0, type="Get", param="malcolm")

    def test_get_device_forwarded_single_device(self):
        client = "CUUID"
        data = json.dumps(
            dict(id=0, type="Ready", device="zebra1"))
        device = "DUUID"
        self.fr.handle_be([device, client, data])
        request = json.dumps(dict(id=0, type="Get", param="zebra1.status"))
        self.fr.handle_fe([client, request])
        self.fr.be_stream.send_multipart.assert_called_once_with(
            [device, client, request])

    @patch("malcolm.zmqComms.zmqMalcolmRouter.log.exception")
    def test_no_providers_error(self, mock_exception):
        self.expected_reply = '{"type": "Error", "id": 0, "message": "No device named foo registered"}'
        self.send_request_check_reply(
            id=0, type="Call", method="foo.func", args=dict(bar="bat"))
        self.assertEqual(mock_exception.call_count, 1)

    def test_single_provider(self):
        client = "CUUID"
        data = json.dumps(
            dict(type="Ready", device="zebra1"))
        device = "DUUID"
        self.fr.handle_be([device, client, data])
        request = json.dumps(dict(id=0, type="Call", method="zebra1.do"))
        self.fr.handle_fe([client, request])
        self.fr.be_stream.send_multipart.assert_called_once_with(
            [device, client, request])

    def test_provider_responds(self):
        client = "CUUID"
        device = "DUUID"
        data = json.dumps(dict(id=0, type="Return", val=[]))
        self.fr.handle_be([device, client, data])
        self.fr.fe_stream.send_multipart.assert_called_once_with(
            [client, data])

    def test_get_monitor_forwarded_single_device(self):
        client = "CUUID"
        data = json.dumps(
            dict(id=0, type="Ready", device="zebra1"))
        device = "DUUID"
        self.fr.handle_be([device, client, data])
        request = json.dumps(dict(id=0, type="Subscribe", param="zebra1.status"))
        self.fr.handle_fe([client, request])
        self.fr.be_stream.send_multipart.assert_called_once_with(
            [device, client, request])
        self.fr.be_stream.reset_mock()
        request = json.dumps(dict(id=0, type="Unsubscribe"))
        self.fr.handle_fe([client, request])
        self.fr.be_stream.send_multipart.assert_called_once_with(
            [device, client, request])


if __name__ == '__main__':
    unittest.main(verbosity=2)
