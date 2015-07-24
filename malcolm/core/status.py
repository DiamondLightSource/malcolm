from timeStamp import TimeStamp
import logging
log = logging.getLogger(__name__)

class Status(object):

    def __init__(self, name, initial_state):
        self.name = name
        self.states = list(initial_state.__class__)
        self.state = initial_state
        self.message = ""
        self.percent = None
        self.timeStamp = None
        # state change listeners for each event
        self.listeners = []

    def update(self, message, percent=None, state=None, timeStamp=None):
        if state is not None:
            assert state in self.states, \
                "State {} should be one of {}".format(state, self.states)
            self.state = state
        self.message = str(message)
        if percent is None:
            self.percent = None
        else:
            self.percent = float(percent)
        self.timeStamp = timeStamp or TimeStamp.now()
        status = self.to_dict()
        for callback in self.listeners:
            try:
                callback(**status)
            except Exception, e:
                log.exception("{}: Got exception in status callback {}"\
                              .format(self.name, callback))

    def add_listener(self, callback):
        """Add a listener callback function to be called when we change state
        """
        assert callback not in self.listeners, \
            "Callback function {} already in callback list".format(
                callback)
        self.listeners.append(callback)

    def remove_listener(self, callback):
        """Remove listener callback function"""
        self.listeners.remove(callback)

    def to_dict(self):
        d = dict(message=self.message, state=self.state, timeStamp=self.timeStamp)
        if self.percent is not None:
            d["percent"] = self.percent
        return d