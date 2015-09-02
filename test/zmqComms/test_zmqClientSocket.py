#!/bin/env dls-python
from pkg_resources import require
from collections import OrderedDict
from malcolm.core.socket import ClientSocket
require("mock")
require("pyzmq")
import unittest
import sys
import os
import weakref
import cothread

import logging
logging.basicConfig()
#logging.basicConfig(level=logging.DEBUG)
from mock import patch, MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqComms.zmqClientSocket import ZmqClientSocket
from malcolm.core.serialize import SType


class DummyZmqClientSocket(ZmqClientSocket):

    def make_zmq_sock(self):
        return MagicMock()


class ZmqClientSocketTest(unittest.TestCase):

    def setUp(self):
        self.cs = DummyZmqClientSocket("ipc://frfe.ipc")
        self.cs.loop_run()

    def test_garbage_collected(self):
        cs = weakref.proxy(self.cs)
        self.cs = None

        def f():
            print cs

        self.assertRaises(ReferenceError, f)

    def test_request(self):
        response = MagicMock()
        typ = SType.Call
        kwargs = OrderedDict()
        kwargs.update(endpoint="zebra1.run")
        self.cs.request(response, typ, kwargs)
        self.cs.sock.send_multipart.assert_called_once_with(
            '{"type": "Call", "id": 0, "endpoint": "zebra1.run"}', flags=1)
        self.assertEqual(response.call_count, 0)

    def test_response(self):
        response = MagicMock()
        def f(flags):
            cothread.Yield()
            return ['{"type": "Return", "id": 0, "value": 32}']
        self.cs.sock.recv_multipart.side_effect = f
        self.cs.request(response, SType.Call, dict(endpoint="zebra1.run"))
        cothread.Yield()
        cothread.Yield()
        response.assert_called_once_with(SType.Return, value=32)

    def test_timeStamp(self):
        response = MagicMock()
        def f(flags):
            cothread.Yield()
            return ['{"type": "Return", "id": 0, "value": {"timeStamp": {"secondsPastEpoch": 43, "nanoseconds": 200000000, "userTag": 0}}}']
        self.cs.sock.recv_multipart.side_effect = f
        self.cs.request(response, SType.Call, dict(endpoint="zebra1.run"))
        cothread.Yield()
        cothread.Yield()
        response.assert_called_once_with(SType.Return, value=OrderedDict(timeStamp=43.2))

    def test_creation(self):
        self.cs = ClientSocket.make_socket("zmq://ipc://frfes.ipc")
        self.assertEqual(self.cs.name, "ipc://frfes.ipc")

    def tearDown(self):
        self.cs = None

if __name__ == '__main__':
    unittest.main(verbosity=2)
