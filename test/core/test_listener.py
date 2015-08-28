#!/bin/env dls-python
import unittest
import sys
import os
#import logging
# logging.basicConfig(level=logging.DEBUG)
from mock import MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.listener import HasListeners


class MyListener(HasListeners):

    def __init__(self, name, out):
        super(MyListener, self).__init__(name)
        self.out = out

    def __del__(self):
        self.out.append("Deleted")


class ListenerTest(unittest.TestCase):

    def setUp(self):
        self.out = []
        self.l = MyListener("Listener", self.out)

    def test_one_listener(self):
        cb = MagicMock()
        self.l.add_listener(cb)
        changes = dict(foo=32)
        self.l.notify_listeners(changes)
        cb.assert_called_once_with(changes)
        cb.reset_mock()
        self.l.remove_listener(cb)
        self.l.notify_listeners(dict(bo=3))
        self.assertEqual(cb.call_count, 0)

    def test_listener_del_called_when_out_of_scope(self):
        self.assertEqual(self.out, [])
        self.l = None
        self.assertEqual(self.out, ["Deleted"])

    def cb(self, changes):
        self.out.append(changes)

    def test_listener_del_called_when_has_listeners(self):
        self.assertEqual(self.out, [])
        self.l.add_listener(self.cb)
        changes = dict(foo=32)
        self.l.notify_listeners(changes)
        self.assertEqual(self.out, [changes])
        self.l = None
        self.assertEqual(self.out, [changes, "Deleted"])


if __name__ == '__main__':
    unittest.main(verbosity=2)
