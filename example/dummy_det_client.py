#!/bin/env dls-python
import sys, os
# Module import
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from pkg_resources import require
require("pyzmq==13.1.0")
from malcolm.zmqComms.functionCaller import FunctionCaller

# start the device wrapper
port = 5600
fc = FunctionCaller("det", fe_addr="tcp://127.0.0.1:{}".format(port))
