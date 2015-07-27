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
from malcolm.zmqComms.zmqProcess import ZmqProcess, CoStream


class MockFunctionCaller(FunctionCaller):

    def setup(self):
        self.socket = MagicMock()


class FunctionCallerTest(unittest.TestCase):

    def setUp(self):
        self.fc = MockFunctionCaller("mydevice")

    def test_call_single_return(self):
        ret = "return val"
        self.fc.socket.recv.return_value = json.dumps(
            dict(type="return", val=ret))
        self.assertEqual(self.fc.call("myfunc", bar="bat"), ret)
        self.fc.socket.send.assert_called_once_with(
            json.dumps(dict(type="call", device="mydevice", method="myfunc", args=dict(bar="bat"))))

    def test_error_call(self):
        self.fc.socket.recv.return_value = json.dumps(
            dict(type="error", name="NameError", message="bad"))
        self.assertRaises(NameError, self.fc.call, "myfunc", bar="bat")
        self.fc.socket.send.assert_called_once_with(
            json.dumps(dict(type="call", device="mydevice", method="myfunc", args=dict(bar="bat"))))

    def test_call_single_get(self):
        ret = "return val"
        self.fc.socket.recv.return_value = json.dumps(
            dict(type="return", val=ret))
        self.assertEqual(self.fc.get("myparam"), ret)
        self.fc.socket.send.assert_called_once_with(
            json.dumps(dict(type="get", device="mydevice", param="myparam")))

    def test_error_get(self):
        self.fc.socket.recv.return_value = json.dumps(
            dict(type="error", name="NameError", message="bad"))
        self.assertRaises(NameError, self.fc.get, "myparam")
        self.fc.socket.send.assert_called_once_with(
            json.dumps(dict(type="get", device="mydevice", param="myparam")))
        

class MiniRouter(ZmqProcess):
    fe_addr = "ipc://frfe.ipc"

    def __init__(self, returnval):
        super(MiniRouter, self).__init__()
        self.returnval = returnval

    def setup(self):
        """Sets up PyZMQ and creates all streams."""
        super(MiniRouter, self).setup()
        self.fe_stream = self.stream(zmq.ROUTER, self.fe_addr, bind=True)
        self.fe_stream.on_recv(self.handle_fe)

    def handle_fe(self, msg):
        clientid, _, data = msg
        if data == "pleasestopnow":
            self.stop()
        else:
            self.fe_stream.send_multipart([clientid, "", self.returnval])


class FunctionCallerProcTest(unittest.TestCase):

    def setUp(self):
        """
        Creates and starts a PongProc process and sets up sockets to
        communicate with it.

        """
        self.context = zmq.Context()

        # make_sock creates and connects a TestSocket that we will use to
        # mimic the Ping process
        self.req_sock = CoStream(zmq.REQ, MiniRouter.fe_addr, bind=False)
        self.fc = FunctionCaller("mydevice", fe_addr=MiniRouter.fe_addr)

    def test_correct_call_return(self):
        ret = "return val"
        self.mr = MiniRouter(json.dumps(dict(type="return", val=ret)))
        self.mr.start()
        self.assertEqual(self.fc.call("myfunc", bar="bat"), ret)

    def test_correct_get_return(self):
        ret = "get val"
        self.mr = MiniRouter(json.dumps(dict(type="return", val=ret)))
        self.mr.start()
        self.assertEqual(self.fc.get("myparam"), ret)

    def tearDown(self):
        """
        Sends a kill message to the pp and waits for the process to terminate.

        """
        # Send a stop message to the prong process and wait until it joins
        self.req_sock.send("pleasestopnow")
        self.mr.join()
        self.req_sock.close()

if __name__ == '__main__':
    unittest.main(verbosity=2)
