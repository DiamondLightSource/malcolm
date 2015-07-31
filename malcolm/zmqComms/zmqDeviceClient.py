from malcolm.zmqComms.zmqSerialize import serialize_call, serialize_get, \
    deserialize
from zmqProcess import ZmqProcess
import zmq
import logging
log = logging.getLogger(__name__)


class ZmqDeviceClient(ZmqProcess):

    def __init__(self, device, fe_addr="ipc://frfe.ipc", timeout=None):
        super(ZmqDeviceClient, self).__init__(timeout)
        # Prepare context and sockets
        self.fe_addr = fe_addr
        self.device = device
        self.id = 0
        # map id -> cothread EventQueue
        self.queue = {}

    def setup(self):
        super(ZmqDeviceClient, self).setup()
        self.fe_stream = self.stream(zmq.DEALER, self.fe_addr, bind=False)
        self.fe_stream.on_recv(self.handle_fe)

    def handle_fe(self, msg):
        log.debug("handle_fe {}".format(msg))
        d = deserialize(msg[0])
        self.queue[d["id"]].Signal(d)

    def _do_request(self, request):
        _id = self.id
        self.id += 1
        self.queue[_id] = self.cothread.EventQueue()
        self.fe_stream.send(request)
        while True:
            d = self.queue[_id].Wait(self.timeout)
            assert d["id"] == _id, "Wrong id"
            if d["type"] in ["value", "return"]:
                yield d.get("val")
            elif d["type"] == "error":
                raise eval(d["name"])(d["message"])
            else:
                raise KeyError("Don't know what to do with {}".format(d))
            if d["type"] == "return":
                self.queue.pop(_id).close()
                return

    def get(self, param=None):
        if param is None:
            param = self.device
        else:
            param = ".".join((self.device, param))
        s = serialize_get(self.id, param)
        log.debug("get {}".format(s))
        ret = list(self._do_request(s))[-1]
        return ret

    def calliter(self, method, **kwargs):
        s = serialize_call(self.id, ".".join((self.device, method)), **kwargs)
        log.debug("calliter {}".format(s))
        ret = self._do_request(s)
        return ret

    def call(self, method, **kwargs):
        s = serialize_call(self.id, ".".join((self.device, method)), **kwargs)
        log.debug("call {}".format(s))
        ret = list(self._do_request(s))[-1]
        return ret
