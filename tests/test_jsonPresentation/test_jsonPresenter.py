#!/bin/env dls-python
from pkg_resources import require
from collections import OrderedDict
require("mock")
require("pyzmq")
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
from malcolm.jsonPresentation.jsonPresenter import JsonPresenter


class JsonPresenterTest(unittest.TestCase):

    def setUp(self):
        self.jp = JsonPresenter()

    def test_timeStamp_deserialize(self):
        d = self.jp.deserialize(
            '{"type": "Return", "id": 0, "value": {"timeStamp": {"secondsPastEpoch": 43, "nanoseconds": 200000000, "userTag": 0}}}')
        self.assertEqual(d["type"], "Return")
        self.assertEqual(d["id"], 0)
        self.assertEqual(d["value"], OrderedDict(timeStamp=43.2))

    def test_timeStamp_serialize(self):
        d = OrderedDict()
        d.update(type="Return")
        d.update(id=0)
        d.update(value=dict(timeStamp=43.2))
        s = self.jp.serialize(d)
        expected = '{"type": "Return", "id": 0, "value": {"timeStamp": {"secondsPastEpoch": 43, "nanoseconds": 200000000, "userTag": 0}}}'
        self.assertEqual(s, expected)

if __name__ == '__main__':
    unittest.main(verbosity=2)
