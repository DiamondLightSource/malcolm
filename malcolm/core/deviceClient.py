import functools

from .device import Device
from .loop import ILoop, LState, TimerLoop
from .serialize import SType
from .base import weak_method
from .attribute import Attribute
from malcolm.core.stateMachine import StateMachine
from malcolm.core.loop import EventLoop


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
        self.sock = sock
        # Every 10 seconds, do a heartbeat
        self.hb = TimerLoop(
            name + ".hb", weak_method(self.do_ping), timeout=10)
        # Add connection attribute
        self.add_attributes(
            device_client_connected=Attribute(bool, "Is device reponsive?"))
        # Get the structure
        structure = self.do_get()
        # Update attributes
        for aname, adata in structure.get("attributes", {}).items():
            self.add_attribute(
                aname, Attribute(adata["type"], adata["descriptor"]))
            if monitor:
                def update(d):
                    self.attributes[aname].update(
                        d["value"], d["alarm"], d["timeStamp"])
                self.do_subscribe(update, "attributes.{}".format(aname))
        # Update statemachine
        for sname, sdata in structure.get("attributes", {}).items():
            sm = StateMachine(self.name + sname, DState.Idle)
            self.add_stateMachine(sm)
            if monitor:
                def update(d):
                    self.stateMachine.update(
                        d["state"], d["message"], d["timeStamp"])
                self.do_subscribe(update, "stateMachine")
        # Update methods
        # TODO: do we need to use a Method here?
        for mname, mdata in structure.get("methods", {}).items():
            f = functools.partial(self.do_call, mname)
            f.__doc__ = mdata["descriptor"]
            f.func_name = str(mname)
            setattr(self, mname, f)

    def do_request(self, typ, endpoint, **kwargs):
        vq = ValueQueue("{}({})".format(typ, endpoint))
        self.add_loop(vq)
        self.sock.request(vq.post, typ, endpoint=endpoint, **kwargs)
        event, d = vq.inq.Wait()
        assert event == SType.Return
        ret = d["value"]
        vq.loop_stop()
        vq.loop_confirm_stopped()
        self.remove_loop(vq)
        return ret

    def do_subscribe(self, callback, endpoint=None):
        if endpoint is not None:
            endpoint = ".".join(self.name, endpoint)
        else:
            endpoint = self.name
        el = EventLoop("Subscribe({})".format(endpoint))
        self.add_loop(el)
        el.add_event_handler(SType.Value, callback)
        # TODO: add errback
        # el.add_event_handler(SType.Error, callback)
        el.add_event_handler(SType.Return, el.loop_stop)
        self.sock.request(el.post, SType.Subscribe, endpoint=endpoint)

    def do_call(self, endpoint, **kwargs):
        # Setup a ValueQueue that will handle the returns
        endpoint = ".".join(self.name, endpoint)
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
