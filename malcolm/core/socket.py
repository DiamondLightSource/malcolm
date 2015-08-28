import abc

from .loop import ILoop, LState
from .serialize import SType


class ISocket(ILoop):

    def __init__(self, address, timeout=None):
        super(ISocket, self).__init__(address)
        self.timeout = timeout

    @abc.abstractmethod
    def send(self, msg):
        """Send the message to the socket"""

    @abc.abstractmethod
    def recv(self):
        """Co-operatively block until received"""

    @abc.abstractmethod
    def serialize(self, typ, kwargs):
        """Serialize the arguments to a string that can be sent to the socket
        """

    @abc.abstractmethod
    def deserialize(self, msg):
        """Deserialize the string to
        (typ, kwargs)"""

    @abc.abstractmethod
    def open(self, address):
        """Open the socket on the given address"""

    @abc.abstractmethod
    def close(self):
        """Close the socket"""

    @abc.abstractmethod
    def handle_message(self, typ, kwargs):
        """Handle message"""

    @classmethod
    def make_socket(cls, address, *args, **kwargs):
        for prefix, socket_cls in cls.type_prefixes:
            if address.startswith(prefix):
                return socket_cls(address[len(prefix):], *args, **kwargs)

    def event_loop(self):
        """Call recv() on socket and deal with return"""
        while self.loop_state() == LState.Running:
            try:
                typ, kwargs = self.deserialize(self.recv())
            except:
                self.log_exception("Exception raised deserializing message")
                continue
            self.log_debug("Got message {} {}".format(typ, kwargs))
            try:
                self.handle_message(typ, kwargs)
            except:
                self.log_exception("Exception raised handling message")
                continue
        self.loop_confirm_stopped()

    def loop_run(self):
        super(ISocket, self).loop_run()
        self.open(self.name)
        self.event_loop_proc = self.spawn(self.event_loop)

    def loop_stop(self):
        super(ISocket, self).loop_stop()
        self.close()

    def loop_wait(self):
        self.event_loop_proc.Wait(timeout=self.timeout)


class ClientSocket(ISocket):
    # (prefix, ClientSocket subclass) tuples
    type_prefixes = []

    @classmethod
    def register(cls, address_prefix):
        """Registers the current class with an address prefix. This will make
        the baseclass make_socket() use the correct class for the prefix"""
        ClientSocket.type_prefixes.append((address_prefix, cls))

    @abc.abstractmethod
    def request(self, response, typ, kwargs):
        """Make a new request and send it out, storing a suitable id so that
        any returns can be mapped to the response function using do_response"""

    @abc.abstractmethod
    def lookup_response(self, kwargs, remove_response=False):
        """Return the reponse function given the id stored in the args. If
        remove, then remove it from the list"""

    def handle_message(self, typ, kwargs):
        """Call recv() on socket and deal with return"""
        remove_response = typ == SType.Return
        func = self.lookup_response(kwargs, remove_response)
        func(typ, **kwargs)


class ServerSocket(ISocket):
    # (prefix, ServerSocket subclass) tuples
    type_prefixes = []

    @classmethod
    def register(cls, address_prefix):
        """Registers the current class with an address prefix. This will make
        the baseclass make_socket() use the correct class for the prefix"""
        ServerSocket.type_prefixes.append((address_prefix, cls))

    def __init__(self, address, processq, timeout=None):
        super(ServerSocket, self).__init__(address, timeout)
        self.processq = processq

    @abc.abstractmethod
    def make_send_function(self, kwargs):
        """Make a send function that will call send with suitable arguments
        to be used as a response function"""

    def handle_message(self, typ, kwargs):
        """Call recv() on socket and deal with return"""
        send = self.make_send_function(kwargs)
        self.processq.Signal((typ, [send], kwargs))
