from malcolm.zmqComms.zmqSerialize import serialize_call, serialize_get, \
    deserialize, SType, serialize_subscribe, serialize_unsubscribe
from zmqProcess import ZmqProcess
import zmq
import logging
log = logging.getLogger(__name__)


class ZmqSubscription(object):

    def __init__(self, dc, _id):
        self.dc = dc
        self.id = _id

    def listen(self, iterator, cb):
        for val in iterator:
            cb(val)

    def unsubscribe(self):
        self.dc.unsubscribe(self.id)


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

    def _do_request(self, s):
        # Keep a ref to id and increment
        _id = self.id
        self.id += 1
        # Send off the request
        self.fe_stream.send(s)
        # Make an event queue that our responses will appear in
        self.queue[_id] = self.cothread.EventQueue()
        # Now wait for responses
        while True:
            log.debug("Waiting for message from id {}".format(_id))
            d = self.queue[_id].Wait(self.timeout)
            log.debug("Got {}".format(d))
            assert d["id"] == _id, "Wrong id"
            if d["type"] in (SType.Value, SType.Return):
                yield d.get("val")
            elif d["type"] == SType.Error:
                raise AssertionError(d["message"])
            else:
                raise KeyError("Don't know what to do with {}".format(d))
            if d["type"] == SType.Return:
                self.queue.pop(_id).close()
                return

    def get(self, param=None):
        if param is None:
            param = self.device
        else:
            param = ".".join((self.device, param))
        log.debug("get {}".format(param))
        # This is an iterator
        iterator = self._do_request(serialize_get(self.id, param))
        # Process the iterator and get the last value
        values = list(iterator)
        assert len(values) == 1, "Expected 1 value, got {}".format(values)
        return values[-1]

    def calliter(self, method, **kwargs):
        method = ".".join((self.device, method))
        pargs = ", ".join("{}={!r}".format(k, v) for k, v in kwargs.items())
        log.debug("calliter {}({})".format(method, pargs))
        # This is an iterator
        iterator = self._do_request(serialize_call(self.id, method, **kwargs))
        return iterator

    def call(self, method, **kwargs):
        # This is an iterator
        iterator = self.calliter(method, **kwargs)
        # Process the iterator and get the last value
        values = list(iterator)
        return values[-1]

    def subscribe(self, cb, param=None):
        if param is None:
            param = self.device
        else:
            param = ".".join((self.device, param))
        log.debug("subscribe {}".format(param))
        # Create a subscription object
        sub = ZmqSubscription(self, self.id)
        # This is an iterator
        iterator = self._do_request(serialize_subscribe(self.id, param))
        # Tell it to manage the iterator
        self.cothread.Spawn(sub.listen, iterator, cb)
        return sub

    def unsubscribe(self, _id):
        s = serialize_unsubscribe(_id)
        self.fe_stream.send(s)
