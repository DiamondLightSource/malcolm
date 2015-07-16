from command import command
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
        raise NotImplementedError

    def do_pausesta(self, event, pausesta):
        raise NotImplementedError

    @command(only_in=DState.Running)
    def pause(self):
        """Pause the current run. Will block until the device is in a rest
        state.
        """
        self.post(DEvent.Pause)
        self.wait_for_transition(DState.rest())
