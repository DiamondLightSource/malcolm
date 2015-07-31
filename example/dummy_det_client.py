#!/bin/env dls-python
import sys
import os
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from pkg_resources import require
require("pyzmq==13.1.0")
require("cothread==2.12")
from malcolm.client import DeviceClient

# start the device wrapper
port = 5600
det = DeviceClient("det", "tcp://127.0.0.1:{}".format(port))
print "Try running det.configure(exposure=0.2, nframes=10)"
