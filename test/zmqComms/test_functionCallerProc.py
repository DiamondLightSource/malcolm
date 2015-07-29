#!/bin/env dls-python
from pkg_resources import require
require("mock")
require("pyzmq")
import unittest
import sys
import os
import multiprocessing
import json
import zmq
import time

#import logging
# logging.basicConfig(level=logging.DEBUG)
from mock import patch, MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.zmqComms.functionCaller import FunctionCaller
from malcolm.zmqComms.zmqProcess import CoStream, ZmqProcess


class MiniRouter(ZmqProcess):
    fe_addr = "ipc://frfe.ipc"

    def __init__(self, returnval, timeout=None):
        super(MiniRouter, self).__init__(timeout)
        self.returnval = returnval

    def setup(self):
        """Sets up PyZMQ and creates all streams."""
        super(MiniRouter, self).setup()
        self.fe_stream = self.stream(zmq.ROUTER, self.fe_addr, bind=True)
        self.fe_stream.on_recv(self.handle_fe)

    def handle_fe(self, msg):
        clientid, data = msg
        if data == "pleasestopnow":
            #print "MiniRouter: stopping"
            self.stop()
        else:
            _id = json.loads(data)["id"]
            returnval = json.dumps(
                dict(id=_id, type="return", val=self.returnval))
            #print "MiniRouter: returning {}".format([clientid, returnval])
            self.fe_stream.send_multipart([clientid, returnval])


class FunctionCallerProcTest(unittest.TestCase):

    def setUp(self):
        """
        Creates and starts a PongProc process and sets up sockets to
        communicate with it.

        """
        self.context = zmq.Context()
        self.fc = FunctionCaller(
            "mydevice", fe_addr=MiniRouter.fe_addr, timeout=1)
        self.req_sock = CoStream(
            self.context, zmq.DEALER, MiniRouter.fe_addr, bind=False, timeout=1)

    def test_minirouter(self):
        self.fc.setup()
        ret = "minireturn val"
        self.mr = MiniRouter(ret, timeout=1)
        self.mr.start()
        for i in range(10):
            self.fc.fe_stream.send(json.dumps(dict(id=i)))
            expected = [json.dumps(dict(id=i, type="return", val=ret))]
            self.assertEquals(self.fc.fe_stream.recv_multipart(), expected)

    def test_correct_call_return(self):
        ret = "return val"
        self.mr = MiniRouter(ret, timeout=1)
        self.mr.start()
        # Mustn't run until after we've started multiprocessing otherwise
        # cothread will spawn matching tasks in both processes...
        self.fc.run(block=False)
        self.assertEqual(self.fc.call("myfunc", bar="bat"), ret)
        self.assertEqual(self.fc.call("myfunc", bar="bat"), ret)
        self.assertEqual(self.fc.call("myfunc", bar="bat"), ret)

    def test_correct_get_return(self):
        ret = "get val"
        self.mr = MiniRouter(ret, timeout=1)
        self.mr.start()
        # Mustn't run until after we've started multiprocessing otherwise
        # cothread will spawn matching tasks in both processes...
        self.fc.run(block=False)
        self.assertEqual(self.fc.get("myparam"), ret)
        self.assertEqual(self.fc.get("myparam"), ret)
        self.assertEqual(self.fc.get("myparam"), ret)

    def tearDown(self):
        """
        Sends a kill message to the pp and waits for the process to terminate.

        """
        # Send a stop message to the prong process and wait until it joins
        self.req_sock.send("pleasestopnow")
        self.mr.join()
        self.req_sock.close()
        self.fc.wait_loops()

if __name__ == '__main__':
    unittest.main(verbosity=2)
