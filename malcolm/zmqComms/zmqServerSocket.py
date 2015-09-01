import weakref

from .zmqSocket import ZmqSocket
from malcolm.core.socket import ServerSocket


class ZmqServerSocket(ZmqSocket, ServerSocket):

    def make_zmq_sock(self):
        """Make the zmq sock and bind or connect to address, returning it"""
        sock = self.context.socket(zmq.ROUTER)
        sock.bind(self.name)
        return sock

    def make_send_function(self, kwargs):
        """Make a send function that will call send with suitable arguments
        to be used as a response function"""
        if not hasattr(self, "_send_functions"):
            self._send_functions = weakref.WeakValueDictionary()
        zmq_id = kwargs.pop("zmq_id")
        _id = kwargs.pop("id")
        if (zmq_id, _id) not in self._send_functions:

            def send(typ, kwargs):
                kwargs.update(id=_id, zmq_id=zmq_id)
                msg = self.serialize(typ, kwargs)
                self.send(msg)

            self._send_functions[(zmq_id, _id)] = send
        return self._send_functions[(zmq_id, _id)]

ZmqServerSocket.register("zmq://")
