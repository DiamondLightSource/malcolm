import multiprocessing
import zmq
import cothread
from cothread import coselect


class CoStream(object):

    def __init__(self, sock_type, addr, bind, timeout=None):
        # Make the socket and bind or connect it
        self.sock = zmq.Context().socket(sock_type)
        if bind:
            self.sock.bind(addr)
        else:
            self.sock.connect(addr)
        # This is the callback when we get a new message
        self._on_recv = None
        # This is the timeout for any blocking call
        self.timeout = timeout

    def fileno(self):
        return self.sock.getsockopt(zmq.FD)

    def __poll(self, event):
        if not coselect.poll_list([(self, event)], self.timeout):
            raise zmq.ZMQError(zmq.ETIMEDOUT, 'Timeout waiting for socket')

    def __retry(self, poll, action, *args, **kwargs):
        while True:
            try:
                return action(*args, **kwargs)
            except zmq.ZMQError as error:
                if error.errno != zmq.EAGAIN:
                    raise
            self.__poll(poll)

    def recv_multipart(self):
        return self.__retry(coselect.POLLIN, self.sock.recv_multipart, flags=zmq.NOBLOCK)

    def send_multipart(self, message):
        return self.__retry(coselect.POLLOUT, self.sock.send_multipart, message, flags=zmq.NOBLOCK)

    def send(self, message):
        return self.__retry(coselect.POLLOUT, self.sock.send, message, flags=zmq.NOBLOCK)

    def recv(self):
        return self.__retry(coselect.POLLOUT, self.sock.recv, flags=zmq.NOBLOCK)


    def on_recv(self, callback):
        self._on_recv = callback

    def event_loop(self):
        while True:
            ret = self.recv_multipart()
            if self._on_recv:
                self._on_recv(ret)

    def close(self):
        self.sock.close()

class ZmqProcess(multiprocessing.Process):
    """
    This is the base for all processes and offers utility functions
    for setup and creating new streams.

    """

    def __init__(self):
        super(ZmqProcess, self).__init__()
        # The zeroMQ context
        self.context = None
        self.streams = []

    def setup(self):
        """
        Creates a :attr:`context` and an event :attr:`loop` for the process.

        """
        self.context = zmq.Context()

    def stream(self, sock_type, addr, bind):
        """
        Creates a CoStream.

        :param sock_type: The zeroMQ socket type (e.g. ``zmq.REQ``)
        :param addr: Address to bind to
        :param bind: Binds to *addr* if ``True`` or tries to connect to it
                otherwise.
        :returns: The stream

        """
        # Create the stream and add the callback
        stream = CoStream(sock_type, addr, bind)
        self.streams.append(stream)
        return stream

    def run(self, block=True):
        """Sets up everything and starts the event loop."""
        self.setup()
        for stream in self.streams:
            cothread.Spawn(stream.event_loop)
        if block:
            cothread.WaitForQuit()

    def stop(self):
        """Stops the event loop."""
        cothread.Quit()
