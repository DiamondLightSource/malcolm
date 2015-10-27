#!/bin/env dls-python
from pkg_resources import require
from collections import OrderedDict
from zmq.error import ZMQError
require("mock")
require("pyzmq")
require("cothread")
import unittest
import sys
import os
import cothread

import logging
# logging.basicConfig()
# logging.basicConfig(level=logging.DEBUG)
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.transport import ServerSocket, ClientSocket, SType


class WsServerSocketProcTest(unittest.TestCase):

    def setUp(self):
        #@cothread.Spawn
        #def ticker():
        #    while True:
        #        print 'I am alive'
        #        cothread.Sleep(0.1)
        self.inq = cothread.EventQueue()
        self.ss = ServerSocket.make_socket(
            "ws://localhost:9000", self.inq)
        self.ss.loop_run()
        #cothread.Sleep(1)
        self.cs = ClientSocket.make_socket(
            "ws://127.0.0.1:9000", timeout=1)
        self.cs.open(self.cs.address)

    def test_gc(self):
        pass

    def test_send_func(self):
        self.cs.send('{"type": "Call", "id": 0, "endpoint": "zebra.run"}')
        typ, args, kwargs = self.inq.Wait(timeout=0.1)
        self.assertEqual(typ, SType.Call)
        self.assertEqual(kwargs, OrderedDict(endpoint="zebra.run"))
        send = args[0]
        send(SType.Return, value=99)
        cs_msg = self.cs.recv()
        self.assertEqual(cs_msg, '{"type": "Return", "id": 0, "value": 99}')

    def tearDown(self):
        def log_debug(msg):
            msgs.append(msg)

        msgs = []
        self.cs.log_debug = log_debug
        self.cs.close()
        self.cs = None
        self.assertEqual(msgs, ['Garbage collecting loop',
                                'Loop garbage collected'])
        msgs = []
        self.ss.log_debug = log_debug
        self.ss = None
        self.assertEqual(msgs, ['Garbage collecting loop', 'Stopping loop',
                                'Waiting for loop to finish', 'Loop finished',
                                'Loop garbage collected'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
