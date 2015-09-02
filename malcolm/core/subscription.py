import weakref

from .loop import EventLoop
from .serialize import SType


class Subscription(EventLoop):

    def __init__(self, device, ename=None, send=None, timeout=None):
        name = "Subscription.{}".format(device.name)
        if ename is not None:
            name += "." + ename
        super(Subscription, self).__init__(name, timeout)
        self.device = weakref.proxy(device)
        self.ename = ename
        device.add_listener(self.post, ename)
        if send:
            self.send = send
        else:
            self.send = self.do_nothing
        self.add_event_handler(None, self.send)

    def do_nothing(self, *args, **kwargs):
        pass

    def post(self, changes):
        if changes.keys() == ["."]:
            endpoint = changes["."]
        else:
            endpoint = self.device
            if self.ename is not None:
                for e in self.ename.split("."):
                    endpoint = endpoint.to_dict()[e]
        super(Subscription, self).post(endpoint, SType.Value, endpoint, changes=changes)

    def loop_stop(self, *args, **kwargs):
        super(Subscription, self).loop_stop()
        self.device.remove_listener(self.post)
        self.send(SType.Return)
