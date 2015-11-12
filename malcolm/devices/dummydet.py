from enum import Enum

from malcolm.core import wrap_method, DState, PausableDevice, \
    Attribute, VInt, VBool, VDouble
from malcolm.core.base import weak_method
from malcolm.core.statemachine import StateMachine
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
        self.sim.add_listener(self.post_changes)
        self.add_loop(self.sim)
        self.sim_post = self.sim.post

    def add_all_attributes(self):
        super(DummyDet, self).add_all_attributes()
        # Add the attributes
        self.add_attributes(
            nframes=Attribute(VInt, "Number of frames"),
            exposure=Attribute(VDouble, "Detector exposure"),
            configureSleep=Attribute(
                VDouble, "Time to sleep to simulate configure"),
        )

    @wrap_method()
    def validate(self, nframes, exposure, configureSleep=0.0):
        """Check whether a set of configuration parameters is valid or not. Each
        parameter name must match one of the names in self.attributes. This set
        of parameters should be checked in isolation, no device state should be
        taken into account. It is allowed from any DState and raises an error
        if the set of configuration parameters is invalid. It should return
        some metrics on the set of parameters as well as the actual parameters
        that should be used, e.g.
        {"runTime": 1.5, arg1=2, arg2="arg2default"}
        """
        assert nframes > 0, "nframes {} should be > 0".format(nframes)
        assert exposure > 0.0, "exposure {} should be > 0.0".format(exposure)
        runTime = nframes * exposure
        return super(DummyDet, self).validate(locals())

    def do_config(self, **config_params):
        """Start doing a configuration using config_params.
        Return DState.Configuring, message when started
        """
        for param, value in config_params.items():
            self.attributes[param].update(value)
        self.currentStep = 0
        self.totalSteps = self.nframes
        self.sim_post(
            SEvent.Config, self.nframes, self.exposure, self.configureSleep)
        return DState.Configuring, "Configuring started"

    def do_configuring(self, status, changes):
        """Work out if the changes mean configuring is complete.
        Return None, message if it isn't.
        Return self.ConfigDoneState, message if it is.
        """
        if status.state == SState.Ready:
            return DState.Ready, "Configuring finished"
        else:
            return None, None

    def do_run(self):
        """Start doing a run.
        Return DState.Running, message when started
        """
        self.sim_post(SEvent.Start)
        return DState.Running, "Starting run"

    def do_running(self, status, changes):
        """Work out if the changes mean running is complete.
        Return None, message if it isn't.
        Return DState.Idle, message if it is and we are all done
        Return DState.Ready, message if it is and we are partially done
        """
        self.currentStep = (self.nframes - self.sim.nframes)
        if status.state == SState.Acquiring:
            percent = self.currentStep * 100 / self.nframes
            return None, "Running in progress {}% done".format(percent)
        elif status.state == SState.Idle:
            return DState.Idle, "Running in progress 100% done"
        else:
            raise Exception("Can't handle: {}".format(status.state))

    def do_rewind(self, steps=None):
        """Start doing an pause with a rewind of steps.
        Return DState.Rewinding, message when started
        """
        if self.stateMachine.state == DState.Running:
            self.sim_post(SEvent.Abort)
            self.frames_to_do = self.sim.nframes
            message = "Pausing started"
        else:
            assert self.frames_to_do + steps <= self.nframes, \
                "Cannot retrace {} steps as we are only on step {}".format(
                    steps, self.nframes - self.frames_to_do)
            self.frames_to_do += steps
            self.post_changes(self.stateMachine, None)
            message = "Retracing started"
        return DState.Rewinding, message

    def do_rewinding(self, status, changes):
        """Work out if the changes mean rewind is complete.
        Return None, message if it isn't.
        Return DState.Paused, message if it is, and we were Paused before
        Return DState.Ready, message if it is, and we were Ready before
        """
        state, message = None, None
        if status.state == SState.Acquiring:
            # detector still doing the last frame
            message = "Waiting for detector to stop"
        elif status.state == SState.Idle:
            # detector done, reconfigure it
            self.sim_post(SEvent.Config, self.frames_to_do, self.exposure,
                          self.configureSleep)
            message = "Reconfiguring detector for {} frames".format(
                self.frames_to_do)
        elif status.state == SState.Ready:
            # detector reconfigured, done
            state, message = DState.Paused, "Pausing finished"
        else:
            raise Exception("Can't handle: {}".format(status.state))
        return state, message

    def do_abort(self):
        """Start doing an abort.
        Return DState.Aborting, message when started
        """
        if self.sim.state == SState.Acquiring:
            self.sim_post(SEvent.Abort)
        else:
            self.post_changes(self.sim.stateMachine, None)
        return DState.Aborting, "Aborting"

    def do_aborting(self, status, changes):
        """Work out if the changes mean aborting is complete.
        Return None, message if it isn't.
        Return DState.Aborted, message if it is.
        """
        if status.state == SState.Acquiring:
            # detector still doing the last frame
            return DState.Aborting, "Waiting for detector to stop"
        elif status.state == SState.Idle:
            return DState.Aborted, "Aborted"
        else:
            raise Exception("Can't handle: {}".format(status.state))

    def do_reset(self):
        """Start doing a reset from aborted or fault state.
        Return DState.Resetting, message when started
        """
        self.post_changes(self.sim.stateMachine, None)
        return DState.Resetting, "Resetting..."

    def do_resetting(self, status, changes):
        """Work out if the changes mean resetting is complete.
        Return None, message if it isn't.
        Return DState.Idle, message if it is.
        """
        return DState.Idle, "Reset complete"
