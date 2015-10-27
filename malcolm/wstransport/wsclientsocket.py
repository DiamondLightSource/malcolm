from collections import OrderedDict
import weakref
import time

from malcolm.core.transport import ClientSocket, SType
from malcolm.jsonpresentation.jsonpresenter import JsonPresenter
from malcolm.core.base import weak_method


presenter = JsonPresenter()


class WsClientSocket(ClientSocket):
    # TODO: this shares a lot with zmq...

    def send(self, msg):
        """Send the message to the socket"""
        self.sock.send(msg)

    def received_message(self, msg):
        assert self.msg is None, \
            "Already got non-zero msg {}".format(self.msg)
        self.msg = str(msg)

    def recv(self, timeout=None):
        """Co-operatively block until received"""
        start = time.time()
        self.msg = None
        if timeout is None:
            timeout = self.timeout
        while True:
            if timeout:
                t = start + timeout - time.time()
            else:
                t = None
            self.sock.sock.settimeout(t)
            if self.sock.once() is False:
                # Failed
                raise StopIteration
            elif self.msg is not None:
                # sys.stdout.write("Got message {}\n".format(self.msg))
                # sys.stdout.flush()
                return self.msg

    def serialize(self, typ, kwargs):
        """Serialize the arguments to a string that can be sent to the socket
        """
        _id = kwargs.pop("id")
        assert type(_id) == int, "Need an integer ID, got {}".format(_id)
        assert typ in SType, \
            "Expected type in {}, got {}".format(list(SType.__members__), typ)
        d = OrderedDict(type=typ.name)
        d.update(id=_id)
        if kwargs is not None:
            d.update(kwargs)
        s = presenter.serialize(d)
        return s

    def deserialize(self, msg):
        """Deserialize the string to
        (typ, kwargs)"""
        d = presenter.deserialize(msg)
        typ = d.pop("type")
        assert typ in SType.__members__, \
            "Expected type in {}, got {}".format(list(SType.__members__), typ)
        typ = SType.__members__[typ]
        assert "id" in d, "No id in {}".format(d)
        return typ, d

    def open(self, address):
        """Open the socket on the given address"""
        from cothread.cosocket import socket as cosocket
        import socket
        from ws4py.client import WebSocketBaseClient
        _socket = socket.socket
        socket.socket = cosocket
        self.sock = WebSocketBaseClient(address)
        self.sock.handshake_ok = lambda: None
        socket.socket = _socket
        self.sock.received_message = weak_method(self.received_message)
        self.sock.connect()

    def close(self):
        """Close the socket"""
        self.sock.close()

    def request(self, response, typ, kwargs):
        """Make a new request and send it out, storing a suitable id so that
        any returns can be mapped to the response function using do_response"""
        # lazily make request map
        if not hasattr(self, "request_id"):
            self.request_id = {}
            self.last_id = -1
        self.last_id += 1
        assert self.last_id not in self.request_id, \
            "Already have a request {} in {}".format(self.last_id,
                                                     self.request_id)
        self.request_id[self.last_id] = response

        self = weakref.proxy(self)

        def do_request(typ, kwargs=None, _id=self.last_id):
            if kwargs is None:
                kwargs = OrderedDict()
            kwargs.update(id=_id)
            self.send(self.serialize(typ, kwargs))

        do_request(typ, kwargs)
        return do_request

    def lookup_response(self, kwargs, remove_response=False):
        """Return the reponse function given the id stored in the args. If
        remove, then remove it from the list"""
        _id = kwargs.pop("id")
        if remove_response:
            return self.request_id.pop(_id)
        else:
            return self.request_id[_id]


WsClientSocket.register("ws://")
WsClientSocket.register("wss://")
