# example_app/base.py
import multiprocessing

from zmq.eventloop import ioloop, zmqstream
import zmq


class ZmqProcess(multiprocessing.Process):
    """
    This is the base for all processes and offers utility functions
    for setup and creating new streams.

    """

    def __init__(self):
        super(ZmqProcess, self).__init__()

        self.context = None
        """The zeroMQ :class:`~zmq.Context` instance."""

        self.loop = None
        """PyZMQ's event loop (:class:`~zmq.eventloop.ioloop.IOLoop`)."""

    def setup(self):
        """
        Creates a :attr:`context` and an event :attr:`loop` for the process.

        """
        self.context = zmq.Context()
        self.loop = ioloop.IOLoop.instance()
        # Arrange for cothread to be serviced

    def stream(self, sock_type, addr, bind, subscribe=b''):
        """
        Creates a :class:`~zmq.eventloop.zmqstream.ZMQStream`.

        :param sock_type: The zeroMQ socket type (e.g. ``zmq.REQ``)
        :param addr: Address to bind to
        :param bind: Binds to *addr* if ``True`` or tries to connect to it
                otherwise.
        :param subscribe: Subscription pattern for *SUB* sockets, optional,
                defaults to ``b''``.
        :returns: A tuple containg the stream and the port number.

        """
        sock = self.context.socket(sock_type)

        # Bind/connect the socket
        if bind:
            sock.bind(addr)
        else:
            sock.connect(addr)

        # Add a default subscription for SUB sockets
        if sock_type == zmq.SUB:
            sock.setsockopt(zmq.SUBSCRIBE, subscribe)

        # Create the stream and add the callback
        stream = zmqstream.ZMQStream(sock, self.loop)
        return stream

    def run(self):
        """Sets up everything and starts the event loop."""
        self.setup()
        self.loop.start()

    def stop(self):
        """Stops the event loop."""
        self.loop.stop()
