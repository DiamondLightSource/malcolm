import inspect
import functools
from collections import OrderedDict


from enum import Enum

from .attribute import HasAttributes, Attribute
from .statemachine import HasStateMachine
from .method import HasMethods, wrap_method
from .loop import HasLoops, TimerLoop
from .base import weak_method
from .vtype import VInt


def not_process_creatable(cls):
    cls.not_process_creatable.append(cls)
    return cls


class DState(Enum):
    # These are the states that our machine supports
    Fault, Idle, Configuring, Ready, Running, Rewinding, Paused, Aborting,\
        Aborted, Resetting = range(10)

    @classmethod
    def rest(cls):
        return [cls.Fault, cls.Idle, cls.Ready, cls.Aborted]

    @classmethod
    def canAbort(cls):
        return [cls.Idle, cls.Configuring, cls.Ready, cls.Running,
                cls.Rewinding, cls.Paused]

    @classmethod
    def canConfig(cls):
        return [cls.Idle, cls.Ready]

    @classmethod
    def canRun(cls):
        return [cls.Ready, cls.Paused]

    @classmethod
    def canReset(cls):
        return [cls.Fault, cls.Aborted]

    @classmethod
    def doneRewind(cls):
        return [cls.Fault, cls.Aborted, cls.Paused, cls.Ready]

    @classmethod
    def doneResume(cls):
        return [cls.Fault, cls.Running]

    def to_dict(self):
        return self.name


class DEvent(Enum):
    # These are the events that we will respond to
    Config, Run, Abort, Rewind, Reset, Changes = range(6)


@not_process_creatable
class Device(HasAttributes, HasMethods, HasStateMachine, HasLoops):
    _endpoints = "name,descriptor,tags,methods,stateMachine,attributes".split(
        ",")
    not_process_creatable = []

    def __init__(self, name, timeout=None):
        super(Device, self).__init__(name)
        # TODO: delete this?
        self.timeout = timeout
        self.add_stateMachine_transitions()
        self.add_all_attributes()
        self.add_methods()
        self.add_loop(TimerLoop("{}.uptime".format(self.name),
                                weak_method(self._inc_uptime), 1))

    def _inc_uptime(self):
        # pylint gets confused if we don't do the longhand...
        if self.attributes["uptime"].value is None:
            self.uptime = 0
        self.uptime += 1

    def add_stateMachine_transitions(self):
        pass

    def add_all_attributes(self):
        """Add all attributes to a device. Make sure you super() call this in
        subclasses"""
        self.add_attributes(
            uptime=Attribute(VInt, "Seconds since device was created"))

    def create_device(self, cls, name, *args, **kwargs):
        """Locally available method to create device, will be overridden if
        running under a process"""
        return cls(name, *args, **kwargs)

    def get_device(self, device):
        """If running under a process, this will allow devices to be connected to
        from the local process or DirectoryService"""
        raise AssertionError(
            "{}: Cannot get device {} as not running under Process"
            .format(self.name, device))

    @classmethod
    def subclasses(cls):
        """Return list of subclasses"""
        subclasses = OrderedDict([(cls.__name__, cls)])
        for s in cls.__subclasses__():
            for g in s.subclasses():
                if g.__name__ not in subclasses:
                    subclasses[g.__name__] = g
        return subclasses.values()

    @classmethod
    def baseclasses(cls):
        return [x for x in inspect.getmro(cls) if issubclass(x, Device)]

    @wrap_method()
    def exit(self):
        """Stop the event loop and destoy the device"""
        self.__del__()

    @property
    def state(self):
        return self.stateMachine.state

    def add_post_methods(self, events):
        for event in events:
            f = functools.partial(weak_method(self.stateMachine.post), event)
            setattr(self, "post_{}".format(event.name.lower()), f)

    def shortcuts(self, s, e):
        # Shortcut to all the self.do_ functions
        class do:
            pass
        for fname in dir(self):
            if fname.startswith("do_"):
                setattr(do, fname[3:], getattr(self, fname))

        # Shortcut to transition function, state list and event list
        t = self.stateMachine.transition
        return (do, t, s, e)

    def to_dict(self):
        """Serialize this object"""
        tags = []
        for x in self.baseclasses():
            tags.append("instance:{}".format(x.__name__))
        return super(Device, self).to_dict(
            tags=tags,
            descriptor=self.__doc__,
            attributes=getattr(self, "attributes", None),
            methods=getattr(self, "methods", None),
            stateMachine=getattr(self, "stateMachine", None))
