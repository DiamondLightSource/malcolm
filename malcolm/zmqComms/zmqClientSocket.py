import zmq

from .zmqSocket import ZmqSocket
from malcolm.core.socket import ClientSocket


class ZmqClientSocket(ZmqSocket, ClientSocket):

    def make_zmq_sock(self):
        """Make the zmq sock and bind or connect to address, returning it"""
        sock = self.context.socket(zmq.DEALER)
        sock.connect(self.name)
        return sock

    def request(self, response, typ, kwargs):
        """Make a new request and send it out, storing a suitable id so that
        any returns can be mapped to the response function using do_response"""
        # lazily make request map
        if not hasattr(self, "request_id"):
            self.request_id = {}
            self.last_id = -1
        self.last_id += 1
        self.request_id[self.last_id] = response
        kwargs.update(id=self.last_id)
        self.send(self.serialize(typ, kwargs))

    def lookup_response(self, kwargs, remove_response=False):
        """Return the reponse function given the id stored in the args. If
        remove, then remove it from the list"""
        _id = kwargs.pop("id")
        if remove_response:
            return self.request_id.pop(_id)
        else:
            return self.request_id[_id]

ZmqClientSocket.register("zmq://")
