#!/bin/env dls-python
from pkg_resources import require
from collections import OrderedDict
require("mock")
require("pyzmq")
require("cothread")
import unittest
import sys
import os
import weakref
import cothread

import logging
#logging.basicConfig()
logging.basicConfig(level=logging.DEBUG)
from mock import patch, MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqComms.zmqClientSocket import ZmqClientSocket
from malcolm.zmqComms.zmqServerSocket import ZmqServerSocket
from malcolm.core.serialize import SType
from malcolm.core.socket import ServerSocket
from malcolm.core.loop import LState


class ZmqServerSocketProcTest(unittest.TestCase):

    def setUp(self):
        self.inq = cothread.EventQueue()
        self.ss = ZmqServerSocket("ipc://frfe.ipc", self.inq)
        self.ss.loop_run()
        self.cs = ZmqClientSocket("ipc://frfe.ipc", timeout=1)
        self.cs.open(self.cs.name)

    def test_gc(self):
        pass

    def test_send_func(self):
        #self.cs.send(['{"type": "Call", "id": 0, "endpoint": "zebra.run"}'])
        cothread.Yield()
        #typ, args, kwargs = self.inq.Wait(timeout=0.1)
        #self.assertEqual(typ, SType.Call)
        #self.assertEqual(kwargs, OrderedDict(endpoint="zebra.run"))
        #send = args[0]
        #send(SType.Return, value=99)
        #cs_msg = self.cs.recv()
        #self.assertEqual(cs_msg[0], '{"type": "Return", "id": 0, "value": 99}')

    def tearDown(self):
        self.cs.close()
        self.cs._loop_state = LState.Stopped
        self.cs = None
        print 3
        
        msgs = []

        def log_debug(msg):
            msgs.append(msg)

        self.ss.log_debug = log_debug
        print 1
        self.ss = None
        print 2
        #cothread.Yield()
        cothread.Sleep(1)
        self.assertEqual(msgs, ['Garbage collecting loop', 'Stopping loop',
                                'Waiting for loop to finish', 'Loop finished',
                                'Loop garbage collected'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
