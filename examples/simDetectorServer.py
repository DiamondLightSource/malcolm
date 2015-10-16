#!/bin/env dls-python
import sys
sys.path.append(
    "/home/tmc43/common/python/cothread/prefix/lib/python2.7/site-packages")
from pkg_resources import require
require("pyzmq==13.1.0")
require("cothread==2.14b1")
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from malcolm.iMalcolm import IMalcolmServer

# Test
ims = IMalcolmServer()
from socket import gethostname
hostname = gethostname().split(".")[0]
pre = "{}-AD-SIM-01:".format(hostname)
#ims.createSimDetector("det:det", pre + "CAM:")
#ims.createPositionPlugin("det:pos", pre + "POS:")
#ims.createHdf5Writer("det:hdf5", pre + "HDF5:")
#ims.createSimDetectorPersonality("det", "det:det", "det:pos", "det:hdf5")
ims.interact()
