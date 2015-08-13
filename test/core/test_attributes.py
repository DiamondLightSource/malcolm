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
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.attributes import Attributes
from malcolm.core.attribute import Attribute
from malcolm.core.traitsapi import Int, Float, Undefined


class AttributeTest(unittest.TestCase):

    def setUp(self):
        self.a = Attributes()
        self.a.add_attributes(
            nframes=Attribute(Int, "Number of frames"),
            exposure=Attribute(Float, "Detector exposure"),
        )

    def test_attr_instance_correct_type(self):
        self.assertIsInstance(self.a.nframes, Attribute)

    def test_setting_attr(self):
        self.a.nframes.value = 32
        self.assertEqual(self.a["nframes"].value, 32)
        self.assertEqual(self.a.nframes.value, 32)

    def test_setting_undefined_attr(self):
        def set():
            self.a.nframes2.value = 32
        self.assertRaises(KeyError, set)

    def test_undefined_getattr(self):
        self.assertEqual(self.a.nframes.value, Undefined)

if __name__ == '__main__':
    unittest.main(verbosity=2)
