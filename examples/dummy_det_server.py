#!/bin/env dls-python
import sys
sys.path.append(
    "/home/tmc43/common/python/cothread/prefix/lib/python2.7/site-packages")
from pkg_resources import require
require("pyzmq==13.1.0")
require("cothread==2.14b1")
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from malcolm.imalcolm import IMalcolmServer

# Test
ims = IMalcolmServer()
ims.createDummyDet(name="det")
ims.interact()
