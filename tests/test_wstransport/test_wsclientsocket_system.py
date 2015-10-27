#!/bin/env dls-python
from pkg_resources import require
from collections import OrderedDict
from zmq.error import ZMQError
require("mock")
# print  require("pyzmq")
# require("cothread")
import unittest
import sys
import os
import cothread

import logging
# logging.basicConfig()
# logging.basicConfig(level=logging.DEBUG)
from mock import MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.transport import ClientSocket, ServerSocket, SType


class WsClientSocketProcTest(unittest.TestCase):

    def setUp(self):
        self.ss = ServerSocket.make_socket(
            "ws://localhost:8888", None, timeout=1)
        self.ss.open(self.ss.address)
        self.ss.cothread = cothread

        def handle_requests():
                try:
                    m = self.ss.recv(0.1)
                except:
                    pass
                else:
                    print "s,", m

        self.cs = ClientSocket.make_socket("ws://127.0.0.1:8888")
        sp = cothread.Spawn(handle_requests)
        self.cs.loop_run()
        sp.Wait()

    def test_gc(self):
        pass

    def test_request(self):
        response = MagicMock()
        typ = SType.Call
        kwargs = OrderedDict()
        kwargs.update(endpoint="zebra1.run")
        self.cs.request(response, typ, kwargs)
        for i in range(5):
            try:
                ss_msg = self.ss.recv(0.1)
                break
            except:
                pass
        self.assertEqual(
            ss_msg[1], '{"type": "Call", "id": 0, "endpoint": "zebra1.run"}')
        self.assertEqual(response.call_count, 0)

    def test_response(self):
        response = MagicMock()
        self.cs.request(response, SType.Call, dict(endpoint="zebra1.run"))
        for i in range(5):
            try:
                ss_msg = self.ss.recv(0.1)
                break
            except:
                pass
        self.ss.send([ss_msg[0], '{"type": "Return", "id": 0, "value": 32}'])
        cothread.Sleep(0.2)
        response.assert_called_once_with(SType.Return, value=32)

    def tearDown(self):
        def log_debug(msg):
            msgs.append(msg)

        msgs = []
        self.ss.log_debug = log_debug
        self.ss.close()
        self.ss = None
        self.assertEqual(msgs, ['Garbage collecting loop',
                                'Loop garbage collected'])
        msgs = []
        self.cs.log_debug = log_debug
        self.cs = None
        self.assertEqual(msgs, ['Garbage collecting loop', 'Stopping loop',
                                'Waiting for loop to finish', 'Loop finished',
                                'Loop garbage collected'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
