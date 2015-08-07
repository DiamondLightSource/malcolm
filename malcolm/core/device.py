from enum import Enum
from stateMachine import StateMachine
from attribute import Attributes
from method import Method, wrap_method
from collections import OrderedDict


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


class Device(StateMachine):
    """External API wrapping a Device"""

    def __init__(self, name):
        # superclass init
        super(Device, self).__init__(name, DState.Idle, DState.Fault)

        # make the attributes object
        self.attributes = Attributes()

    def start_event_loop(self):
        # dict of Method wrappers to @wrap_method decorated methods
        self.methods = Method.describe_methods(self)
        super(Device, self).start_event_loop()

    def shortcuts(self):
        # Shortcut to all the self.do_ functions
        class do:
            pass
        for fname in dir(self):
            if fname.startswith("do_"):
                setattr(do, fname[3:], getattr(self, fname))

        # Shortcut to transition function, state list and event list
        t = self.transition
        s = DState
        e = DEvent
        return (do, t, s, e)

    def __getattr__(self, attr):
        """If we haven't defined a class attribute, then get its value from 
        the self.attributes object"""
        if hasattr(self, "attributes"):
            return getattr(self.attributes, attr)
        else:
            raise KeyError("No attributes defined")

    def __setattr__(self, attr, value):
        """If we have an attribute, then set it, otherwise set it as a local
        variable"""
        try:
            return setattr(self.attributes, attr, value)
        except (AttributeError, KeyError) as e:
            return object.__setattr__(self, attr, value)

    @wrap_method(only_in=DState)
    def exit(self):
        """Stop the event loop and destroy the device"""
        self.inq.close()
        self.event_loop_proc.Wait()

    def to_dict(self):
        d = OrderedDict(name=self.name)
        d.update(classname=type(self).__name__)
        d.update(descriptor=self.__doc__)
        d.update(methods=self.methods)
        d.update(status=self.status)
        d.update(attributes=self.attributes)
        return d
