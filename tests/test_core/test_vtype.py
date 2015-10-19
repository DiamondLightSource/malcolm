#!/bin/env dls-python
import unittest
import sys
import os
import logging
import numpy
# logging.basicConfig(level=logging.DEBUG)
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.vtype import VDouble, VInt, VFloat, VType, VString, VStringArray, VEnum, VNumber,\
    VTable, VFloatArray, VDoubleArray


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
        self.assertEqual(v.validate(2), 2)
        self.assertRaises(AssertionError, v.validate, "x")
        self.assertRaises(AssertionError, v.validate, 3)

    def test_vfloatarray_from_pylist(self):
        v = VFloatArray()
        l = [1.2, 33]
        nparray = v.validate(l)
        self.assertEqual(nparray.dtype.type, numpy.float32)

    def test_vdoublearray_from_numpy(self):
        v = VDoubleArray()
        l = numpy.array([1.2, 33], dtype=numpy.float64)
        nparray = v.validate(l)
        self.assertEqual(nparray.dtype.type, numpy.float64)

    def test_wrong_numpy_dtype(self):
        v = VDoubleArray()
        l = numpy.array([1.2, 33], dtype=numpy.float32)
        self.assertRaises(AssertionError, v.validate, l)

    def test_vtable(self):
        data = [
            ("Name", VString, ["A", "B", "C"]),
            ("Index", VInt, [1, 2, 3]),
            ("Value", VDouble, [3.14, 1.25, -0.1]),
        ]
        out = VTable().validate(data)
        self.assertEqual(len(out), len(data))
        for i, o in zip(data, out):
            self.assertEqual(i[0], o[0])  # name
            self.assertEqual(i[1], o[1])  # type
            if i[1] == VString:
                self.assertEqual(type(o[2][0]), str)
            else:
                self.assertEqual(i[1]().numpy_type(), o[2].dtype.type)

    def test_ragged_vtable(self):
        data = [
            ("Long", VString, ["A", "B", "C"]),
            ("Short", VInt, [1, 2]),
        ]
        self.assertRaises(AssertionError, VTable().validate, data)


if __name__ == '__main__':
    unittest.main(verbosity=2)
