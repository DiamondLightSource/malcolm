import inspect

from enum import Enum

from .attribute import HasAttributes
from .stateMachine import HasStateMachine
from .method import HasMethods, wrap_method
from .loop import HasLoops
from malcolm.core.serialize import Serializable


class DState(Enum):
    # These are the states that our machine supports
    Fault, Idle, Configuring, Ready, Running, Pausing, Paused, Aborting,\
        Aborted, Resetting = range(10)

    @classmethod
    def rest(cls):
        return [cls.Fault, cls.Idle, cls.Ready, cls.Aborted]

    @classmethod
    def pausedone(cls):
        return [cls.Fault, cls.Aborted, cls.Paused]

    @classmethod
    def abortable(cls):
        return [cls.Configuring, cls.Ready, cls.Running, cls.Pausing,
                cls.Paused, cls.Resetting]

    @classmethod
    def configurable(cls):
        return [cls.Idle, cls.Ready]

    @classmethod
    def runnable(cls):
        return [cls.Ready, cls.Paused]

    @classmethod
    def resettable(cls):
        return [cls.Fault, cls.Aborted]

    def to_dict(self):
        choices = [e.name for e in self.__class__]
        d = dict(index=self.value, choices=choices)
        return d


class DEvent(Enum):
    # These are the messages that we will respond to
    Error, Reset, ResetSta, Config, ConfigSta, Run, RunSta, Abort, AbortSta, \
        Pause, PauseSta = range(11)


class Device(HasAttributes, HasMethods, HasStateMachine, HasLoops, Serializable):
    _endpoints = "name,descriptor,tags,methods,stateMachine,attributes".split(
        ",")

    def __init__(self, name, process, timeout=None):
        super(Device, self).__init__(name)
        self.timeout = timeout
        self.process = process
        self.add_attributes()

    def shortcuts(self):
        # Shortcut to all the self.do_ functions
        class do:
            pass
        for fname in dir(self):
            if fname.startswith("do_"):
                setattr(do, fname[3:], getattr(self, fname))

        # Shortcut to transition function, state list and event list
        t = self.stateMachine.transition
        s = DState
        e = DEvent
        return (do, t, s, e)

    def loop_run(self):
        self.add_methods()
        super(Device, self).loop_run()

    @wrap_method(only_in=DState)
    def exit(self):
        """Stop the event loop and destoy the device"""
        super(Device, self).loop_stop()
        super(Device, self).loop_wait()
        self.process.device_exited(self.name)

    def to_dict(self):
        """Serialize this object"""
        baseclasses = [x.__name__ for x in inspect.getmro(type(self))]
        return super(Device, self).to_dict(
            tags=baseclasses,
            descriptor=self.__doc__,
            attributes=getattr(self, "_attributes", None),
            methods=getattr(self, "_methods", None),
            stateMachine=getattr(self, "stateMachine", None))
