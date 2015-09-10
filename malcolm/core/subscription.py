from .loop import EventLoop
from .serialize import SType
from .base import weak_method


class Subscription(EventLoop):

    def __init__(self, device, ename=None, send=None, timeout=None):
        name = "Subscription.{}".format(device.name)
        if ename is not None:
            name += "." + ename
        super(Subscription, self).__init__(name, timeout)
        # Device has a ref to us, so we shouldn't have a strong ref to it
        self.device_remove_listener = weak_method(device.remove_listener)
        device.add_listener(self.post, ename)
        if send:
            self.send = send
        else:
            self.send = self.do_nothing
        self.add_event_handler(None, self.send)

    def do_nothing(self, *args, **kwargs):
        pass

    def post(self, value, changes):
        super(Subscription, self).post(value, SType.Value, value, changes=changes)

    def loop_stop(self, *args, **kwargs):
        super(Subscription, self).loop_stop()
        self.device_remove_listener(self.post)
        self.send(SType.Return)
