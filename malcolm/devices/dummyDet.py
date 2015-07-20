from malcolm.core import command, DState, DEvent, PausableDevice
from malcolm.core.stateMachine import StateMachine
from enum import Enum
import cothread


class SState(Enum):
    Idle, Ready, Acquiring = range(3)


class SEvent(Enum):
    Config, Start, Done, Abort = range(4)


class DummyDetSim(StateMachine):

    def __init__(self, name):
        super(DummyDetSim, self).__init__(name, SState.Idle)
        # shortcuts
        s = SState
        e = SEvent
        t = self.transition
        # State table
        t(s.Idle, e.Config, self.do_config, s.Ready)
        t(s.Ready, e.Start, self.do_start, s.Acquiring)
        t(s.Acquiring, e.Done, None, s.Idle)
        t(s.Acquiring, e.Abort, self.do_abort, s.Acquiring)
        # Go
        self.start_event_loop()

    def do_config(self, event, nframes, exposure):
        self.nframes = nframes
        self.exposure = exposure

    def do_abort(self, event):
        self.need_abort = True

    def do_start(self, event):
        cothread.Spawn(self.acquire_task)

    def acquire_task(self):
        self.need_abort = False
        while self.nframes > 0 and not self.need_abort:
            cothread.Sleep(self.exposure)
            self.nframes -= 1
            self.notify_status(
                "Completed a frame. {} frames left".format(self.nframes))
        self.post(SEvent.Done)


class DummyDet(PausableDevice):

    attributes = dict(
        nframes=(int, "Number of frames"),
        exposure=(float, "Detector exposure"),
    )

    def __init__(self, name, single=False):
        # TODO: add single step
        super(DummyDet, self).__init__(name)
        self.single = single
        self.sim = DummyDetSim(name + "Sim")
        self.sim.add_listener(self.on_status)
        self.start_event_loop()

    @command(only_in=DState)
    def assert_valid(self, nframes, exposure):
        """Make sure params are valid"""
        assert nframes > 0, "nframes {} should be > 0".format(nframes)
        assert exposure > 0.0, "exposure {} should be > 0.0".format(exposure)

    def do_reset(self, event):
        """Reset the underlying device"""
        return DState.Idle

    def on_status(self, state, message, timeStamp, percent=None):
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
        else:
            print "Unhandled", state, message

    def do_config(self, event, nframes, exposure):
        """Check config params and send them to sim state machine"""
        self.nframes = nframes
        self.exposure = exposure
        self.sim.post(SEvent.Config, self.nframes, self.exposure)
        self.post(DEvent.ConfigSta, None)

    def do_configsta(self, event, configsta):
        """Receive configuration events and move to next state when finished"""
        if configsta is None:
            self.notify_status("Configuring started", 0)
        elif configsta == "finished":
            self.notify_status("Configuring finished", 100)
            return DState.Ready
        return DState.Configuring

    def do_run(self, event):
        """Start a run"""
        self.sim.post(SEvent.Start)

    def do_runsta(self, event, runsta):
        """Receive run status events and move to next state when finished"""
        if runsta == "finished":
            return DState.Idle
        else:
            percent = (self.nframes - runsta) * 100 / self.nframes
            self.notify_status("Running in progress", percent)
        return DState.Running

    def do_pause(self, event):
        """Start a pause"""
        self.sim.post(SEvent.Abort)
        self.post(DEvent.PauseSta, pausesta=None)

    def do_pausesta(self, event, pausesta):
        """Receive run status events and move to next state when finished"""
        if pausesta is None:
            # got here from do_pause
            percent = 0
        elif pausesta == "finishing":
            # detector still doing the last frame
            percent = 50
        elif pausesta == "finished":
            # detector done, reconfigure it
            percent = 75
            self.sim.post(SEvent.Config, self.sim.nframes, self.exposure)
        elif pausesta == "configured":
            # detector reconfigured, done
            self.notify_status("Pausing finished", 100)
            return DState.Paused
        self.notify_status("Pausing in progress", percent)
        return DState.Pausing

    def do_abort(self, event):
        """Abort the machine"""
        pass
