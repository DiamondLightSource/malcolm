from malcolm.zmqComms.functionCaller import FunctionCaller
import functools

class DeviceClient(object):

    def __init__(self, device, addr):
        self._fc = FunctionCaller(device, addr)
        self._fc.run(block=False)
        structure = self._fc.get()
        for mname, mdata in structure["methods"].items():
            f = functools.partial(self.do_call, mname)
            f.__doc__ = mdata["descriptor"]
            f.func_name = str(mname)
            setattr(self, mname, f)

    def do_call(self, method, **kwargs):
        try:
            for status in self._fc.calliter(method, **kwargs):
                if status:
                    state = status["state"]["choices"][status["state"]["index"]]
                    print "{}: {}".format(state, status["message"])
        except KeyboardInterrupt:
            self.abort()

    @property
    def status(self):
        return self._fc.get("status")
    
    @property
    def state(self):
        status = self.status
        state = status["state"]["choices"][status["state"]["index"]]
        return str(state)