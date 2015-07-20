from serialize import serialize_call, deserialize
import zmq
import logging
log = logging.getLogger(__name__)

class FunctionCaller(object):

    def __init__(self, device, fe_addr="ipc://frfe.ipc"):
        # Prepare context and sockets
        self.fe_addr = fe_addr
        self.device = device
        self.setup()

    def setup(self):
        self.socket = zmq.Context().socket(zmq.REQ)
        self.socket.connect(self.fe_addr)

    def call(self, method, **kwargs):
        s = serialize_call(self.device, method, **kwargs)
        log.debug("send {}".format(s))
        self.socket.send(s)
        reply = self.socket.recv()
        log.debug("recv {}".format(reply))
        d = deserialize(reply)
        if d["type"] == "return":
            return d["val"]
        elif d["type"] == "error":
            raise eval(d["name"])(d["message"])
        else:
            raise KeyError("Don't know what to do with {}".format(d))
