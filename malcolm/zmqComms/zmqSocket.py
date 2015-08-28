import abc
import json
from collections import OrderedDict

import zmq

from malcolm.core.socket import ISocket
from malcolm.core.serialize import SType


class CustomSerializer(json.JSONEncoder):

    def default(self, o):
        if hasattr(o, "to_dict"):
            return o.to_dict()
        else:
            return super(CustomSerializer, self).default(o)

serializer = CustomSerializer()


class ZmqSocket(ISocket):

    @abc.abstractmethod
    def make_zmq_sock(self):
        """Make the zmq sock and bind or connect to address, returning it"""

    def send(self, msg):
        """Send the message to the socket"""
        return self.__retry(self.POLLOUT, self.sock.send_multipart, msg,
                            flags=zmq.NOBLOCK)

    def recv(self):
        """Co-operatively block until received"""
        return self.__retry(self.POLLIN, self.sock.recv_multipart,
                            flags=zmq.NOBLOCK)

    def serialize(self, typ, kwargs=None):
        """Serialize the arguments to a string that can be sent to the socket
        """
        zmq_id = kwargs.pop("zmq_id", None)
        _id = kwargs.pop("id")
        assert type(_id) == int, "Need an integer ID, got {}".format(_id)
        assert typ in SType, \
            "Expected type in {}, got {}".format(list(SType.__members__), typ)
        d = OrderedDict(type=typ.name)
        d.update(id=_id)
        if kwargs is not None:
            d.update(kwargs)
        s = serializer.encode(d)
        return s

    def deserialize(self, msg):
        """Deserialize the string to
        (typ, kwargs)"""
        if len(msg) == 1:
            # No client id
            zmq_id, data = None, msg[0]
        elif len(msg) == 2:
            # client id
            zmq_id, data = msg
        else:
            raise AssertionError("Message {} has wrong number of elements"
                                 .format(msg))
        d = json.loads(data, object_pairs_hook=OrderedDict)
        typ = d.pop("type")
        assert typ in SType.__members__, \
            "Expected type in {}, got {}".format(list(SType.__members__), typ)
        typ = SType.__members__[typ]
        assert "id" in d, "No id in {}".format(d)
        if zmq_id:
            d["zmq_id"] = zmq_id
        return typ, d

    def fileno(self):
        """Needed so that we can co-operatively poll socket"""
        return self.sock.fd

    def __poll(self, event):
        if not self.poll_list([(self, event)], self.timeout):
            raise zmq.ZMQError(zmq.ETIMEDOUT, 'Timeout waiting for socket')

    def __retry(self, poll, action, *args, **kwargs):
        while True:
            try:
                ret = action(*args, **kwargs)
                return ret
            except zmq.ZMQError as error:
                if error.errno != zmq.EAGAIN:
                    raise
            self.__poll(poll)

    def open(self, address):
        """Open the socket on the given address"""
        self.context = zmq.Context()
        from cothread import coselect
        self.poll_list = coselect.poll_list
        self.POLLIN = coselect.POLLIN
        self.POLLOUT = coselect.POLLOUT
        self.sock = self.make_zmq_sock()

    def close(self):
        """Close the socket"""
        self.sock.close()
