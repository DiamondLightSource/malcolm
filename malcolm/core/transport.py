import abc
import socket

from enum import Enum

from .loop import ILoop
from .base import weak_method


class SType(Enum):
    Call, Get, Subscribe, Unsubscribe, Error, Value, Return = range(7)


class ISocket(ILoop):
    # Name is the server string we should use to connect to it
    # Address is the address we should bind to

    def __init__(self, name, address, timeout=None):
        super(ISocket, self).__init__(name)
        # Store
        self.address = address
        self.timeout = timeout

    @abc.abstractmethod
    def send(self, msg):
        """Send the message to the socket"""

    @abc.abstractmethod
    def recv(self, timeout=None):
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
                # Calc name from address
                hostname = socket.getfqdn()
                ip = socket.gethostbyname(hostname)
                name = address.replace("0.0.0.0", ip)
                return socket_cls(name, address, *args, **kwargs)

    def loop_event(self):
        msg = weak_method(self.recv)(timeout=0)
        typ, kwargs = weak_method(self.deserialize)(msg)
        weak_method(self.handle_message)(typ, kwargs)

    def loop_run(self):
        self.open(self.address)
        super(ISocket, self).loop_run()

    def loop_stop(self):
        super(ISocket, self).loop_stop()
        self.close()


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
        cached = kwargs.copy()
        func = self.lookup_response(kwargs, remove_response)
        try:
            func(typ, **kwargs)
        except ReferenceError:
            # Object has gone, remove response if not already gone
            self.log_debug("Response to {} refs object that no longer exists"
                           .format(cached))
            if not remove_response:
                self.log_debug("Removing its response function")
                self.lookup_response(cached, True)


class ServerSocket(ISocket):
    # (prefix, ServerSocket subclass) tuples
    type_prefixes = []

    @classmethod
    def register(cls, address_prefix):
        """Registers the current class with an address prefix. This will make
        the baseclass make_socket() use the correct class for the prefix"""
        ServerSocket.type_prefixes.append((address_prefix, cls))

    def __init__(self, name, address, processq, timeout=None):
        super(ServerSocket, self).__init__(name, address, timeout)
        self.processq = processq

    @abc.abstractmethod
    def make_send_function(self, kwargs):
        """Make a send function that will call send with suitable arguments
        to be used as a response function"""

    def handle_message(self, typ, kwargs):
        """Call recv() on socket and deal with return"""
        send = self.make_send_function(kwargs)
        send.endpoint = kwargs.get("endpoint", "")
        self.processq.Signal((typ, [send], kwargs))
