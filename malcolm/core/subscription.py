from .loop import EventLoop
from .base import weak_method
from .transport import SType


class ServerSubscription(EventLoop):

    def __init__(self, device, ename=None, send=None, timeout=None):
        name = "ServerSubscription.{}".format(device.name)
        if ename is not None:
            name += "." + ename
        super(ServerSubscription, self).__init__(name, timeout)
        # Device has a ref to us, so we shouldn't have a strong ref to it
        self.device_remove_listener = weak_method(device.remove_listener)
        device.add_listener(self.post, ename)
        if send:
            self.send = send
        else:
            self.send = self.do_nothing
        self.add_event_handler(None, self.send)

    def __repr__(self):
        return "<{}>".format(self.name)

    def do_nothing(self, *args, **kwargs):
        pass

    def post(self, value, changes):
        super(ServerSubscription, self).post(
            value, SType.Value, value, changes=changes)

    def loop_stop(self, *args, **kwargs):
        super(ServerSubscription, self).loop_stop()
        self.device_remove_listener(self.post)
        self.send(SType.Return)


class ClientSubscription(EventLoop):

    def __init__(self, sock, endpoint, callback, timeout=None):
        name = "ClientSubscription.{}".format(endpoint)
        super(ClientSubscription, self).__init__(name, timeout)
        self.add_event_handler(SType.Value, callback)
        # TODO: add errback
        # el.add_event_handler(SType.Error, callback)
        self.add_event_handler(SType.Return, self.loop_stop)
        self.sock_response = sock.request(
            weak_method(self.post), SType.Subscribe, dict(endpoint=endpoint))

    def loop_stop(self, *args, **kwargs):
        super(ClientSubscription, self).loop_stop()
        if self.sock_response:
            self.sock_response(SType.Unsubscribe)
