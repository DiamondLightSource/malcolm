import abc

from .method import wrap_method
from .attribute import Attribute
from .runnabledevice import RunnableDevice, DState, DEvent
from .vtype import VInt, VBool
import time


class PausableDevice(RunnableDevice):
    """Adds pause command to Device"""

    def add_stateMachine_transitions(self):
        super(PausableDevice, self).add_stateMachine_transitions()

        # some shortcuts for the state table
        do, t, s, e = self.shortcuts(DState, DEvent)

        # Ready
        t(s.Ready,     e.Rewind,  do.rewind,    s.Rewinding)
        # Running
        t(s.Running,   e.Rewind,  do.rewind,    s.Rewinding)
        # Rewinding
        t(s.Rewinding, e.Changes, do.rewinding, s.Rewinding, s.Ready, s.Paused)
        # Paused
        t(s.Paused,    e.Changes, do.paused,    s.Paused)
        t(s.Paused,    e.Run,     do.run,       s.Running)
        t(s.Paused,    e.Rewind,  do.rewind,    s.Rewinding)

    def add_all_attributes(self):
        super(PausableDevice, self).add_all_attributes()
        # Add attributes
        self.add_attributes(
            totalSteps=Attribute(VInt, "Readback of number of scan steps"),
            currentStep=Attribute(VInt, "Readback of current scan step"),
            stepsPerRun=Attribute(
                VInt, "Readback of steps that will be done each run"),
        )

    def _get_default_times(self, funcname=None):
        # If we have a cached version, use this
        if not hasattr(self, "_default_times"):
            # update defaults with our extra functions
            super(PausableDevice, self)._get_default_times().update(
                pauseTimeout=1,
                rewindTimeout=1,
                resumeTimeout=1,
            )
        # Now just return superclass result
        return super(PausableDevice, self)._get_default_times(funcname)

    @abc.abstractmethod
    def do_rewind(self, steps=None):
        """Start doing an pause with a rewind of steps.
        Return DState.Rewinding, message when started
        """

    @abc.abstractmethod
    def do_rewinding(self, value, changes):
        """Work out if the changes mean rewind is complete.
        Return None, message if it isn't.
        Return DState.Paused, message if it is, and we were Paused before
        Return DState.Ready, message if it is, and we were Ready before
        """

    def do_paused(self, value, changes):
        """Work out if the changes should constitute an error, and if so raise.
        Return None, None for no changes
        """
        return None, None

    @wrap_method(only_in=DState.Running,
                 block=Attribute(VBool, "Wait for function to complete?"))
    def pause(self, block=True):
        """Pause a run so that it can be resumed later. It blocks until the
        device is in a pause done state:
         * Normally it will return a DState.Paused Status
         * If the user aborts then it will return a DState.Aborted Status
         * If something goes wrong it will return a DState.Fault Status
        """
        self.post_rewind()
        if block:
            timeout = self._get_default_times("pause")
            self.wait_until(DState.doneRewind(), timeout=timeout)

    @wrap_method(only_in=DState.canRewind(),
                 steps=Attribute(VInt, "Number of steps to rewind by"),
                 block=Attribute(VBool, "Wait for function to complete?"))
    def rewind(self, steps, block=True):
        """Retrace a number of steps in the current scan. It blocks until the
        device is in pause done state:
         * Normally it will return a DState.Paused Status
         * If the user aborts then it will return a DState.Aborted Status
         * If something goes wrong it will return a DState.Fault Status
        """
        assert self.currentStep - steps > 0, \
            "Cannot rewind {} steps as we are only on step {}".format(
                steps, self.currentStep)
        self.post_rewind(steps)
        if block:
            timeout = self._get_default_times("rewind")
            self.wait_until(DState.doneRewind(), timeout=timeout)

    @wrap_method(only_in=DState.Paused,
                 block=Attribute(VBool, "Wait for function to complete?"))
    def resume(self, block=True):
        """Resume the current scan. It returns as soon as the device has
        continued to run:
         * Normally it will return a DState.Running Status
         * If something goes wrong it will return a DState.Fault Status
        """
        self.post_run()
        if block:
            timeout = self._get_default_times("resume")
            self.wait_until(DState.doneResume(), timeout=timeout)

    @wrap_method(only_in=DState.Ready,
                 block=Attribute(VBool, "Wait for function to complete?"))
    def run(self, block=True):
        """Start a configured device running. It blocks until the device is in a
        rest state:
         * Normally it will return a DState.Idle Status
         * If the device allows many runs from a single configure the it
           will return a DState.Ready Status
         * If the user aborts then it will return a DState.Aborted Status
         * If something goes wrong it will return a DState.Fault Status
        """
        self.post_run()
        if block:
            typical = self._get_default_times()["runTime"]
            extra = self._get_default_times("run") - typical
            while True:
                todo = 1 - float(self.currentStep) / self.totalSteps
                timeout = typical * todo + extra
                self.wait_until(
                    DState.rest() + [DState.Paused], timeout=timeout)
                if self.state in DState.rest():
                    return
                else:
                    self.wait_until(DState.rest() + [DState.Running],
                                    timeout=None)
                    if self.state != DState.Running:
                        return
