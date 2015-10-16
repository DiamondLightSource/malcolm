#!/bin/env dls-python
from pkg_resources import require
from collections import OrderedDict
require("mock")
require("pyzmq")
import unittest
import sys
import os
import cothread

import logging
# logging.basicConfig()
logging.basicConfig(level=logging.DEBUG)
from mock import MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqTransport.zmqClientSocket import ZmqClientSocket
from malcolm.core.transport import ClientSocket, SType


class InqSock(cothread.EventQueue):

    def __init__(self):
        super(InqSock, self).__init__()
        self.send_multipart = MagicMock()
        self.fd = 0

    def recv_multipart(self, flags=None):
        return self.Wait()


class DummyZmqClientSocket(ZmqClientSocket):

    def send(self, msg, timeout=None):
        return self.sock.send_multipart(msg, flags=1)

    def recv(self, timeout=None):
        return self.sock.recv_multipart(flags=1)

    def make_zmq_sock(self, address):
        return InqSock()

    def close(self):
        self.sock.close()

DummyZmqClientSocket.register("dzmq://")


class ZmqClientSocketTest(unittest.TestCase):

    def setUp(self):
        self.cs = ClientSocket.make_socket("dzmq://ipc://frfes.ipc")
        self.cs.loop_run()

    def test_request(self):
        response = MagicMock()
        typ = SType.Call
        kwargs = OrderedDict()
        kwargs.update(endpoint="zebra1.run")
        self.cs.request(response, typ, kwargs)
        self.cs.sock.send_multipart.assert_called_once_with(
            ['{"type": "Call", "id": 0, "endpoint": "zebra1.run"}'], flags=1)
        self.assertEqual(response.call_count, 0)

    def test_response(self):
        response = MagicMock()
        self.cs.sock.Signal(['{"type": "Return", "id": 0, "value": 32}'])
        self.cs.request(response, SType.Call, dict(endpoint="zebra1.run"))
        cothread.Yield()
        response.assert_called_once_with(SType.Return, value=32)

    def test_timeStamp(self):
        response = MagicMock()
        self.cs.sock.Signal(
            ['{"type": "Return", "id": 0, "value": {"timeStamp": {"secondsPastEpoch": 43, "nanoseconds": 200000000, "userTag": 0}}}'])
        self.cs.request(response, SType.Call, dict(endpoint="zebra1.run"))
        cothread.Yield()
        response.assert_called_once_with(
            SType.Return, value=OrderedDict(timeStamp=43.2))

    def test_creation(self):
        self.assertEqual(self.cs.name, "dzmq://ipc://frfes.ipc")
        self.assertEqual(self.cs.address, "ipc://frfes.ipc")

    def tearDown(self):
        msgs = []

        def log_debug(msg):
            msgs.append(msg)

        self.cs.log_debug = log_debug
        self.cs = None
        self.assertEqual(msgs, ['Garbage collecting loop', 'Stopping loop',
                                'Waiting for loop to finish', 'Loop finished',
                                'Loop garbage collected'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
