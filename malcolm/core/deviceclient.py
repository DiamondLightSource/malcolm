import functools

from collections import OrderedDict

from .runnabledevice import DState
from .loop import ILoop, HasLoops, TimerLoop
from .base import weak_method
from .transport import SType
from .attribute import Attribute, HasAttributes
from .statemachine import StateMachine, HasStateMachine
from .alarm import Alarm
from .subscription import ClientSubscription
from .method import HasMethods
from .vtype import VBool
from malcolm.core.method import ClientMethod


class ValueQueue(ILoop):

    def loop_run(self):
        """Start the event loop running"""
        super(ValueQueue, self).loop_run()
        self.inq = self.cothread.EventQueue()

    def post(self, event, **kwargs):
        self.inq.Signal((event, kwargs))

    def loop_stop(self):
        """Signal the event loop to stop running and wait for it to finish"""
        self.inq.close()
        super(ValueQueue, self).loop_stop()

    def wait_for_return(self, timeout=None):
        event, d = self.inq.Wait(timeout)
        if event == SType.Return:
            return d.get("value", None)
        elif event == SType.Error:
            raise AssertionError(d["message"])
        else:
            raise AssertionError("Don't know what to do with {} {}"
                                 .format(event, d))


class DeviceClient(HasAttributes, HasMethods, HasStateMachine, HasLoops):
    _endpoints = "name,descriptor,tags,methods,stateMachine,attributes".split(
        ",")

    def __init__(self, name, sock, monitor=True):
        super(DeviceClient, self).__init__(name + "Client")
        self.devicename = name
        self.monitor = monitor
        self.sock = sock
        self.add_methods()
        self.add_loop(TimerLoop("{}.uptime".format(self.name),
                                weak_method(self._check_uptime), 1))

    def loop_run(self):
        super(DeviceClient, self).loop_run()
        self._reconnect()

    @property
    def state(self):
        return self.stateMachine.state

    def _reconnect(self):
        self._last_uptime = 0
        self._uptime_static = 0
        # Unsubscribe old subs
        for sub in self._loops:
            if type(sub) == ClientSubscription:
                sub.loop_stop()
        # Get the structure
        structure = self.do_get()
        # Update properties
        self.descriptor = structure.get("descriptor", "")
        self.tags = structure.get("tags", [])
        # Update attributes
        self.attributes = OrderedDict()
        # Add connection attribute
        self.add_attributes(
            deviceClientConnected=Attribute(VBool, "Is device reponsive?"))
        for aname, adata in structure.get("attributes", {}).items():
            self.make_attribute(aname, adata)
        # Update stateMachine
        if "stateMachine" in structure:
            sdata = structure["stateMachine"]
            keys = [s.name for s in DState]
            for state in sdata["states"]:
                assert state in keys, \
                    "DState mismatch: {} not in {}".format(state, keys)
            initial = DState.__members__[sdata["state"]]
            sm = StateMachine(self.name + ".stateMachine", initial)
            self.add_stateMachine(sm)
            sm.states = [DState.__members__[s] for s in sdata["states"]]

            def update(value):
                d = value
                state = DState.__members__[d["state"]]
                sm.update(state, d["message"], d.get("timeStamp", None))
            update(sdata)
            if self.monitor:
                self.do_subscribe(update, "stateMachine")
        # Update methods
        for mname, mdata in structure.get("methods", {}).items():
            m = self.make_method(mname, mdata)
            self.add_method(m)
        self.deviceClientConnected = True
        self.log_info("Device connected")

    def do_subscribe(self, callback, endpoint=None):
        if endpoint is not None:
            endpoint = ".".join((self.devicename, endpoint))
        else:
            endpoint = self.devicename
        el = ClientSubscription(self.sock, endpoint, callback)
        self.add_loop(el)
        return el

    def make_method(self, mname, mdata):
        def f(self, *args, **kwargs):
            return self.do_call(mname, *args, **kwargs)
        valid_states = mdata.get("validStates", None)
        if valid_states:
            valid_states = [DState.__members__[s] for s in valid_states]
        m = ClientMethod(mname, mdata.get("descriptor", mname), f,
                         valid_states)
        m.in_arguments = mdata.get("arguments", {})
        return m

    def make_attribute(self, aname, adata):
        endpoint = ".".join((self.devicename, "attributes", aname))

        weak_do_put = weak_method(self.do_put)

        def do_put(value):
            weak_do_put(endpoint, value)

        typ = adata["type"]
        attr = self.add_attribute(
            aname, Attribute(typ, adata["descriptor"],
                             tags=adata.get("tags", None)))
        attr.update = do_put

        def update(value, attr=attr):
            d = value
            value = d.get("value", None)
            alarm = d.get("alarm", None)
            if alarm is None:
                alarm = Alarm.ok()
            else:
                alarm = Alarm(**d["alarm"])
            Attribute.update(attr, value, alarm, d.get("timeStamp", None))
        update(adata)
        if self.monitor:
            self.do_subscribe(update, "attributes.{}".format(aname))

    def do_call(self, method, *args, **kwargs):
        # Call a method on this device
        assert len(args) == 0, \
            "Can't take positional args to methods"
        d = OrderedDict(endpoint=self.devicename)
        d.update(method=method)
        d.update(arguments=OrderedDict(sorted(kwargs.items())))
        # Setup a ValueQueue that will handle the returns
        vq = ValueQueue("Call({}.{})".format(self.name, method))
        vq.loop_run()
        self.sock.request(weak_method(vq.post), SType.Call, d)
        return vq.wait_for_return()

    def do_get(self, endpoint=None):
        if endpoint is not None:
            endpoint = ".".join((self.devicename, endpoint))
        else:
            endpoint = self.devicename
        d = OrderedDict(endpoint=endpoint)
        vq = ValueQueue("Get({})".format(endpoint))
        vq.loop_run()
        self.sock.request(weak_method(vq.post), SType.Get, d)
        return vq.wait_for_return()

    def do_put(self, endpoint, value):
        d = OrderedDict(endpoint=endpoint)
        d.update(value=value)
        vq = ValueQueue("Put({})".format(endpoint))
        vq.loop_run()
        self.sock.request(weak_method(vq.post), SType.Put, d)
        return vq.wait_for_return()

    def _check_uptime(self):
        if self._last_uptime >= self.uptime and self._uptime_static > 5:
            # Device inactive for 5s, must be dead
            self.log_info("Device inactive, reconnecting")
            self.deviceClientConnected = False
            for attr in self.attributes.values():
                Attribute.update(attr, alarm=Alarm.disconnected())
            self._reconnect()
        elif self._last_uptime >= self.uptime:
            self._uptime_static += 1
        else:
            self._last_uptime = self.uptime

    def to_dict(self):
        """Serialize this object"""
        return super(DeviceClient, self).to_dict(
            attributes=getattr(self, "attributes", None),
            methods=getattr(self, "methods", None),
            stateMachine=getattr(self, "stateMachine", None))
