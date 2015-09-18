from collections import OrderedDict
import weakref

import zmq

from malcolm.core.transport import ClientSocket
from .zmqSocket import ZmqSocket


class ZmqClientSocket(ZmqSocket, ClientSocket):

    def make_zmq_sock(self, address):
        """Make the zmq sock and bind or connect to address, returning it"""
        sock = self.context.socket(zmq.DEALER)
        # LINGER for 1s after close() to make sure messages are sent
        sock.setsockopt(zmq.LINGER, 1000)
        sock.connect(address)
        return sock

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
            self.send([self.serialize(typ, kwargs)])

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

ZmqClientSocket.register("zmq://")
