#!/bin/env dls-python
from pkg_resources import require
from collections import OrderedDict
from malcolm.core.socket import ServerSocket
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
from malcolm.zmqComms.zmqServerSocket import ZmqServerSocket
from malcolm.core.serialize import SType


class DummyZmqServerSocket(ZmqServerSocket):

    def make_zmq_sock(self):
        return MagicMock()


class ZmqClientSocketTest(unittest.TestCase):

    def setUp(self):
        self.inq = cothread.EventQueue()
        self.cs = DummyZmqServerSocket("ipc://frfe.ipc", self.inq)
        self.cs.loop_run()

    def test_garbage_collected(self):
        cs = weakref.proxy(self.cs)
        self.cs = None

        def f():
            print cs

        self.assertRaises(ReferenceError, f)

    def test_send_func(self):
        def side_effect(flags):
            cothread.Yield()
            return [43, '{"type": "Call", "id": 0, "endpoint": "zebra.run"}']
        self.cs.sock.recv_multipart.side_effect = side_effect
        typ, args, kwargs = self.inq.Wait()
        self.assertEqual(typ, SType.Call)
        self.assertEqual(kwargs, OrderedDict(endpoint="zebra.run"))
        send = args[0]
        self.assertEqual(self.cs.sock.send_multipart.call_count, 0)
        send(SType.Value, dict(value=99))
        self.cs.sock.send_multipart.assertCalledOnceWith(['{"type": "Return", "id": 0, "value": 32}'])

    def test_2_send_funcs_are_same(self):
        def side_effect(flags):
            cothread.Yield()
            return [43, '{"type": "Call", "id": 0, "endpoint": "zebra.run"}']
        self.cs.sock.recv_multipart.side_effect = side_effect
        typ1, args1, kwargs1 = self.inq.Wait()
        typ2, args2, kwargs2 = self.inq.Wait()
        self.assertEqual(typ1, typ2)
        self.assertEqual(args1, args2)
        self.assertEqual(kwargs1, kwargs2)

    def test_creation(self):
        self.cs = ServerSocket.make_socket("zmq://ipc://frfess.ipc", self.inq)
        self.assertEqual(self.cs.name, "ipc://frfess.ipc")
        self.assertEqual(self.cs.processq, self.inq)

    def tearDown(self):
        self.cs = None

if __name__ == '__main__':
    unittest.main(verbosity=2)
