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
from malcolm.wstransport import WsServerSocket
from malcolm.core.transport import ServerSocket, SType


class DummyWsServerSocket(WsServerSocket):

    def open(self, address):
        self.inq = cothread.EventQueue()
        self.server = MagicMock()
        self.event_list = None

        def poll_list(event_list, t):
            cothread.Yield()
            return True

        self.poll_list = poll_list

DummyWsServerSocket.register("dws://")


class WsServerSocketTest(unittest.TestCase):

    def setUp(self):
        self.inq = cothread.EventQueue()
        self.ss = ServerSocket.make_socket("dws://192.168.0.1:8888", self.inq)
        self.ss.loop_run()

    def test_send_func(self):
        me = MagicMock()
        self.ss.inq.Signal(
            [me, '{"type": "Call", "id": 0, "endpoint": "zebra", "method": "run"}'])
        typ, args, kwargs = self.inq.Wait()
        self.assertEqual(typ, SType.Call)
        self.assertEqual(kwargs, OrderedDict(endpoint="zebra", method="run"))
        send = args[0]
        self.assertEqual(me.send.call_count, 0)
        send(SType.Return, 99)
        me.send.assert_called_once_with(
            '{"type": "Return", "id": 0, "value": 99}')

    def test_2_send_funcs_are_same(self):
        me = MagicMock()
        self.ss.inq.Signal(
            [me, '{"type": "Call", "id": 0, "endpoint": "zebra", "method": "run"}'])
        self.ss.inq.Signal(
            [me, '{"type": "Call", "id": 0, "endpoint": "zebra", "method": "run"}'])
        typ1, args1, kwargs1 = self.inq.Wait()
        typ2, args2, kwargs2 = self.inq.Wait()
        self.assertEqual(typ1, typ2)
        self.assertEqual(args1, args2)
        self.assertEqual(kwargs1, kwargs2)

    def test_creation(self):
        self.assertEqual(self.ss.name, "dws://192.168.0.1:8888")
        self.assertEqual(self.ss.address, "dws://192.168.0.1:8888")
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
