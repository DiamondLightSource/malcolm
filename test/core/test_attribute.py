#!/bin/env dls-python
from pkg_resources import require
require("mock")
import unittest
import sys
import os
#import logging
# logging.basicConfig(level=logging.DEBUG)
from mock import patch, MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from malcolm.core.attribute import Attributes, Attribute


class AttributeTest(unittest.TestCase):

    def setUp(self):
        attributes = dict(
            nframes=(int, "Number of frames"),
            exposure=(float, "Detector exposure"),
        )
        self.a = Attributes(attributes)

    def test_attr_instance_correct_type(self):
        self.assertIsInstance(self.a.attributes["nframes"], Attribute)

    def test_setting_attr(self):
        self.a.nframes = 32
        self.assertEqual(self.a.attributes["nframes"].value, 32)
        self.assertEqual(self.a.nframes, 32)

    def test_setting_undefined_attr(self):
        def set():
            self.a.nframes2 = 32
        self.assertRaises(KeyError, set)

    def test_undefined_getattr(self):
        self.assertEqual(self.a.nframes, None)

if __name__ == '__main__':
    unittest.main(verbosity=2)
