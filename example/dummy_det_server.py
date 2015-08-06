#!/bin/env dls-python
import sys
import os
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from pkg_resources import require
require("cothread==2.12")
require("pyzmq==13.1.0")
from malcolm.devices.dummyDet import DummyDet
from malcolm.zmqComms.zmqDeviceWrapper import ZmqDeviceWrapper
from malcolm.zmqComms.zmqMalcolmRouter import ZmqMalcolmRouter
import logging
logging.basicConfig(level=logging.INFO)

# start the device wrapper
port = 5600
dw = ZmqDeviceWrapper("det", DummyDet)
dw.start()
mr = ZmqMalcolmRouter(fe_addr="tcp://0.0.0.0:{}".format(port))
mr.run()
