import zmq
import time
import json

def make_sock(context, sock_type, bind=None, connect=None):
    """
    Creates a *sock_type* typed socket and binds or connects it to the given
    address.

    """
    sock = TestSocket(context, sock_type)
    if bind:
        sock.bind(bind)
    elif connect:
        sock.connect(connect)

    return sock

def get_forwarder(func):
    """Returns a simple wrapper for *func*."""
    def forwarder(*args, **kwargs):
        return func(*args, **kwargs)

    return forwarder

def get_wrapped_fwd(func):
    """
    Returns a wrapper, that tries to call *func* multiple time in non-blocking
    mode before rasing an :class:`zmq.ZMQError`.

    """
    def forwarder(*args, **kwargs):
        # 100 tries * 0.01 second == 1 second
        for i in range(100):
            try:
                rep = func(*args, flags=zmq.NOBLOCK, **kwargs)
                return rep

            except zmq.ZMQError:
                # running under client event loop (no cothread), so this is ok
                time.sleep(0.01)

        # We should not get here, so raise an error.
        msg = 'Could not %s message.' % func.__name__[:4]
        raise zmq.ZMQError(msg)

    return forwarder

class TestSocket(object):
    """
    Wraps ZMQ :class:`~zmq.core.socket.Socket`. All *recv* and *send* methods
    will be called multiple times in non-blocking mode before a
    :class:`zmq.ZMQError` is raised.

    """
    def __init__(self, context, sock_type):
        self._context = context

        sock = context.socket(sock_type)
        self._sock = sock

        forwards = [  # These methods can simply be forwarded
            sock.bind,
            sock.bind_to_random_port,
            sock.connect,
            sock.close,
            sock.setsockopt,
        ]
        wrapped_fwd = [  # These methods are wrapped with a for loop
            sock.recv,
            sock.recv_json,
            sock.recv_multipart,
            sock.recv_unicode,
            sock.send,
            sock.send_json,
            sock.send_multipart,
            sock.send_unicode,
        ]

        for func in forwards:
            setattr(self, func.__name__, get_forwarder(func))

        for func in wrapped_fwd:
            setattr(self, func.__name__, get_wrapped_fwd(func))
            
