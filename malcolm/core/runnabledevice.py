import abc

from .method import wrap_method
from .configurabledevice import ConfigurableDevice, DState, DEvent
from .attribute import Attribute
from .vtype import VBool


class RunnableDevice(ConfigurableDevice):
    ConfigDoneState = DState.Ready

    def add_stateMachine_transitions(self):
        super(RunnableDevice, self).add_stateMachine_transitions()

        # some shortcuts for the state table
        do, t, s, e = self.shortcuts(DState, DEvent)

        # Ready
        t(s.Ready,       e.Changes,   do.ready,     s.Ready, s.Idle)
        t(s.Ready,       e.Config,    do.config,    s.Configuring)
        t(s.Ready,       e.Run,       do.run,       s.Running)
        # Running
        t(s.Running,     e.Changes,   do.running,   s.Running, s.Idle, s.Ready)

    def do_ready(self, value, changes):
        """Work out if the changes mean we are still ready for run.
        Return None, message if it is still ready.
        Return DState.Idle, message if it isn't still ready.
        """
        return None, None

    @abc.abstractmethod
    def do_run(self):
        """Start doing a run.
        Return DState.Running, message when started
        """

    @abc.abstractmethod
    def do_running(self, value, changes):
        """Work out if the changes mean running is complete.
        Return None, message if it isn't.
        Return DState.Idle, message if it is and we are all done
        Return DState.Ready, message if it is and we are partially done
        """

    def _get_default_times(self, funcname=None):
        # If we have a cached version, use this
        if not hasattr(self, "_default_times"):
            # update defaults with our extra functions
            super(RunnableDevice, self)._get_default_times().update(
                runTimeout=1,
                runTime=None,
            )
        # Now just return superclass result
        return super(RunnableDevice, self)._get_default_times(funcname)

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
            timeout = self._get_default_times("run")
            self.wait_until(DState.rest(), timeout=timeout)
            # TODO: timeout handling for paused


class HasConfigSequence(RunnableDevice):

    @abc.abstractmethod
    def make_config_sequence(self, **config_params):
        """Return a Sequence object that can be used for configuring"""

    def do_config(self, **config_params):
        """Start doing a configuration using config_params.
        Return DState.Configuring, message when started
        """
        self._sconfig = self.make_config_sequence(**config_params)
        item_done, msg = self._sconfig.start()
        if item_done:
            # Arrange for a callback to process the next item
            self.post_changes(None, None)
        return DState.Configuring, msg

    def do_configuring(self, value, changes):
        """Work out if the changes mean configuring is complete.
        Return None, message if it isn't.
        Return self.ConfigDoneState, message if it is.
        """
        running, item_done, msg = self._sconfig.process(value, changes)
        if running is False:
            # Finished
            return DState.Ready, "Configuring done"
        elif item_done:
            # Arrange for a callback to process the next item
            self.post_changes(None, None)
        # Still going
        return DState.Configuring, msg

    def do_ready(self, value, changes):
        """Work out if the changes mean we are still ready for run.
        Return None, message if it is still ready.
        Return DState.Idle, message if it isn't still ready.
        """
        mismatches = self._sconfig.mismatches()
        if mismatches:
            return DState.Idle, "Unconfigured: {}".format(mismatches)
        else:
            return None, None