from malcolm.zmqComms.functionCaller import FunctionCaller
import functools

class DeviceClient(object):

    def __init__(self, device, addr):
        self.addr = addr
        self.fc = FunctionCaller(device, addr)
        self.structure = self.fc.get()
        for mname, mdata in self.structure["methods"].items():
            f = functools.partial(FunctionCaller(device, addr).call, mname)
            f.__doc__ = mdata["descriptor"]
            f.func_name = str(mname)
            setattr(self, mname, f)
