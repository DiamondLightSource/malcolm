from enum import Enum

from malcolm.core import wrap_method, DState, PausableDevice, \
    Attribute, VInt, VBool, VDouble
from malcolm.core.base import weak_method
from malcolm.core.stateMachine import StateMachine
from malcolm.core.listener import HasListeners
from malcolm.core.loop import TimerLoop, HasLoops


class SState(Enum):
    Idle, Configuring, Ready, Acquiring = range(4)


class SEvent(Enum):
    Config, Start, Done, Abort, Status = range(5)


class DummyDetSim(StateMachine, HasListeners, HasLoops):

    def __init__(self, name):
        super(DummyDetSim, self).__init__(name, SState.Idle)

        # shortcuts
        s = SState
        e = SEvent
        t = self.transition
        # State table
        t([s.Idle, s.Ready], e.Config, self.do_config, s.Configuring, s.Ready)
        t(s.Configuring, e.Done, None, s.Ready)
        t(s.Ready, e.Start, self.do_start, s.Acquiring)
        t(s.Acquiring, e.Status, self.do_status, s.Acquiring, s.Idle)
        t(s.Acquiring, e.Abort, self.do_abort, s.Acquiring)

    def config_done(self):
        self.post(SEvent.Done)

    def do_config(self, nframes, exposure, configureSleep):
        self.nframes = nframes
        self.exposure = exposure
        if configureSleep > 0:
            self.add_loop(TimerLoop(
                "ConfigTimer", self.config_done, timeout=configureSleep, 
                retrigger=False))
            return SState.Configuring, "Configuring"
        else:
            return SState.Ready, "Ready"

    def do_abort(self):
        self.need_abort = True
        return SState.Acquiring, "Aborting..."

    def do_start(self):
        self.cothread.Spawn(self.acquire_task)
        return SState.Acquiring, "Starting..."

    def do_status(self):
        if self.nframes > 0 and not self.need_abort:
            message = "Completed a frame. {} frames left".format(self.nframes)
            return SState.Acquiring, message
        else:
            return SState.Idle, "Finished"

    def acquire_task(self):
        self.need_abort = False
        while self.nframes > 0 and not self.need_abort:
            self.cothread.Sleep(self.exposure)
            self.nframes -= 1
            try:
                self.post(SEvent.Status)
            except:
                break


class DummyDet(PausableDevice):
    """Dummy detector for testing purposes"""
    class_attributes = dict(
        single=Attribute(VBool, "Whether to single step or not"))

    def __init__(self, name, single=False, timeout=None):
        # TODO: add single step
        super(DummyDet, self).__init__(name, timeout=timeout)
        self.single = single
        self.sim = DummyDetSim(name + "Sim")
        self.sim.add_listener(weak_method(self.on_status))
        self.add_loop(self.sim)
        self.sim_post = self.sim.post

    def add_all_attributes(self):
        super(DummyDet, self).add_all_attributes()
        # Add the attributes
        self.add_attributes(
            nframes=Attribute(VInt, "Number of frames"),
            exposure=Attribute(VDouble, "Detector exposure"),
            configureSleep=Attribute(VDouble, "Time to sleep to simulate configure"),
        )

    @wrap_method()
    def validate(self, nframes, exposure, configureSleep=0.0):
        """Check whether the configuration parameters are valid or not. This set
        of parameters are checked in isolation, no device state is taken into
        account. It raises an error if the set of configuration parameters is
        invalid.
        """
        assert nframes > 0, "nframes {} should be > 0".format(nframes)
        assert exposure > 0.0, "exposure {} should be > 0.0".format(exposure)
        runTime = nframes * exposure
        return super(DummyDet, self).validate(locals())

    def do_reset(self):
        """Reset the underlying device"""
        self.post_resetsta("finished")
        return DState.Resetting, "Resetting..."

    def do_resetsta(self, resetsta):
        if resetsta == "finished":
            return DState.Idle, "Reset complete"
        else:
            return DState.Fault, "Unhandled reset message {}".format(resetsta)

    def on_status(self, status, changes):
        """Respond to status updates from the sim sim_state machine"""
        sim_state = status.state
        my_state = self.stateMachine.state
        if my_state == DState.Configuring and sim_state == SState.Ready:
            self.post_configsta("finished")
        elif my_state == DState.Running and sim_state == SState.Acquiring:
            self.post_runsta(self.sim.nframes)
        elif my_state == DState.Running and sim_state == SState.Idle:
            self.post_runsta("finished")
        elif my_state == DState.Pausing and sim_state == SState.Acquiring:
            self.post_pausesta("finishing")
        elif my_state == DState.Pausing and sim_state == SState.Idle:
            self.post_pausesta("finished")
        elif my_state == DState.Pausing and sim_state == SState.Ready:
            self.post_pausesta("configured")
        elif my_state == DState.Aborting and sim_state == SState.Acquiring:
            self.post_abortsta("finishing")
        elif my_state == DState.Aborting and sim_state == SState.Idle:
            self.post_abortsta("finished")
        else:
            print "Unhandled", status

    def do_config(self, **config_params):
        """Check config params and send them to sim state machine"""
        for param, value in config_params.items():
            self.attributes[param].update(value)
        self.sim_post(
            SEvent.Config, self.nframes, self.exposure, self.configureSleep)
        return DState.Configuring, "Configuring started"

    def do_configsta(self, configsta):
        """Receive configuration events and move to next state when finished"""
        assert configsta == "finished", "What is this '{}'".format(configsta)
        return DState.Ready, "Configuring finished"

    def do_run(self):
        """Start a run"""
        self.sim_post(SEvent.Start)
        return DState.Running, "Starting run"

    def do_runsta(self, runsta):
        """Receive run status events and move to next state when finished"""
        if runsta == "finished":
            return DState.Idle, "Running in progress 100% done"
        else:
            percent = (self.nframes - runsta) * 100 / self.nframes
            return None, "Running in progress {}% done".format(percent)

    def do_pause(self, steps):
        """Start a pause"""
        if self.stateMachine.state == DState.Running:
            self.sim_post(SEvent.Abort)
            self.frames_to_do = self.sim.nframes
            message = "Pausing started"
        else:
            assert self.frames_to_do + steps <= self.nframes, \
                "Cannot retrace {} steps as we are only on step {}".format(
                    steps, self.nframes - self.frames_to_do)
            self.frames_to_do += steps
            self.post_pausesta("finished")
            message = "Retracing started"
        return DState.Pausing, message

    def do_pausesta(self, pausesta):
        """Receive run status events and move to next state when finished"""
        state, message = None, None
        if pausesta == "finishing":
            # detector still doing the last frame
            message = "Waiting for detector to stop"
        elif pausesta == "finished":
            # detector done, reconfigure it
            self.sim_post(SEvent.Config, self.frames_to_do, self.exposure, 
                          self.configureSleep)
            message = "Reconfiguring detector for {} frames".format(
                self.frames_to_do)
        elif pausesta == "configured":
            # detector reconfigured, done
            state, message = DState.Paused, "Pausing finished"
        else:
            raise Exception("What is: {}".format(pausesta))
        return state, message

    def do_abort(self):
        """Abort the machine"""
        if self.sim.state == SState.Acquiring:
            self.sim_post(SEvent.Abort)
        else:
            self.post_abortsta("finished")
        return DState.Aborting, "Aborting"

    def do_abortsta(self, abortsta):
        if abortsta == "finishing":
            # detector still doing the last frame
            return DState.Aborting, "Waiting for detector to stop"
        elif abortsta == "finished":
            return DState.Aborted, "Aborted"
        else:
            raise Exception("What is: {}".format(abortsta))
