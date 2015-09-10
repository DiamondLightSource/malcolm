#!/bin/env dls-python
import unittest
import sys
import os
import logging
import cothread
from mock import MagicMock
from malcolm.core.serialize import SType
from malcolm.core.method import wrap_method
# logging.basicConfig()
# logging.basicConfig(level=logging.DEBUG)
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.process import Process
from malcolm.core.socket import ServerSocket
from malcolm.core.device import Device


class MockSocket(ServerSocket):

    def send(self, msg):
        """Send the message to the socket"""
        self.out.append(msg)

    def recv(self):
        """Co-operatively block until received"""
        return self.inq.Wait()

    def serialize(self, typ, kwargs):
        """Serialize the arguments to a string that can be sent to the socket
        """
        return (typ, kwargs)

    def deserialize(self, msg):
        """Deserialize the string to
        (typ, kwargs)"""
        return msg

    def open(self, address):
        """Open the socket on the given address"""
        self.out = []
        self.send = None
        self.inq = self.cothread.EventQueue()

    def close(self):
        """Close the socket"""
        self.inq.close()

    def make_send_function(self, kwargs):
        """Make a send function that will call send with suitable arguments
        to be used as a response function"""
        if not self.send:
            self.send = MagicMock()
        return self.send

MockSocket.register("tst://")


class MockDevice(Device):
    "Mock thing"
    runcalled = False

    @wrap_method()
    def run(self):
        self.runcalled = True
        return 32


class AttributeTest(unittest.TestCase):

    def setUp(self):
        self.p = Process(["tst://socket"], "The Process")
        self.p.run(block=False)
        self.s = self.p._server_socks["tst://socket"]

    def test_gc(self):
        msgs = []

        def log_debug(msg):
            msgs.append(msg)
        self.p.log_debug = log_debug
        self.s = None
        self.p = None
        self.assertEqual(msgs, ['Garbage collecting loop', 'Stopping loop', 'Waiting for loop to finish', 
                                'Confirming loop stopped', 'Loop garbage collected'])

    def test_create_device(self):
        self.assertEqual(self.p.device_types, [
                         'Device', 'RunnableDevice', 'PausableDevice', 'DummyDet', 'DeviceClient', 'Process', 'MockDevice'])
        d = self.p.create_MockDevice("MD")
        self.assertIsInstance(d, MockDevice)
        self.assertEqual(d.name, "MD")

    def test_call_on_device(self):
        d = self.p.create_MockDevice("MD")
        self.s.inq.Signal((SType.Call, dict(endpoint="MD.methods.run")))
        self.assertEqual(d.runcalled, False)
        # Yield to let socket recv
        cothread.Yield()
        # Yield to let process retrieve from inq
        cothread.Yield()
        # Yield to let spawned do_func run
        cothread.Yield()
        self.assertEqual(d.runcalled, True)
        self.assertIsNot(self.s.send, None)
        self.s.send.assert_called_once_with(SType.Return, 32)

    def test_get_on_device(self):
        d = self.p.create_MockDevice("MD")
        self.s.inq.Signal((SType.Get, dict(endpoint="MD.methods")))
        # Yield to let socket recv
        cothread.Yield()
        # Yield to let process retrieve from inq
        cothread.Yield()
        self.assertIsNot(self.s.send, None)
        self.s.send.assert_called_once_with(SType.Return, d.methods)

    def test_subscribe_on_device(self):
        d = self.p.create_MockDevice("MD")
        self.s.inq.Signal((SType.Subscribe, dict(endpoint="MD.methods.run")))
        # Yield to let socket recv
        cothread.Yield()
        # Yield to let process retrieve from inq
        cothread.Yield()
        d.notify_listeners({"methods.run.descriptor": "new desc"})
        # Yield to let subscription send back out
        cothread.Yield()
        self.assertIsNot(self.s.send, None)
        self.s.send.assert_called_once_with(
            SType.Value, d.methods["run"], changes=dict(descriptor="new desc"))
        self.s.send.reset_mock()
        self.s.inq.Signal((SType.Unsubscribe, {}))
        # Yield to let socket recv
        cothread.Yield()
        # Yield to let process retrieve from inq
        cothread.Yield()
        self.s.send.assert_called_once_with(
            SType.Return)
        # Yield to let subscription remove itself from parent
        cothread.Yield()

if __name__ == '__main__':
    unittest.main(verbosity=2)
