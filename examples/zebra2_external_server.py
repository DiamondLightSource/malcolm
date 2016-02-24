#!/bin/env dls-python
import os
import sys
sys.path.append(
    "/home/tmc43/common/python/cothread/prefix/lib/python2.7/site-packages")
sys.path.append(
    "/dls_sw/work/tools/RHEL6-x86_64/ws4py/prefix/lib/python2.7/site-packages/ws4py-0.3.4-py2.7.egg")
from pkg_resources import require
require("pyzmq==13.1.0")
require("cothread==2.14b1")
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from malcolm.imalcolm import IMalcolmServer
from malcolm.devices.zebra2.zebra2 import Zebra2

# Test
ims = IMalcolmServer(prefix="ws://")
ims.create_device(Zebra2, "Z", hostname="172.23.252.201", port=8888)
ims.interact()
