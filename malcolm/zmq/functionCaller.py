from serialize import serialize_method, deserialize
import zmq


class FunctionCaller(object):

    def __init__(self, fe_addr="ipc://frfe.ipc"):
        # Prepare context and sockets
        self.fe_addr = fe_addr
        self.setup()

    def setup(self):
        self.socket = zmq.Context().socket(zmq.REQ)
        self.socket.connect(self.fe_addr)

    def call(self, method, **kwargs):
        s = serialize_method(method, **kwargs)
        self.socket.send(s)
        reply = self.socket.recv()
        d = deserialize(reply)
        if d["name"] == "return":
            return d["ret"]
        elif d["name"] == "error":
            raise eval(d["type"])(d["message"])
        else:
            raise KeyError("Don't know what to do with {}".format(d))
