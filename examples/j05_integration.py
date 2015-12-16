#!/bin/env dls-python
import os
import subprocess
#os.environ["EPICS_CA_SERVER_PORT"] = "6064"
#ioc = "/dls_sw/work/R3.14.12.3/support/mapping/iocs/TS-EA-IOC-02/bin/linux-x86_64/stTS-EA-IOC-02.sh"
#ioc = subprocess.Popen([ioc, "512", "512"], stdin=subprocess.PIPE)

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
pre = "BL05J-TS-CAM-01:"
ims.createSimDetectorDriver("det:det", pre + "CAM:")
ims.createPositionPlugin("det:pos", pre + "POS:")
ims.createHdf5Writer("det:hdf5", pre + "HDF5:")
ims.createSimDetector("det", "det:det", "det:pos", "det:hdf5")
ims.createProgScan("prog", "BL05J-EA-SM-01:SCAN:")
ims.createArpesScan("arpes", "det", "prog")
ims.interact()
