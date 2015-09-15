import abc
import json
from collections import OrderedDict

import zmq

from malcolm.core.transport import ISocket, SType
from malcolm.core.base import weak_method
from malcolm.jsonPresentation.jsonPresenter import JsonPresenter


presenter = JsonPresenter()


class ZmqSocket(ISocket):

    @abc.abstractmethod
    def make_zmq_sock(self):
        """Make the zmq sock and bind or connect to address, returning it"""

    def send(self, msg):
        """Send the message to the socket"""
        self.log_debug("Sent message {}".format(msg))
        return weak_method(self.__retry)(self.POLLOUT, self.sock.send_multipart, msg,
                            flags=zmq.NOBLOCK)

    def recv(self):
        """Co-operatively block until received"""
        try:
            msg = weak_method(self.__retry)(self.POLLIN, self.sock.recv_multipart,
                                            flags=zmq.NOBLOCK)
        except zmq.ZMQError:
            raise StopIteration
        else:
            self.log_debug("Got message {}".format(msg))
            return msg

    def serialize(self, typ, kwargs):
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
        s = presenter.serialize(d)
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
        d = presenter.deserialize(data)
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

    def __retry(self, poll, action, *args, **kwargs):
        while True:
            try:
                ret = action(*args, **kwargs)
                return ret
            except zmq.ZMQError as error:
                if error.errno != zmq.EAGAIN:
                    raise
            if not self.poll_list([(self, poll)], self.timeout):
                raise zmq.ZMQError(zmq.ETIMEDOUT, 'Timeout waiting for socket')            

    def open(self, address):
        """Open the socket on the given address"""
        from cothread import coselect
        import cothread
        self.cothread = cothread
        self.poll_list = coselect.poll_list
        self.POLLIN = coselect.POLLIN
        self.POLLOUT = coselect.POLLOUT
        self.context = zmq.Context()
        self.sock = self.make_zmq_sock(address)

    def close(self):
        """Close the socket"""
        self.sock.close()
        self.context.destroy()
