#!/bin/env dls-python
from pkg_resources import require
import malcolm
require("mock")
require("cothread")
import unittest
import sys
import os
from enum import Enum
import inspect
#import logging
# logging.basicConfig(level=logging.DEBUG)
from mock import patch, MagicMock
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
from malcolm.core.method import wrap_method, Method
from malcolm.core.attribute import Attribute
from malcolm.core.attributes import Attributes
from traits.api import Int, Float, Undefined

class TState(Enum):
    State1, State2 = range(2)


class MethodTest(unittest.TestCase):

    @wrap_method(TState.State1)
    def f(self, nframes, exposure=0.1):
        "Return total time"
        return nframes * exposure

    @wrap_method(TState.State2, f)
    def g(self, **params):
        "Proxy thing"
        pass

    def setUp(self):
        self.attributes = Attributes(
            nframes=Attribute(Int, "Number of frames"),
            exposure=Attribute(Float, "Detector exposure"),
        )
        self.state = TState.State1

    def test_calling_f(self):
        self.f.describe(self)
        self.assertEqual(self.f(3, 4), 12)

    def test_attribute_description(self):
        methods = Method.describe_methods(self)
        method = methods["f"]
        self.assertEqual(method, self.f)
        self.assertEqual(method.descriptor, "Return total time")
        nframes = method.args["nframes"]
        self.assertEqual(nframes.descriptor, "Number of frames")
        self.assertEqual(nframes.typ, Int)
        self.assertEqual(nframes.value, Undefined)
        self.assertEqual(nframes.tags, ["required"])
        exposure = method.args["exposure"]
        self.assertEqual(exposure.descriptor, "Detector exposure")
        self.assertEqual(exposure.typ, Float)
        self.assertEqual(exposure.value, 0.1)
        self.assertEqual(exposure.tags, [])
        self.assertEqual(method.valid_states, [TState.State1])

    def test_attribute_override_description(self):
        methods = Method.describe_methods(self)
        method = methods["g"]
        self.assertEqual(method, self.g)
        self.assertEqual(method.descriptor, "Proxy thing")
        nframes = method.args["nframes"]
        self.assertEqual(nframes.descriptor, "Number of frames")
        self.assertEqual(nframes.typ, Int)
        self.assertEqual(nframes.value, Undefined)
        self.assertEqual(nframes.tags, ["required"])
        exposure = method.args["exposure"]
        self.assertEqual(exposure.descriptor, "Detector exposure")
        self.assertEqual(exposure.typ, Float)
        self.assertEqual(exposure.value, 0.1)
        self.assertEqual(exposure.tags, [])
        self.assertEqual(method.valid_states, [TState.State2])

if __name__ == '__main__':
    unittest.main(verbosity=2)
