from method import wrap_method
from device import DState, DEvent
from attribute import Attribute
from runnableDevice import RunnableDevice
from malcolm.core.traitsapi import Int


class PausableDevice(RunnableDevice):
    """Adds pause command to Device"""

    def __init__(self, name, timeout=None):
        # superclass init
        super(PausableDevice, self).__init__(name, timeout=timeout)

        # some shortcuts for the state table
        do, t, s, e = self.shortcuts()

        # add pause states
        t(s.Running,     e.Pause,     do.pause,     s.Pausing)
        t(s.Paused,      e.Pause,     do.pause,     s.Pausing)
        t(s.Pausing,     e.PauseSta,  do.pausesta,  s.Pausing, s.Paused)
        t(s.Paused,      e.Run,       do.run,       s.Running)

        # Add attributes
        self.add_attributes(
            total_steps=Attribute(Int, "Number of scan steps"),
            current_step=Attribute(Int, "Current scan step"),
            retrace_steps=Attribute(Int, "Number of steps to retrace by"),
        )

    def do_pause(self, event, steps=None):
        """Start doing an pause with a retrace of steps, arranging for a
        callback doing self.post(DEvent.PauseSta, pausesta) when progress has
        been made, where pausesta is any device specific abort status
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
        device is in a pause done state:
         * Normally it will return a DState.Paused Status
         * If the user aborts then it will return a DState.Aborted Status
         * If something goes wrong it will return a DState.Fault Status
        """
        self.post(DEvent.Pause, None)
        self.wait_for_transition(DState.pausedone())

    @wrap_method(only_in=DState.Paused)
    def retrace(self, retrace_steps):
        """Retrace a number of steps in the current scan. It blocks until the
        device is in pause done state:
         * Normally it will return a DState.Paused Status
         * If the user aborts then it will return a DState.Aborted Status
         * If something goes wrong it will return a DState.Fault Status
        """
        self.post(DEvent.Pause, retrace_steps)
        self.wait_for_transition(DState.pausedone())

    @wrap_method(only_in=DState.Paused)
    def resume(self):
        """Resume the current scan. It returns as soon as the device has
        continued to run:
         * Normally it will return a DState.Running Status
         * If something goes wrong it will return a DState.Fault Status
        """
        self.post(DEvent.Run)
        self.wait_for_transition([DState.Running, DState.Fault])
