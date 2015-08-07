from malcolm.core import wrap_method, DState, DEvent, PausableDevice
from malcolm.core.stateMachine import StateMachine
from enum import Enum
from malcolm.core.attribute import Attribute


class SState(Enum):
    Idle, Ready, Acquiring = range(3)


class SEvent(Enum):
    Config, Start, Done, Abort, Status = range(5)


class DummyDetSim(StateMachine):

    def __init__(self, name):
        super(DummyDetSim, self).__init__(name, SState.Idle)
        # shortcuts
        s = SState
        e = SEvent
        t = self.transition
        # State table
        t([s.Idle, s.Ready], e.Config, self.do_config, s.Ready)
        t(s.Ready, e.Start, self.do_start, s.Acquiring)
        t(s.Acquiring, e.Status, self.do_status, s.Acquiring, s.Idle)
        t(s.Acquiring, e.Abort, self.do_abort, s.Acquiring)
        # Go
        self.start_event_loop()

    def do_config(self, event, nframes, exposure):
        self.nframes = nframes
        self.exposure = exposure

    def do_abort(self, event):
        self.need_abort = True

    def do_start(self, event):
        self.cothread.Spawn(self.acquire_task)

    def do_status(self, event):
        if self.nframes > 0 and not self.need_abort:
            self.status_message(
                "Completed a frame. {} frames left".format(self.nframes))
            return SState.Acquiring
        else:
            self.status_message("Finished")
            return SState.Idle

    def acquire_task(self):
        self.need_abort = False
        while self.nframes > 0 and not self.need_abort:
            self.cothread.Sleep(self.exposure)
            self.nframes -= 1
            self.post(SEvent.Status)


class DummyDet(PausableDevice):
    """Dummy detector for testing purposes"""

    def __init__(self, name, single=False):
        # TODO: add single step
        super(DummyDet, self).__init__(name)
        # Add the attributes
        self.attributes.add_attributes(
            nframes=Attribute(int, "Number of frames"),
            exposure=Attribute(float, "Detector exposure"),
        )
        self.single = single
        self.sim = DummyDetSim(name + "Sim")
        self.sim.add_listener(self.on_status)
        self.start_event_loop()

    @wrap_method(only_in=DState)
    def assert_valid(self, nframes, exposure):
        """Check whether the configuration parameters are valid or not. This set
        of parameters are checked in isolation, no device state is taken into
        account. It raises an error if the set of configuration parameters is
        invalid.
        """
        assert nframes > 0, "nframes {} should be > 0".format(nframes)
        assert exposure > 0.0, "exposure {} should be > 0.0".format(exposure)

    def do_reset(self, event):
        """Reset the underlying device"""
        self.status_message("Resetting")
        self.post(DEvent.ResetSta, "finished")

    def do_resetsta(self, event, resetsta):
        if resetsta == "finished":
            self.status_message("Reset complete")
            return DState.Idle
        else:
            return DState.Fault

    def on_status(self, state, message, timeStamp):
        """Respond to status updates from the sim state machine"""
        if self.state == DState.Configuring and state == SState.Ready:
            self.post(DEvent.ConfigSta, "finished")
        elif self.state == DState.Running and state == SState.Acquiring:
            self.post(DEvent.RunSta, self.sim.nframes)
        elif self.state == DState.Running and state == SState.Idle:
            self.post(DEvent.RunSta, "finished")
        elif self.state == DState.Pausing and state == SState.Acquiring:
            self.post(DEvent.PauseSta, "finishing")
        elif self.state == DState.Pausing and state == SState.Idle:
            self.post(DEvent.PauseSta, "finished")
        elif self.state == DState.Pausing and state == SState.Ready:
            self.post(DEvent.PauseSta, "configured")
        elif self.state == DState.Aborting and state == SState.Acquiring:
            self.post(DEvent.AbortSta, "finishing")
        elif self.state == DState.Aborting and state == SState.Idle:
            self.post(DEvent.AbortSta, "finished")
        else:
            print "Unhandled", state, message

    def do_config(self, event, nframes, exposure):
        """Check config params and send them to sim state machine"""
        self.nframes = nframes
        self.exposure = exposure
        self.sim.post(SEvent.Config, self.nframes, self.exposure)
        self.status_message("Configuring started")

    def do_configsta(self, event, configsta):
        """Receive configuration events and move to next state when finished"""
        assert configsta == "finished", "What is this '{}'".format(configsta)
        self.status_message("Configuring finished")
        return DState.Ready

    def do_run(self, event):
        """Start a run"""
        self.status_message("Starting run")
        self.sim.post(SEvent.Start)

    def do_runsta(self, event, runsta):
        """Receive run status events and move to next state when finished"""
        if runsta == "finished":
            self.status_message("Running in progress 100% done")
            return DState.Idle
        else:
            percent = (self.nframes - runsta) * 100 / self.nframes
            self.status_message("Running in progress {}% done".format(percent))
        return DState.Running

    def do_pause(self, event, steps):
        """Start a pause"""
        if self.state == DState.Running:
            self.sim.post(SEvent.Abort)
            self.status_message("Pausing started")
            self.frames_to_do = self.sim.nframes
        else:
            assert self.frames_to_do + steps <= self.nframes, \
                "Cannot retrace {} steps as we are only on step {}".format(
                    steps, self.nframes - self.frames_to_do)
            self.frames_to_do += steps
            self.status_message("Retracing started")
            self.post(DEvent.PauseSta, "finished")

    def do_pausesta(self, event, pausesta):
        """Receive run status events and move to next state when finished"""
        if pausesta == "finishing":
            # detector still doing the last frame
            self.status_message("Waiting for detector to stop")
        elif pausesta == "finished":
            # detector done, reconfigure it
            self.sim.post(SEvent.Config, self.frames_to_do, self.exposure)
            self.status_message("Reconfiguring detector for {} frames"
                                .format(self.frames_to_do))
        elif pausesta == "configured":
            # detector reconfigured, done
            self.status_message("Pausing finished")
            return DState.Paused
        else:
            raise Exception("What is: {}".format(pausesta))
        return DState.Pausing

    def do_abort(self, event):
        """Abort the machine"""
        self.status_message("Aborting")
        if self.sim.state == SState.Acquiring:
            self.sim.post(SEvent.Abort)
        else:
            self.post(DEvent.AbortSta, "finished")

    def do_abortsta(self, event, abortsta):
        if abortsta == "finishing":
            # detector still doing the last frame
            self.status_message("Waiting for detector to stop")
            return DState.Aborting
        elif abortsta == "finished":
            self.status_message("Aborted")
            return DState.Aborted
        else:
            raise Exception("What is: {}".format(abortsta))
