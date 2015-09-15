import weakref
from collections import OrderedDict

import zmq

from malcolm.core.transport import ServerSocket, SType
from .zmqSocket import ZmqSocket


class ZmqServerSocket(ZmqSocket, ServerSocket):

    def make_zmq_sock(self, address):
        """Make the zmq sock and bind or connect to address, returning it"""
        sock = self.context.socket(zmq.ROUTER)
        # Set router sockets to error when client is no longer connected
        try:
            sock.setsockopt(zmq.ROUTER_BEHAVIOR, 1)
        except:
            sock.setsockopt(zmq.ROUTER_MANDATORY, 1)
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
                try:
                    self.send([zmq_id, msg])
                except zmq.ZMQError:
                    # Unsubscribe all things with this zmq id
                    sends = []
                    for (z, i) in self._send_functions.keys():
                        if z == zmq_id:
                            sends.append(self._send_functions.pop((z, i)))
                    if sends:
                        self.log_debug("Unsubscribing {}"
                                       .format([s.endpoint for s in sends]))
                        for send in sends:
                            self.processq.Signal(
                                (SType.Unsubscribe, [send], {}))

            self._send_functions[(zmq_id, _id)] = send
        return self._send_functions[(zmq_id, _id)]

ZmqServerSocket.register("zmq://")
