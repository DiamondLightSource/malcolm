import functools

from .device import Device
from .runnableDevice import DState
from .loop import ILoop, LState, TimerLoop
from .serialize import SType
from .base import weak_method
from .attribute import Attribute
from .stateMachine import StateMachine
from .loop import EventLoop
from malcolm.core.alarm import Alarm


class ValueQueue(ILoop):

    def loop_run(self):
        """Start the event loop running"""
        super(ValueQueue, self).loop_run()
        self.inq = self.cothread.EventQueue()
        self.finished = self.cothread.Pulse()

    def post(self, event, **kwargs):
        self.inq.Signal((event, kwargs))

    def loop_wait(self):
        """Wait for a loop to finish"""
        if self.loop_state() != LState.Stopped:
            self.finished.Wait()

    def loop_confirm_stopped(self):
        super(ValueQueue, self).loop_confirm_stopped()
        self.finished.Signal()

    def loop_stop(self):
        """Signal the event loop to stop running and wait for it to finish"""
        super(ValueQueue, self).loop_stop()
        self.inq.close()


class DeviceClient(Device):

    def __init__(self, name, sock, monitor=True, timeout=None):
        super(DeviceClient, self).__init__(name, timeout)
        self.monitor = monitor
        self.sock = sock
        # Every 10 seconds, do a heartbeat
        self.hb = TimerLoop(
            name + ".hb", weak_method(self.do_ping), timeout=10)
        # Add connection attribute
        self.add_attributes(
            device_client_connected=Attribute(bool, "Is device reponsive?"))

    def loop_run(self):
        super(DeviceClient, self).loop_run()
        # Get the structure
        structure = self.do_get()
        # Update attributes
        for aname, adata in structure.get("attributes", {}).items():
            self.add_attribute(
                aname, Attribute(eval(adata["type"]), adata["descriptor"],
                                 tags=adata.get("tags", None)))

            def update(d):
                self.attributes[aname].update(
                    d["value"], Alarm(**d["alarm"]), d["timeStamp"])
            update(adata)
            if self.monitor:
                self.do_subscribe(update, "attributes.{}".format(aname))
        # Update statemachine
        if "stateMachine" in structure:
            sdata = structure["stateMachine"]
            choices = sdata["state"]["choices"]
            keys = [s.name for s in DState]
            assert choices == keys, \
                "DState mismatch: {} != {}".format(choices, keys)
            initial = list(DState)[sdata["state"]["index"]]
            sm = StateMachine(self.name + ".stateMachine", initial)
            self.add_stateMachine(sm)

            def update(d):
                state = list(DState)[d["state"]["index"]]
                sm.update(state, d["message"], d["timeStamp"])
            update(sdata)
            if self.monitor:
                self.do_subscribe(update, "stateMachine")
        # Update methods
        for mname, mdata in structure.get("methods", {}).items():
            f = functools.partial(self.do_call, mname)
            f.__doc__ = mdata["descriptor"]
            f.func_name = str(mname)
            setattr(self, mname, f)

    def do_request(self, typ, endpoint, **kwargs):
        vq = ValueQueue("{}({})".format(typ, endpoint))
        self.add_loop(vq)
        kwargs["endpoint"] = endpoint
        self.sock.request(vq.post, typ, kwargs)
        event, d = vq.inq.Wait(self.timeout)
        vq.loop_stop()
        vq.loop_confirm_stopped()
        if event == SType.Return:
            return d["value"]
        elif event == SType.Error:
            raise AssertionError(d["message"])
        else:
            raise AssertionError("Don't know what to do with {} {}"
                                 .format(event, d))

    def do_subscribe(self, callback, endpoint=None):
        if endpoint is not None:
            endpoint = ".".join((self.name, endpoint))
        else:
            endpoint = self.name
        el = EventLoop("Subscription.{}".format(endpoint))
        self.add_loop(el)
        el.add_event_handler(SType.Value, callback)
        # TODO: add errback
        # el.add_event_handler(SType.Error, callback)
        el.add_event_handler(SType.Return, el.loop_stop)
        self.sock.request(el.post, SType.Subscribe, dict(endpoint=endpoint))
        return el

    def do_call(self, endpoint, **kwargs):
        # Setup a ValueQueue that will handle the returns
        endpoint = ".".join((self.name, endpoint))
        return self.do_request(SType.Call, endpoint, args=kwargs)

    def do_get(self, endpoint=None):
        if endpoint is not None:
            endpoint = ".".join(self.name, endpoint)
        else:
            endpoint = self.name
        return self.do_request(SType.Get, endpoint)

    def do_ping(self):
        try:
            assert self.ping() == "pong"
        except:
            self.connected = False
        else:
            self.connected = True
