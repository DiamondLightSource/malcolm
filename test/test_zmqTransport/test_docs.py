#!/bin/env dls-python
from pkg_resources import require

require("mock")
require("pyzmq")
import unittest
from mock import MagicMock, patch
import sys
import os
import json
import zmq
import time
import cothread

import logging
logging.basicConfig()
# level=logging.DEBUG)
# format="%(asctime)s;%(levelname)s;%(message)s")
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.runnableDevice import RunnableDevice, DState
from malcolm.core.attribute import Attribute
from malcolm.zmqTransport.zmqClientSocket import ZmqClientSocket
from malcolm.core.deviceClient import DeviceClient
from collections import OrderedDict
import difflib
from malcolm.zmqTransport.zmqServerSocket import ZmqServerSocket
from malcolm.core.loop import LState
from malcolm.core.transport import SType
from malcolm.core.method import wrap_method
from malcolm.core.directoryService import DirectoryService


class DummyClientSocket(ZmqClientSocket):

    def make_zmq_sock(self, address):
        return MagicMock()


class DummyServerSocket(ZmqServerSocket):

    def make_zmq_sock(self, address):
        return MagicMock()


class DummyZebra(RunnableDevice):

    def __init__(self, name):
        super(DummyZebra, self).__init__(name)

    def add_all_attributes(self):
        RunnableDevice.add_all_attributes(self)
        self.add_attributes(
            PC_BIT_CAP=Attribute(int, "Which encoders to capture"),
            PC_TSPRE=Attribute(str, "What time units for capture"),
            CONNECTED=Attribute(int, "Is zebra connected"),
        )

    @wrap_method()
    def assert_valid(self, PC_BIT_CAP, PC_TSPRE):
        "Check parameters are valid"

    def do_abort(self):
        pass

    def do_abortsta(self):
        pass

    def do_config(self):
        pass

    def do_configsta(self):
        pass

    def do_reset(self):
        pass

    def do_resetsta(self):
        pass

    def do_run(self):
        pass

    def do_runsta(self):
        pass


class ZmqDocsTest(unittest.TestCase):

    def setUp(self):
        self.cs = DummyClientSocket("cs", "csaddr")
        self.cs.open(self.cs.address)
        self.ss = DummyServerSocket("ss", "ssaddr", None)
        self.ss.open(self.ss.address)
        self.zebraClient = DeviceClient("zebra1", self.cs)
        self.dsClient = DeviceClient("DirectoryService", self.cs)
        self.ds = DirectoryService([])
        self.zebra = self.ds.create_device(DummyZebra, "zebra1")

    def assertDocExample(self, fname, actual):
        expected = open(os.path.join(os.path.dirname(
            __file__), "..", "..", "docs", "comms", "zmqExamples", fname)).read()
        prettyactual = json.dumps(
            json.loads(actual, object_pairs_hook=OrderedDict), indent=2)
        header = ".. code-block:: javascript\n\n"
        docactual = header + \
            "\n".join("    " + x for x in prettyactual.splitlines()) + "\n"
        if expected != docactual:
            print
            print docactual
            message = ''.join(difflib.unified_diff(
                expected.splitlines(True), docactual.splitlines(True)))
            self.fail("Output doesn't match docs: %s\n" % message)

    @patch("malcolm.core.deviceClient.ValueQueue")
    def test_call_zebra_configure(self, mock_vq):
        self.zebraClient.do_call("configure", PC_BIT_CAP=1, PC_TSPRE="ms")
        call_args = self.cs.sock.send_multipart.call_args
        self.assertDocExample("call_zebra_configure", call_args[0][0][0])

    @patch("malcolm.core.deviceClient.ValueQueue")
    def test_get_DirectoryService_Device_instances(self, mock_vq):
        self.dsClient.do_get("attributes.Device_instances.value")
        call_args = self.cs.sock.send_multipart.call_args
        self.assertDocExample(
            "get_DirectoryService_Device_instances", call_args[0][0][0])

    @patch("malcolm.core.deviceClient.ValueQueue")
    def test_get_zebra_status(self, mock_vq):
        self.zebraClient.do_get("stateMachine")
        call_args = self.cs.sock.send_multipart.call_args
        self.assertDocExample("get_zebra_status", call_args[0][0][0])

    @patch("malcolm.core.deviceClient.ValueQueue")
    def test_get_zebra(self, mock_vq):
        self.zebraClient.do_get()
        call_args = self.cs.sock.send_multipart.call_args
        self.assertDocExample("get_zebra", call_args[0][0][0])

    def test_subscribe_zebra_status(self):
        el = self.zebraClient.do_subscribe(lambda: None, "stateMachine")
        call_args = self.cs.sock.send_multipart.call_args
        self.assertDocExample("subscribe_zebra_status", call_args[0][0][0])
        el.inq = MagicMock()
        el.loop_stop()
        el._loop_state = LState.Stopped
        call_args = self.cs.sock.send_multipart.call_args
        self.assertDocExample("unsubscribe_zebra_status", call_args[0][0][0])

    def test_value_zebra_status(self):
        send = self.ss.make_send_function(dict(zmq_id=1, id=0))
        sub = self.ds.do_subscribe(send, "zebra1.stateMachine")
        sub.inq = MagicMock()
        self.zebra.stateMachine.update(
            state=DState.Configuring, message="Configuring...", timeStamp=14419090000.2)
        send(*sub.inq.Signal.call_args[0][0][1])
        call_args = self.ss.sock.send_multipart.call_args
        self.assertDocExample("value_zebra_status", call_args[0][0][1])

    def test_return_zebra_status(self):
        send = self.ss.make_send_function(dict(zmq_id=1, id=0))
        self.zebra.stateMachine.update(
            state=DState.Configuring, message="Configuring...", timeStamp=14419090000.2)
        self.ds.do_get(send, "zebra1.stateMachine")
        call_args = self.ss.sock.send_multipart.call_args
        self.assertDocExample("return_zebra_status", call_args[0][0][1])

    def test_return_zebra(self):
        send = self.ss.make_send_function(dict(zmq_id=1, id=0))
        self.zebra.stateMachine.update(
            state=DState.Configuring, message="Configuring...", timeStamp=14419090000.2)
        self.ds.do_get(send, "zebra1")
        call_args = self.ss.sock.send_multipart.call_args
        self.assertDocExample("return_zebra", call_args[0][0][1])

    def test_return_DirectoryService_Device_instances(self):
        send = self.ss.make_send_function(dict(zmq_id=1, id=0))
        self.ds.do_get(
            send, "DirectoryService.attributes.Device_instances.value")
        call_args = self.ss.sock.send_multipart.call_args
        self.assertDocExample(
            "return_DirectoryService_Device_instances", call_args[0][0][1])

    # Mock out EventLoop so we don't log error
    @patch("malcolm.core.process.EventLoop")
    def test_error_foo(self, el):
        send = self.ss.make_send_function(dict(zmq_id=1, id=0))
        try:
            self.ds.do_get(send, "foo.stateMachine")
        except Exception, e:
            self.ds.do_error(e, send)
        call_args = self.ss.sock.send_multipart.call_args
        self.assertDocExample("error_foo", call_args[0][0][1])

if __name__ == '__main__':
    unittest.main(verbosity=2)
