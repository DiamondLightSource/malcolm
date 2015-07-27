import multiprocessing
import zmq
import cothread
from cothread import coselect


class CoStream(object):

    def __init__(self, sock):
        self.sock = sock
        self._on_recv = None

    def send_multipart(self, message):
        self.sock.send_multipart(message)

    def fileno(self):
        return self.sock.getsockopt(zmq.FD)

    def recv_multipart(self, timeout=None):
        while True:
            try:
                return self.sock.recv_multipart(flags=zmq.NOBLOCK)
            except zmq.ZMQError as error:
                if error.errno != zmq.EAGAIN:
                    raise
            if not coselect.poll_list([(self, coselect.POLLIN)], timeout):
                raise zmq.ZMQError(zmq.ETIMEDOUT, 'Timeout waiting for socket')

    def on_recv(self, callback):
        self._on_recv = callback

    def event_loop(self):
        while True:
            ret = self.recv_multipart()
            if self._on_recv:
                self._on_recv(ret)


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
        sock = self.context.socket(sock_type)

        # Bind/connect the socket
        if bind:
            sock.bind(addr)
        else:
            sock.connect(addr)

        # Create the stream and add the callback
        stream = CoStream(sock)
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
