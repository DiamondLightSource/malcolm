import abc


from .method import wrap_method
from .base import weak_method
from .device import Device, DState, DEvent
from .statemachine import StateMachine
from .attribute import Attribute
from .vtype import VBool


class ConfigurableDevice(Device):
    ConfigDoneState = DState.Idle

    def add_stateMachine_transitions(self):
        # Make a stateMachine
        sm = StateMachine(self.name + ".stateMachine", DState.Idle,
                          DState.Fault)
        self.add_stateMachine(sm)

        # some shortcuts for the state table
        do, t, s, e = self.shortcuts(DState, DEvent)

        # Override the error handler of the stateMachine
        sm.do_error = weak_method(self.do_error)

        # Configuring done transition different for subclasses
        Configured = self.ConfigDoneState
        # Idle
        t(s.Idle,        e.Changes, do.idle,        s.Idle)
        t(s.Idle,        e.Config,  do.config,      s.Configuring)
        # Configuring
        t(s.Configuring, e.Changes, do.configuring, s.Configuring, Configured)
        # canAbort
        t(s.canAbort(),  e.Abort,   do.abort,       s.Aborting)
        # Aborting
        t(s.Aborting,    e.Changes, do.aborting,    s.Aborting, s.Aborted)
        # Aborted
        t(s.Aborted,     e.Changes, do.aborted,     s.Resetting)
        t(s.Aborted,     e.Reset,   do.reset,       s.Resetting)
        # Resetting
        t(s.Resetting,   e.Changes, do.resetting,   s.Resetting, s.Idle)
        # Fault
        t(s.Fault,       e.Changes, do.fault,       s.Fault, s.Idle)
        t(s.Fault,       e.Reset,   do.reset,       s.Resetting)

        # Add some post methods
        self.add_post_methods(list(DEvent))

    def do_error(self, error):
        """Handle an error"""
        return DState.Fault, str(error)

    def do_idle(self, value, changes):
        """Work out if the changes should constitute an error, and if so raise.
        Return None, None for no changes
        """
        return None, None

    @abc.abstractmethod
    def do_config(self, **config_params):
        """Start doing a configuration using config_params.
        Return DState.Configuring, message when started
        """

    @abc.abstractmethod
    def do_configuring(self, value, changes):
        """Work out if the changes mean configuring is complete.
        Return None, message if it isn't.
        Return self.ConfigDoneState, message if it is.
        """

    @abc.abstractmethod
    def do_abort(self):
        """Start doing an abort.
        Return DState.Aborting, message when started
        """

    @abc.abstractmethod
    def do_aborting(self, value, changes):
        """Work out if the changes mean aborting is complete.
        Return None, message if it isn't.
        Return DState.Aborted, message if it is.
        """

    def do_aborted(self, value, changes):
        """Work out if the changes should constitute an error, and if so raise.
        Return None, None for no changes
        """
        return None, None

    @abc.abstractmethod
    def do_reset(self):
        """Start doing a reset from aborted or fault state.
        Return DState.Resetting, message when started
        """

    @abc.abstractmethod
    def do_resetting(self, value, changes):
        """Work out if the changes mean resetting is complete.
        Return None, message if it isn't.
        Return DState.Idle, message if it is.
        """

    def do_fault(self, value, changes):
        """Work out if the changes mean an error has cleared.
        Return DState.Idle, message if it has.
        Return None, None for no change.
        """
        return None, None

    def _get_default_times(self, funcname=None):
        # If we have a cached version, use this
        if not hasattr(self, "_default_times"):
            self._default_times = dict(
                abortTimeout=1,
                resetTimeout=1,
                configureTimeout=1,
                runTimeout=1,
                runTime=None,
            )
        if funcname is None:
            return self._default_times
        else:
            return self._default_times[funcname + "Timeout"]

    @abc.abstractmethod
    def validate(self, params):
        """Check whether a set of configuration parameters is valid or not. Each
        parameter name must match one of the names in self.attributes. This set
        of parameters should be checked in isolation, no device state should be
        taken into account. It is allowed from any DState and raises an error
        if the set of configuration parameters is invalid. It should return
        some metrics on the set of parameters as well as the actual parameters
        that should be used, e.g.
        {"runTime": 1.5, arg1=2, arg2="arg2default"}
        """
        times = self._get_default_times()
        # get rid of unrecognised keys
        for key in params.keys():
            if key not in self.attributes and key not in times:
                if "timeout" in key.lower():
                    self.log_warning(
                        "Possible mis-spelt keyword {}. Could be one of {}"
                        .format(key, times.keys()))
                params.pop(key)
        # add in default times
        for key, time in times.items():
            if key not in params:
                params[key] = time
        return params

    @wrap_method(only_in=DState.canConfig(), arguments_from=validate,
                 block=Attribute(VBool, "Wait for function to complete?"))
    def configure(self, block=True, **params):
        """Assert params are valid, then use them to configure a device for a run.
        It blocks until the device is in a rest state:
         * Normally it will return a DState.Configured Status
         * If the user aborts then it will return a DState.Aborted Status
         * If something goes wrong it will return a DState.Fault Status
        """
        valid_params = self.validate(**params)
        # update default timeouts from results
        default_times = self._get_default_times()
        for key in default_times:
            if key in valid_params:
                default_times[key] = valid_params.pop(key)
        # clamp runTimeout
        if default_times["runTimeout"] < default_times["runTime"]:
            default_times["runTimeout"] = default_times["runTime"] * 2
        self.post_config(**valid_params)
        if block:
            timeout = self._get_default_times("configure")
            self.wait_until(DState.rest(), timeout=timeout)

    @wrap_method(only_in=DState.canAbort(),
                 block=Attribute(VBool, "Wait for function to complete?"))
    def abort(self, block=True):
        """Abort configuration or abandon the current run whether it is
        running or paused. It blocks until the device is in a rest state:
         * Normally it will return a DState.Aborted Status
         * If something goes wrong it will return a DState.Fault Status
        """
        self.post_abort()
        if block:
            timeout = self._get_default_times("abort")
            self.wait_until(DState.rest(), timeout=timeout)

    @wrap_method(only_in=DState.canReset(),
                 block=Attribute(VBool, "Wait for function to complete?"))
    def reset(self, block=True):
        """Try and reset the device into DState.Idle. It blocks until the
        device is in a rest state:
         * Normally it will return a DState.Idle Status
         * If something goes wrong it will return a DState.Fault Status
        """
        self.post_reset()
        if block:
            timeout = self._get_default_times("reset")
            self.wait_until(DState.rest(), timeout=timeout)

