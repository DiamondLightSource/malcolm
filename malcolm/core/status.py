from timeStamp import TimeStamp
from collections import OrderedDict
import logging
from malcolm.core.traitsapi import HasTraits, Str, Any, Instance

log = logging.getLogger(__name__)


class Status(HasTraits):
    state = Any
    message = Str
    timeStamp = Instance(TimeStamp)

    def __init__(self, initial_state):
        self.states = list(initial_state.__class__)
        self.state = initial_state

    def update(self, message, state, timeStamp=None):
        assert state in self.states, \
            "State {} should be one of {}".format(state, self.states)
        self.state = state
        if message is not None:
            self.message = str(message)
        self.timeStamp = timeStamp or TimeStamp.now()

    def __repr__(self):
        a = ", ".join("{}={!r}".format(*x) for x in self.to_dict().items())        
        return "<Status({})>".format(a)

    def to_dict(self):
        d = OrderedDict(message=self.message)
        d.update(state=self.state)
        d.update(timeStamp=self.timeStamp)
        return d
