import abc

from .method import wrap_method
from .device import DState, DEvent
from .attribute import Attribute
from .runnableDevice import RunnableDevice


class PausableDevice(RunnableDevice):
    """Adds pause command to Device"""

    def __init__(self, name, process, timeout=None):
        # superclass init
        super(PausableDevice, self).__init__(name, process, timeout=timeout)

        # some shortcuts for the state table
        do, t, s, e = self.shortcuts()

        # add pause states
        t(s.Running,     e.Pause,     do.pause,     s.Pausing)
        t(s.Paused,      e.Pause,     do.pause,     s.Pausing)
        t(s.Pausing,     e.PauseSta,  do.pausesta,  s.Pausing, s.Paused)
        t(s.Paused,      e.Run,       do.run,       s.Running)

        # Add attributes
        self.add_attributes(
            total_steps=Attribute(int, "Number of scan steps"),
            current_step=Attribute(int, "Current scan step"),
            retrace_steps=Attribute(int, "Number of steps to retrace by"),
        )

    @abc.abstractmethod
    def do_pause(self, steps=None):
        """Start doing an pause with a retrace of steps, arranging for a
        callback doing self.post(DEvent.PauseSta, pausesta) when progress has
        been made, where pausesta is any device specific abort status
        """
 
    @abc.abstractmethod
    def do_pausesta(self, pausesta):
        """Examine pausesta for pause progress, returning DState.Pausing if still
        in progress or DState.Paused if done.
        """
        raise NotImplementedError

    @wrap_method(only_in=DState.Running)
    def pause(self, timeout=None):
        """Pause a run so that it can be resumed later. It blocks until the
        device is in a pause done state:
         * Normally it will return a DState.Paused Status
         * If the user aborts then it will return a DState.Aborted Status
         * If something goes wrong it will return a DState.Fault Status
        """
        timeout = timeout or self.timeout
        self.stateMachine.post(DEvent.Pause, None)
        self.wait_until(DState.pausedone(), timeout=timeout)

    @wrap_method(only_in=DState.Paused)
    def retrace(self, retrace_steps, timeout=None):
        """Retrace a number of steps in the current scan. It blocks until the
        device is in pause done state:
         * Normally it will return a DState.Paused Status
         * If the user aborts then it will return a DState.Aborted Status
         * If something goes wrong it will return a DState.Fault Status
        """
        timeout = timeout or self.timeout
        self.stateMachine.post(DEvent.Pause, retrace_steps)
        self.wait_until(DState.pausedone(), timeout=timeout)

    @wrap_method(only_in=DState.Paused)
    def resume(self, timeout=None):
        """Resume the current scan. It returns as soon as the device has
        continued to run:
         * Normally it will return a DState.Running Status
         * If something goes wrong it will return a DState.Fault Status
        """
        timeout = timeout or self.timeout
        self.stateMachine.post(DEvent.Run)
        self.wait_until([DState.Running, DState.Fault], timeout=timeout)
