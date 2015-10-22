#!/bin/env dls-python
from pkg_resources import require
from collections import OrderedDict
require("mock")
require("pyzmq")
import unittest
import sys
import os
import weakref
import cothread

import logging
# logging.basicConfig()
# logging.basicConfig(level=logging.DEBUG)
from mock import patch, MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqtransport.zmqserversocket import ZmqServerSocket
from malcolm.core.transport import ServerSocket, SType


class InqSock(cothread.EventQueue):
    def __init__(self):
        super(InqSock, self).__init__()
        self.send_multipart = MagicMock()
        self.fd = 0

    def recv_multipart(self, flags=None):
        return self.Wait()


class DummyZmqServerSocket(ZmqServerSocket):

    def send(self, msg, timeout=None):
        return self.sock.send_multipart(msg, flags=1)

    def recv(self, timeout=None):
        return self.sock.recv_multipart(flags=1)

    def make_zmq_sock(self, address):
        return InqSock()

    def close(self):
        self.sock.close()

DummyZmqServerSocket.register("dzmq://")

class ZmqServerSocketTest(unittest.TestCase):

    def setUp(self):
        self.inq = cothread.EventQueue()
        self.ss = ServerSocket.make_socket("dzmq://ipc://frfess.ipc", self.inq)        
        self.ss.loop_run()

    def test_send_func(self):
        self.ss.sock.Signal([43, '{"type": "Call", "id": 0, "endpoint": "zebra", "method": "run"}'])
        typ, args, kwargs = self.inq.Wait()
        self.assertEqual(typ, SType.Call)
        self.assertEqual(kwargs, OrderedDict(endpoint="zebra", method="run"))
        send = args[0]
        self.assertEqual(self.ss.sock.send_multipart.call_count, 0)
        send(SType.Return, 99)
        self.ss.sock.send_multipart.assert_called_once_with([43, '{"type": "Return", "id": 0, "value": 99}'], flags=1)

    def test_2_send_funcs_are_same(self):
        self.ss.sock.Signal([43, '{"type": "Call", "id": 0, "endpoint": "zebra", "method": "run"}'])
        self.ss.sock.Signal([43, '{"type": "Call", "id": 0, "endpoint": "zebra", "method": "run"}'])
        typ1, args1, kwargs1 = self.inq.Wait()
        typ2, args2, kwargs2 = self.inq.Wait()
        self.assertEqual(typ1, typ2)
        self.assertEqual(args1, args2)
        self.assertEqual(kwargs1, kwargs2)

    def test_timestamp(self):
        self.ss.sock.Signal([43, '{"type": "Call", "id": 0, "endpoint": "zebra", "method": "run"}'])
        typ, args, kwargs = self.inq.Wait()
        send = args[0]
        self.assertEqual(self.ss.sock.send_multipart.call_count, 0)
        class ts:
            def to_dict(self):
                return OrderedDict(timeStamp=43.2)
        send(SType.Value, ts())
        self.ss.sock.send_multipart.assert_called_once_with([43, '{"type": "Value", "id": 0, "value": {"timeStamp": {"secondsPastEpoch": 43, "nanoseconds": 200000000, "userTag": 0}}}'], flags=1)

    def test_creation(self):
        self.assertEqual(self.ss.name, "dzmq://ipc://frfess.ipc")
        self.assertEqual(self.ss.address, "ipc://frfess.ipc")
        self.assertEqual(self.ss.processq, self.inq)

    def tearDown(self):
        msgs = []

        def log_debug(msg):
            msgs.append(msg)

        self.ss.log_debug = log_debug
        self.ss = None
        self.assertEqual(msgs, ['Garbage collecting loop', 'Stopping loop',
                                'Waiting for loop to finish', 'Loop finished',
                                'Loop garbage collected'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
