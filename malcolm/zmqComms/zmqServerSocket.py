import weakref

import zmq

from .zmqSocket import ZmqSocket
from malcolm.core.socketInterface import ServerSocket
from collections import OrderedDict
from malcolm.core.serialize import SType
from malcolm.core.base import weak_method


class ZmqServerSocket(ZmqSocket, ServerSocket):

    def make_zmq_sock(self, address):
        """Make the zmq sock and bind or connect to address, returning it"""
        sock = self.context.socket(zmq.ROUTER)
        sock.bind(address)
        return sock

    def make_send_function(self, kwargs):
        """Make a send function that will call send with suitable arguments
        to be used as a response function"""
        if not hasattr(self, "_send_functions"):
            self._send_functions = weakref.WeakValueDictionary()
        zmq_id = kwargs.pop("zmq_id")
        _id = kwargs.pop("id")
        if (zmq_id, _id) not in self._send_functions:
            self = weakref.proxy(self)

            def send(typ, value=None, **kwargs):
                kwargs = OrderedDict(id=_id)
                if typ == SType.Error:
                    kwargs.update(message=value.message)
                else:
                    if hasattr(value, "to_dict"):
                        value = value.to_dict()
                    kwargs.update(value=value)
                msg = self.serialize(typ, kwargs)
                self.send([zmq_id, msg])

            self._send_functions[(zmq_id, _id)] = send
        return self._send_functions[(zmq_id, _id)]

ZmqServerSocket.register("zmq://")
