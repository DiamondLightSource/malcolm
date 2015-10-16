import abc
from collections import OrderedDict
import time

import zmq
import os

from malcolm.core.transport import ISocket, SType
from malcolm.core.base import weak_method
from malcolm.jsonPresentation.jsonPresenter import JsonPresenter


presenter = JsonPresenter()


class ZmqSocket(ISocket):

    @abc.abstractmethod
    def make_zmq_sock(self, address):
        """Make the zmq sock and bind or connect to address, returning it"""

    def send(self, msg, timeout=None):
        """Send the message to the socket"""
        if timeout is None:
            timeout = self.timeout
        weak_method(self.__retry)(
            self.sock.send_multipart, self.send_list, timeout, msg)
        # sys.stdout.write("Sent message {}\n".format(msg))
        # sys.stdout.flush()
        # Tell our event loop to recheck recv
        os.write(self.sendsig_w, "-")

    def recv(self, timeout=None):
        """Co-operatively block until received"""
        if timeout is None:
            timeout = self.timeout
        try:
            msg = weak_method(self.__retry)(
                self.sock.recv_multipart, self.recv_list, timeout)
        except zmq.ZMQError as error:
            if error.errno in [zmq.ENOTSOCK, zmq.ENOTSUP]:
                raise StopIteration
            else:
                raise
        else:
            # sys.stdout.write("Got message {}\n".format(msg))
            # sys.stdout.flush()
            return msg

    def serialize(self, typ, kwargs):
        """Serialize the arguments to a string that can be sent to the socket
        """
        kwargs.pop("zmq_id", None)
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

    def __retry(self, action, event_list, timeout, *args, **kwargs):
        start = time.time()
        kwargs.update(flags=zmq.NOBLOCK)
        while True:
            try:
                return action(*args, **kwargs)
            except zmq.ZMQError as error:
                if error.errno != zmq.EAGAIN:
                    raise
                else:
                    if timeout:
                        t = start + self.timeout - time.time()
                    else:
                        t = None
                    ready = self.poll_list(event_list, t)
                    if not ready:
                        raise zmq.ZMQError(
                            zmq.ETIMEDOUT, 'Timeout waiting for socket')
                    elif ready[0][0] == self.sendsig_r:
                        # clear send pipe
                        os.read(self.sendsig_r, 1)

    def open(self, address):
        """Open the socket on the given address"""
        from cothread import coselect
        import cothread
        self.cothread = cothread
        self.poll_list = coselect.poll_list
        self.context = zmq.Context()
        self.sock = self.make_zmq_sock(address)
        self.sendsig_r, self.sendsig_w = os.pipe()
        self.send_list = [(self.sock.fd, coselect.POLLOUT)]
        self.recv_list = [(self.sock.fd, coselect.POLLIN),
                          (self.sendsig_r, coselect.POLLIN)]

    def close(self):
        """Close the socket"""
        os.write(self.sendsig_w, "-")
        self.sock.close()
        self.context.destroy()
