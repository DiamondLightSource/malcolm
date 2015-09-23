import abc
from collections import OrderedDict
import time

import zmq

from malcolm.core.transport import ISocket, SType
from malcolm.core.base import weak_method
from malcolm.jsonPresentation.jsonPresenter import JsonPresenter


presenter = JsonPresenter()


class ZmqSocket(ISocket):

    @abc.abstractmethod
    def make_zmq_sock(self, address):
        """Make the zmq sock and bind or connect to address, returning it"""

    def send(self, msg):
        """Send the message to the socket"""
        # self.sock.send_multipart(msg)
        weak_method(self.__retry)(self.poll_out_flags, self.sock.send_multipart, msg,
                                  flags=zmq.NOBLOCK)
        # self.log_debug("Sent message {}".format(msg))

    def recv(self):
        """Co-operatively block until received"""
        try:
            msg = weak_method(self.__retry)(self.poll_in_flags, self.sock.recv_multipart,
                                            flags=zmq.NOBLOCK)
        except zmq.ZMQError as error:
            if error.errno == zmq.ENOTSUP:
                raise StopIteration
            else:
                raise
        else:
            # self.log_debug("Got message {}".format(msg))
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

    def fileno(self):
        """Needed so that we can co-operatively poll socket"""
        return self.sock.fd

    def __retry(self, poll, action, *args, **kwargs):
        start = time.time()
        while True:
            try:
                ret = action(*args, **kwargs)
                return ret
            except zmq.ZMQError as error:
                if error.errno != zmq.EAGAIN:
                    raise
            if self.timeout and time.time() - start > self.timeout:
                raise zmq.ZMQError(zmq.ETIMEDOUT, 'Timeout waiting for socket')
            # Unfortunately, doing a close() on the socket doesn't always
            # break out of this poll(), so timeout and rely on the socket
            # call to catch the fact it's been closed
            self.poll_list([(self, poll)], 1)

    def open(self, address):
        """Open the socket on the given address"""
        from cothread import coselect
        import cothread
        self.cothread = cothread
        self.poll_list = coselect.poll_list
        # Extras that we should listen to apart from our dir
        poll_extra_flags = coselect.POLLHUP | coselect.POLLERR
        self.poll_in_flags = coselect.POLLIN | poll_extra_flags
        self.poll_out_flags = coselect.POLLOUT | poll_extra_flags
        self.context = zmq.Context()
        self.sock = self.make_zmq_sock(address)

    def close(self):
        """Close the socket"""
        self.sock.close()
        self.context.term()
