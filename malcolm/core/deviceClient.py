import functools

from .device import Device, not_process_creatable
from .runnableDevice import DState
from .loop import ILoop, LState, TimerLoop
from .serialize import SType
from .base import weak_method
from .attribute import Attribute
from .stateMachine import StateMachine
from .loop import EventLoop
from .alarm import Alarm
import time


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
        self.loop_confirm_stopped()


@not_process_creatable
class DeviceClient(Device):

    def __init__(self, name, sock, monitor=True, timeout=None):
        super(DeviceClient, self).__init__(name, timeout)
        self.monitor = monitor
        self.sock = sock
        # Every 10 seconds, do a heartbeat
        #self.add_loop(TimerLoop(
        #    name + ".hb", weak_method(self.do_ping), timeout=10))
        # Add connection attribute
        self.add_attributes(
            device_client_connected=Attribute(bool, "Is device reponsive?"))

    def loop_run(self):
        super(DeviceClient, self).loop_run()
        # Get the structure
        structure = self.do_get()
        # Update attributes
        for aname, adata in structure.get("attributes", {}).items():
            typ = adata["type"]
            if type(typ) == list:
                typ = [eval(t) for t in typ]
            else:
                typ = eval(typ)
            attr = self.add_attribute(
                aname, Attribute(typ, adata["descriptor"],
                                 tags=adata.get("tags", None)))

            def update(value, attr=attr):
                d = value
                value = d.get("value", None)
                if value is None:
                    if type(d["type"]) == list:
                        value = []
                    else:
                        value = eval(d["type"])()
                alarm = d.get("alarm", None)
                if alarm is None:
                    alarm = Alarm.ok()
                else:
                    alarm = Alarm(**d["alarm"])
                attr.update(value, alarm, d.get("timeStamp", None))
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

            def update(value):
                d = value
                state = list(DState)[d["state"]["index"]]
                sm.update(state, d["message"], d.get("timeStamp", None))
            update(sdata)
            if self.monitor:
                self.do_subscribe(update, "stateMachine")
        # Update methods
        for mname, mdata in structure.get("methods", {}).items():
            f = functools.partial(weak_method(self.do_call), "methods." + mname)
            f.__doc__ = mdata.get("descriptor", mname)
            f.func_name = str(mname)
            setattr(self, mname, f)

    def do_request(self, typ, endpoint, **kwargs):
        vq = ValueQueue("{}({})".format(typ, endpoint))
        vq.loop_run()
        kwargs["endpoint"] = endpoint
        self.sock.request(weak_method(vq.post), typ, kwargs)
        event, d = vq.inq.Wait(self.timeout)
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
        el = EventLoop("SockSubscription.{}".format(endpoint))
        self.add_loop(el)
        el.add_event_handler(SType.Value, callback)
        # TODO: add errback
        # el.add_event_handler(SType.Error, callback)
        el.add_event_handler(SType.Return, el.loop_stop)
        self.sock.request(
            weak_method(el.post), SType.Subscribe, dict(endpoint=endpoint))
        return el

    def do_call(self, endpoint, *args, **kwargs):
        # Setup a ValueQueue that will handle the returns
        endpoint = ".".join((self.name, endpoint))
        assert len(args) == 0, \
            "Can't take positional args to methods"
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
            self.device_client_connected = False
        else:
            self.device_client_connected = True
