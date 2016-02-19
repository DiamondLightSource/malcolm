#!/bin/env dls-python
import os
import sys
sys.path.append(
    "/home/tmc43/common/python/cothread/prefix/lib/python2.7/site-packages")
print sys.path
from pkg_resources import require
require("pyzmq==13.1.0")
require("cothread==2.14b1")
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from malcolm.imalcolm.client import make_client
from malcolm import gui

# Test
self = make_client()
self.run(block=False)
arpes = self.get_device("arpes")
gui(arpes)
