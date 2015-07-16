from enum import Enum
from stateMachine import StateMachine
from attribute import Attributes


class DState(Enum):
    # These are the states that our machine supports
    Fault, Idle, Configuring, Ready, Running, Pausing, Paused = range(7)

    @classmethod
    def rest(cls):
        return [cls.Fault, cls.Idle, cls.Ready, cls.Paused]

    @classmethod
    def abortable(cls):
        return [cls.Configuring, cls.Ready, cls.Running, cls.Pausing,
                cls.Paused]

    @classmethod
    def configurable(cls):
        return [cls.Idle, cls.Ready]

    @classmethod
    def runnable(cls):
        return [cls.Ready, cls.Paused]


class DEvent(Enum):
    # These are the messages that we will respond to
    Error, Reset, Config, ConfigSta, Run, RunSta, Abort, Pause, PauseSta \
        = range(9)


class Device(StateMachine):
    """External API wrapping a Device"""
    attributes = {}

    def __init__(self, name):
        # superclass init
        super(Device, self).__init__(name, DState.Idle, DState.Fault)

        # make the attributes object
        self.attributes = Attributes(self.attributes)

        # TODO: Register all publishable things with a comms object
        # self.comms = Comms(self)

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
        return getattr(self.attributes, attr)

    def __setattr__(self, attr, value):
        """If we have an attribute, then set it, otherwise set it as a local
        variable"""
        try:
            return setattr(self.attributes, attr, value)
        except (AttributeError, KeyError) as e:
            return object.__setattr__(self, attr, value)
