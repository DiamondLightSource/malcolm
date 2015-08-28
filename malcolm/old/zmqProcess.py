import sys
import multiprocessing
import zmq
import logging
log = logging.getLogger(__name__)


class CoStream(object):

    def __init__(self, context, sock_type, addr, bind, timeout=None):
        # Make the socket and bind or connect it
        self.sock = context.socket(sock_type)
        if bind:
            self.sock.bind(addr)
        else:
            self.sock.connect(addr)
        # This is the callback when we get a new message
        self._on_recv = None
        # This is the timeout for any blocking call
        self.timeout = timeout

    def setup(self, coselect):
        self.poll_list = coselect.poll_list
        self.POLLIN = coselect.POLLIN
        self.POLLOUT = coselect.POLLOUT

    def fileno(self):
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

    def recv_multipart(self):
        return self.__retry(self.POLLIN, self.sock.recv_multipart, flags=zmq.NOBLOCK)

    def recv(self):
        return self.__retry(self.POLLIN, self.sock.recv, flags=zmq.NOBLOCK)

    def send_multipart(self, message):
        # return self.sock.send_multipart(message)
        return self.__retry(self.POLLOUT, self.sock.send_multipart, message, 
                            flags=zmq.NOBLOCK)

    def send(self, message):
        # return self.sock.send(message)
        return self.__retry(self.POLLOUT, self.sock.send, message, flags=zmq.NOBLOCK)

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

    def __init__(self, timeout=None):
        super(ZmqProcess, self).__init__()
        self.streams = []
        self.loops = []
        self.timeout = timeout

    def setup(self):
        """
        Creates a :attr:`context` and an event :attr:`loop` for the process.

        """
        self.context = zmq.Context()
        # If we are in a multiprocessing loop then check that cothread has not
        # been inherited from the forked mainprocess. If it has then we can't
        # use cothread as we will share the same scheduler!
        if type(multiprocessing.current_process()) == type(self):
            # We are in a multiprocessing child process
            cothread_imports = [x for x in sys.modules
                                if x.startswith("cothread")]
            assert len(cothread_imports) == 0, \
                "Cothread has already been imported, this will not work!"
        import cothread
        self.cothread = cothread

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
        stream = CoStream(self.context, sock_type, addr, bind, self.timeout)
        stream.setup(self.cothread.coselect)
        self.streams.append(stream)
        return stream

    def run(self, block=True):
        """Sets up everything and starts the event loops."""
        self.setup()
        for stream in self.streams:
            self.loops.append(self.cothread.Spawn(
                stream.event_loop, raise_on_wait=True))
        self.quitsig = self.cothread.Pulse()
        if block:
            self.quitsig.Wait()
            self.wait_loops()

    def wait_loops(self):
        for stream in self.streams:
            stream.close()
        for loop in self.loops:
            try:
                loop.Wait()
            except zmq.ZMQError as e:
                log.debug("Exception raised in event loop {}".format(e))

    def exit(self):
        """Stops the event loop."""
        self.quitsig.Signal()
