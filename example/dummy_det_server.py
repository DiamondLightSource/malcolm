#!/bin/env dls-python
import sys, os
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from pkg_resources import require
require("cothread==2.12")
require("pyzmq==13.1.0")
from malcolm.devices.dummyDet import DummyDet
from malcolm.zmqComms.deviceWrapper import DeviceWrapper
from malcolm.zmqComms.functionRouter import FunctionRouter

# start the device wrapper
port = 5600
dw = DeviceWrapper("det", DummyDet)
dw.start()
fr = FunctionRouter(fe_addr="tcp://127.0.0.1:{}".format(port))
fr.run()
