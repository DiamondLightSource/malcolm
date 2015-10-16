#!/bin/env dls-python
import unittest
import sys
import os
import logging
import cothread
from mock import MagicMock
logging.basicConfig()
# logging.basicConfig(level=logging.DEBUG)
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.directoryService import DirectoryService
from malcolm.core.transport import ServerSocket, SType
from malcolm.core.device import Device
from malcolm.core.method import wrap_method
from malcolm.core.attribute import InstanceAttribute, This


class MockSocket(ServerSocket):

    def send(self, msg, timeout=None):
        """Send the message to the socket"""
        self.out.append(msg)

    def recv(self, timeout=None):
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
        import cothread
        self.inq = cothread.EventQueue()

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


class MockDevice2(Device):
    "Mock thing"
    runcalled = False
    class_attributes = dict(
        child=InstanceAttribute(This, "child device"))

    @wrap_method()
    def run(self):
        self.runcalled = True
        return 32


class DirectoryServiceTest(unittest.TestCase):

    def setUp(self):
        self.ds = DirectoryService(["tst://socket"], "The Process")
        self.ds.run(block=False)
        self.s = self.ds._server_socks["tst://socket"]

    def test_gc(self):
        msgs = []

        def log_debug(msg):
            msgs.append(msg)
        self.ds.log_debug = log_debug
        self.s = None
        self.ds = None
        self.assertEqual(msgs, ['Garbage collecting loop', 'Stopping loop', 'Waiting for loop to finish',
                                "Loop finished", 'Loop garbage collected'])

    def test_update_instance_attributes(self):
        d1 = self.ds.createMockDevice2("MD1")
        self.assertEqual(d1.child, None)
        self.assertEqual(d1.attributes["child"].typ.labels, ("MD1",))
        l = MagicMock()
        d1.add_listener(l, "attributes.child")
        d2 = self.ds.createMockDevice2("MD2")
        self.assertEqual(d2.child, None)
        self.assertEqual(d1.attributes["child"].typ.labels, ("MD1", "MD2"))
        self.assertEqual(d2.attributes["child"].typ.labels, ("MD1", "MD2"))
        l.assert_called_once_with(
            d1.attributes["child"], dict(type=d1.attributes["child"].typ))
        self.assertRaises(
            AssertionError, d1.attributes["child"].update, "MD2ss")
        d1.child = "MD2"
        self.assertEqual(d1.child, d2)
        self.assertEqual(d1.attributes["child"].to_dict()["value"], "MD2")


if __name__ == '__main__':
    unittest.main(verbosity=2)
