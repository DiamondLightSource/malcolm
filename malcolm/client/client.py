from malcolm.zmqComms.functionCaller import FunctionCaller
import functools

class DeviceClient(object):

    def __init__(self, device, addr):
        self._fc = FunctionCaller(device, addr)
        self._fc.run(block=False)
        structure = self._fc.get()
        for mname, mdata in structure["methods"].items():
            f = functools.partial(self._fc.call, mname)
            f.__doc__ = mdata["descriptor"]
            f.func_name = str(mname)
            setattr(self, mname, f)

