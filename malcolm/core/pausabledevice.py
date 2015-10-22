import abc

from .method import wrap_method
from .attribute import Attribute
from malcolm.core.runnabledevice import RunnableDevice, DState, DEvent
from .vtype import VInt


class PausableDevice(RunnableDevice):
    """Adds pause command to Device"""

    def __init__(self, name, timeout=None):
        # superclass init
        super(PausableDevice, self).__init__(name, timeout=timeout)

        # some shortcuts for the state table
        do, t, s, e = self.shortcuts(DState, DEvent)

        # add pause states
        t(s.Running,     e.Pause,     do.pause,     s.Pausing)
        t(s.Paused,      e.Pause,     do.pause,     s.Pausing)
        t(s.Pausing,     e.PauseSta,  do.pausesta,  s.Pausing, s.Paused)
        t(s.Paused,      e.Run,       do.run,       s.Running)

    def add_all_attributes(self):
        super(PausableDevice, self).add_all_attributes()
        # Add attributes
        self.add_attributes(
            totalSteps=Attribute(VInt, "Readback of number of scan steps"),
            currentStep=Attribute(VInt, "Readback of current scan step"),
            stepsPerRun=Attribute(
                VInt, "Readback of steps that will be done each run"),
            retraceSteps=Attribute(VInt, "Number of steps to retrace by"),
        )

    def _get_default_times(self, funcname=None):
        # If we have a cached version, use this
        if not hasattr(self, "_default_times"):
            # update defaults with our extra functions
            super(PausableDevice, self)._get_default_times().update(
                pauseTimeout=1,
                retraceTimeout=1,
                resumeTimeout=1,
            )
        # Now just return superclass result
        return super(PausableDevice, self)._get_default_times(funcname)

    @abc.abstractmethod
    def do_pause(self, steps=None):
        """Start doing an pause with a retrace of steps, arranging for a
        callback doing self.post_pausesta(pausesta) when progress has
        been made, where pausesta is any device specific abort status
        """

    @abc.abstractmethod
    def do_pausesta(self, pausesta):
        """Examine pausesta for pause progress, returning DState.Pausing if still
        in progress or DState.Paused if done.
        """
        raise NotImplementedError

    @wrap_method(only_in=DState.Running)
    def pause(self, block=True):
        """Pause a run so that it can be resumed later. It blocks until the
        device is in a pause done state:
         * Normally it will return a DState.Paused Status
         * If the user aborts then it will return a DState.Aborted Status
         * If something goes wrong it will return a DState.Fault Status
        """
        self.post_pause(None)
        if block:
            timeout = self._get_default_times("pause")
            self.wait_until(DState.donePause(), timeout=timeout)

    @wrap_method(only_in=DState.Paused)
    def retrace(self, retraceSteps, block=True):
        """Retrace a number of steps in the current scan. It blocks until the
        device is in pause done state:
         * Normally it will return a DState.Paused Status
         * If the user aborts then it will return a DState.Aborted Status
         * If something goes wrong it will return a DState.Fault Status
        """
        self.post_pause(retraceSteps)
        if block:
            timeout = self._get_default_times("retrace")
            self.wait_until(DState.donePause(), timeout=timeout)

    @wrap_method(only_in=DState.Paused)
    def resume(self, block=True):
        """Resume the current scan. It returns as soon as the device has
        continued to run:
         * Normally it will return a DState.Running Status
         * If something goes wrong it will return a DState.Fault Status
        """
        self.post_run()
        if block:
            timeout = self._get_default_times("resume")
            self.wait_until([DState.Running, DState.Fault], timeout=timeout)
