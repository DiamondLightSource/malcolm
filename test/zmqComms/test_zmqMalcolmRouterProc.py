#!/bin/env dls-python
from pkg_resources import require
from test.zmqComms.support import make_sock
require("mock")
require("pyzmq")
import unittest
import sys
import os
import json
import zmq
import time

import logging
logging.basicConfig()
#logging.basicConfig(level=logging.DEBUG)
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqComms.zmqMalcolmRouter import ZmqMalcolmRouter


class ZmqMalcolmRouterProcTest(unittest.TestCase):

    def setUp(self):
        self.context = zmq.Context()

        # make_sock creates and connects a TestSocket that we will use to
        # mimic the Ping process
        fe_addr = "ipc://frfe.ipc"
        be_addr = "ipc://frbe.ipc"
        for x in sys.modules.keys():
            if x.startswith("cothread"):
                del sys.modules[x]
        self.caller_sock = make_sock(
            self.context, zmq.DEALER, fe_addr, bind=False)
        self.dev_sock = make_sock(
            self.context, zmq.DEALER, be_addr, bind=False)
        self.fr = ZmqMalcolmRouter(fe_addr=fe_addr, be_addr=be_addr, timeout=1)
        self.fr.start()

    def test_single_provider_callsback(self):
        ready = json.dumps(
            dict(type="Ready", device="zebra1"))
        self.dev_sock.send_multipart(["malcolm", ready])
        # give it time to register zebra
        time.sleep(0.2)
        request = json.dumps(dict(id=0, type="Call", method="zebra1.do"))
        self.caller_sock.send(request)
        at_device = self.dev_sock.recv_multipart()
        self.assertEqual(at_device[1], request)
        # send a function response
        response = json.dumps(dict(id=0, type="Return", name=None))
        self.dev_sock.send_multipart([at_device[0], response])
        at_req = self.caller_sock.recv()
        self.assertEqual(at_req, response)

    def test_single_provider_getsback(self):
        ready = json.dumps(
            dict(type="Ready", device="zebra1"))
        self.dev_sock.send_multipart(["malcolm", ready])
        # give it time to register zebra
        time.sleep(0.2)
        request = json.dumps(dict(id=0, type="Get", param="zebra1.status"))
        self.caller_sock.send(request)
        at_device = self.dev_sock.recv_multipart()
        self.assertEqual(at_device[1], request)
        # send a function response
        response = json.dumps(
            dict(id=0, type="Return", val=dict(message="Message", percent=54.3)))
        self.dev_sock.send_multipart([at_device[0], response])
        at_req = self.caller_sock.recv()
        self.assertEqual(at_req, response)

    def tearDown(self):
        # Send a stop message to the process and wait until it joins
        self.caller_sock.send(
            json.dumps(dict(id=-1, type="Call", method="malcolm.pleasestopnow")))
        self.fr.join()
        self.caller_sock.close()
        self.dev_sock.close()

if __name__ == '__main__':
    unittest.main(verbosity=2)
