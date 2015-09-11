import functools

from collections import OrderedDict

from .device import Device, not_process_creatable
from .runnableDevice import DState
from .loop import ILoop, LState
from .serialize import SType
from .base import weak_method
from .attribute import Attribute
from .stateMachine import StateMachine
from .alarm import Alarm
from .subscription import ClientSubscription


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

    def wait_for_return(self, timeout=None):
        event, d = self.inq.Wait(timeout)
        if event == SType.Return:
            return d["value"]
        elif event == SType.Error:
            raise AssertionError(d["message"])
        else:
            raise AssertionError("Don't know what to do with {} {}"
                                 .format(event, d))


@not_process_creatable
class DeviceClient(Device):

    def __init__(self, name, sock, monitor=True, timeout=None):
        super(DeviceClient, self).__init__(name, timeout)
        self.monitor = monitor
        self.sock = sock
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
            f = functools.partial(weak_method(self.do_call), mname)
            f.__doc__ = mdata.get("descriptor", mname)
            f.func_name = str(mname)
            setattr(self, mname, f)

    def do_subscribe(self, callback, endpoint=None):
        if endpoint is not None:
            endpoint = ".".join((self.name, endpoint))
        else:
            endpoint = self.name
        el = ClientSubscription(self.sock, endpoint, callback)
        self.add_loop(el)
        return el

    def do_call(self, method, *args, **kwargs):
        # Call a method on this device
        assert len(args) == 0, \
            "Can't take positional args to methods"
        d = OrderedDict(endpoint=self.name)
        d.update(method=method)
        d.update(args=OrderedDict(sorted(kwargs.items())))
        # Setup a ValueQueue that will handle the returns
        vq = ValueQueue("Call({}.{})".format(self.name, method))
        vq.loop_run()
        self.sock.request(weak_method(vq.post), SType.Call, d)
        return vq.wait_for_return()

    def do_get(self, endpoint=None):
        if endpoint is not None:
            endpoint = ".".join((self.name, endpoint))
        else:
            endpoint = self.name
        d = OrderedDict(endpoint=endpoint)
        vq = ValueQueue("Get({})".format(endpoint))
        vq.loop_run()
        self.sock.request(weak_method(vq.post), SType.Get, d)
        return vq.wait_for_return()

    def do_ping(self):
        try:
            assert self.ping() == "pong"
        except:
            self.device_client_connected = False
        else:
            self.device_client_connected = True
