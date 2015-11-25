#!/bin/env dls-python
import os
import signal
import subprocess
simserver = "/home/tmc43/common/zebra2-server/simserver"
s = subprocess.Popen(simserver, stdin=subprocess.PIPE)

import sys
sys.path.append(
    "/home/tmc43/common/python/cothread/prefix/lib/python2.7/site-packages")
from pkg_resources import require
require("pyzmq==13.1.0")
require("cothread==2.14b1")
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from malcolm.imalcolm import IMalcolmServer
from malcolm.devices.zebra2.zebra2 import Zebra2

# Test
try:
    ims = IMalcolmServer()
    ims.create_device(Zebra2, "Z", hostname="localhost", port=8888)
    ims.interact()
finally:
    try:
        os.killpg(os.getpgid(s.pid), signal.SIGINT)
    except:
        pass
