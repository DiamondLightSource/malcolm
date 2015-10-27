import abc
import time
import os
from collections import OrderedDict, deque

import zmq

from malcolm.core.transport import ISocket, SType
from malcolm.jsonpresentation.jsonpresenter import JsonPresenter


presenter = JsonPresenter()


class ZmqSocket(ISocket):

    @abc.abstractmethod
    def make_zmq_sock(self, address):
        """Make the zmq sock and bind or connect to address, returning it"""

    def send(self, msg):
        """Send the message to the socket"""
        self.sendq.append(msg)
        # sys.stdout.write("Sent message {}\n".format(msg))
        # sys.stdout.flush()
        # Tell our event loop to recheck recv
        os.write(self.sendsig_w, "-")

    def recv(self, timeout=None):
        """Co-operatively block until received"""
        start = time.time()
        if timeout is None:
            timeout = self.timeout
        while True:
            try:
                msg = self.sock.recv_multipart(flags=zmq.NOBLOCK)
            except zmq.ZMQError as error:
                if error.errno == zmq.EAGAIN:
                    if timeout:
                        t = start + timeout - time.time()
                    else:
                        t = None
                    ready = self.poll_list(self.event_list, t)
                    if not ready:
                        raise zmq.ZMQError(
                            zmq.ETIMEDOUT, 'Timeout waiting for socket')
                    elif ready[0][0] == self.sendsig_r:
                        # clear send pipe
                        if os.read(self.sendsig_r, 1) == "!":
                            raise StopIteration
                        else:
                            # Send sent thing
                            self.sock.send_multipart(self.sendq.popleft())
                elif error.errno in [zmq.ENOTSOCK, zmq.ENOTSUP]:
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

    def open(self, address):
        """Open the socket on the given address"""
        from cothread import coselect
        import cothread
        self.cothread = cothread
        self.poll_list = coselect.poll_list
        self.context = zmq.Context()
        self.sock = self.make_zmq_sock(address[len("zmq://"):])
        self.sendsig_r, self.sendsig_w = os.pipe()
        self.sendq = deque()
        self.event_list = [(self.sock.fd, coselect.POLLIN),
                           (self.sendsig_r, coselect.POLLIN)]

    def close(self):
        """Close the socket"""
        os.write(self.sendsig_w, "!")
        self.sock.close()
        self.context.destroy()
