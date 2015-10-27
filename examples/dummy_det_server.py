#!/bin/env dls-python
import sys
sys.path.append(
    "/home/tmc43/common/python/cothread/prefix/lib/python2.7/site-packages")
sys.path.append(
    "/dls_sw/work/tools/RHEL6-x86_64/ws4py/prefix/lib/python2.7/site-packages/ws4py-0.3.4-py2.7.egg")
from pkg_resources import require
require("pyzmq==13.1.0")
require("cothread==2.14b1")
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from malcolm.imalcolm import IMalcolmServer

# Test
ims = IMalcolmServer(prefix="ws://")
ims.createDummyDet(name="det")
ims.interact()
