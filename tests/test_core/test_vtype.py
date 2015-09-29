#!/bin/env dls-python
import unittest
import sys
import os
import logging
# logging.basicConfig(level=logging.DEBUG)
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.vtype import VDouble, VInt, VFloat, VType, VString, VStringArray, VEnum, VNumber


class AttributeTest(unittest.TestCase):

    def test_all_subclasses(self):
        self.assertIn(VDouble, VType.subclasses().values())
        self.assertNotIn(VNumber, VType.subclasses().values())

    def test_vfloat_from_int(self):
        self.assertEqual(VFloat().validate(32), 32.0)

    def test_vint_from_double_no_decimal(self):
        self.assertEqual(VInt().validate(32.0), 32)

    def test_vint_from_double_decimal(self):
        self.assertRaises(AssertionError, VInt().validate, 32.4)

    def test_vstring_from_float(self):
        self.assertEqual(VString().validate(32.0), "32.0")

    def test_vstring_from_int(self):
        self.assertEqual(VString().validate(32), "32")

    def test_vstringarray_from_int_tuple(self):
        self.assertEqual(VStringArray().validate(range(3)), ["0", "1", "2"])

    def test_vstringarray_from_string_fails(self):
        self.assertRaises(AssertionError, VStringArray().validate, "thing")
        self.assertRaises(AssertionError, VStringArray().validate, u"thing")

    def test_sting_venum(self):
        self.assertRaises(AssertionError, VEnum, range(3))
        v = VEnum("a,b,c")
        self.assertEqual(v.validate("a"), "a")
        self.assertEqual(v.validate(u"a"), "a")
        self.assertEqual(v.validate(2), "c")
        self.assertRaises(AssertionError, v.validate, "x")
        self.assertRaises(AssertionError, v.validate, 3)

if __name__ == '__main__':
    unittest.main(verbosity=2)
