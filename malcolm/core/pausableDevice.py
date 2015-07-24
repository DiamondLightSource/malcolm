from method import wrap_method
from device import DState, DEvent
from runnableDevice import RunnableDevice


class PausableDevice(RunnableDevice):
    """Adds pause command to Device"""

    def __init__(self, name):
        # superclass init
        super(PausableDevice, self).__init__(name)

        # some shortcuts for the state table
        do, t, s, e = self.shortcuts()

        # add pause states
        t(s.Running,     e.Pause,     do.pause,     s.Pausing)
        t(s.Pausing,     e.PauseSta,  do.pausesta,  s.Pausing, s.Paused)
        t(s.Paused,      e.Run,       do.run,       s.Running)

    def do_pause(self, event):
        """Start doing an pause, arranging for a callback doing
        self.post(DEvent.PauseSta, pausesta) when progress has been made, where
        pausesta is any device specific abort status
        """
        raise NotImplementedError

    def do_pausesta(self, event, pausesta):
        """Examine pausesta for pause progress, returning DState.Pausing if still
        in progress or DState.Paused if done.
        """
        raise NotImplementedError

    @wrap_method(only_in=DState.Running)
    def pause(self):
        """Pause a run so that it can be resumed later. It blocks until the
        device is in a rest state:
         * Normally it will return a DState.Paused Status
         * If the user aborts then it will return a DState.Aborted Status
         * If something goes wrong it will return a DState.Fault Status
        """
        self.post(DEvent.Pause)
        self.wait_for_transition(DState.rest())
        return self.status
