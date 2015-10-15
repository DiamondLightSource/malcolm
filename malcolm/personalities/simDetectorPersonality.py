import os

from malcolm.core import PausableDevice, DState, InstanceAttribute, \
    wrap_method, Attribute, VDouble, VString, VTable, VNumber
from malcolm.devices import SimDetector, Hdf5Writer, PositionPlugin


class SimDetectorPersonality(PausableDevice):
    class_attributes = dict(
        simDetector=InstanceAttribute(SimDetector, "SimDetector Device"),
        hdf5Writer=InstanceAttribute(Hdf5Writer, "Hdf5Writer Device"),
        positionPlugin=InstanceAttribute(
            PositionPlugin, "PositionPlugin Device"),
    )

    def __init__(self, name, simDetector, positionPlugin, hdf5Writer,
                 timeout=None):
        super(SimDetectorPersonality, self).__init__(name, timeout)
        self.simDetector = simDetector
        self.positionPlugin = positionPlugin
        self.hdf5Writer = hdf5Writer
        self.children = [simDetector, positionPlugin, hdf5Writer]
        for d in self.children:
            d.add_listener(self.on_child_state_change, "stateMachine.state")
        hdf5Writer.add_listener(
            self.on_uid_change, "attributes.uniqueId.value")

    def add_all_attributes(self):
        super(SimDetectorPersonality, self).add_all_attributes()
        self.add_attributes(
            # Configure
            exposure=Attribute(VDouble, "Exposure time for each frame"),
            period=Attribute(VDouble, "Time between the start of each frame"),
            positions=Attribute(
                VTable,
                "Position table, column headings are dimension names, " \
                "slowest changing first"),
            hdf5File=Attribute(VString, "HDF5 full file path to write"),
        )

    def on_uid_change(self, value, changes):
        if self.state == DState.Running:
            self.currentStep = value

    def on_child_state_change(self, state=None, changes=None):
        child_states = [d.state for d in self.children]
        child_running = [self.simDetector.acquire, self.positionPlugin.running,
                         self.hdf5Writer.capture]
        if self.state == DState.Configuring:
            self.post_configsta(child_states)
        elif self.state == DState.Running:
            self.post_runsta(child_states, child_running)
        elif self.state == DState.Aborting:
            self.post_abortsta(child_states)
        elif self.state == DState.Resetting:
            self.post_abortsta()

    def _get_num_images(self, positions):
        # Get the length of the first column of positions
        return len(positions[0][2])

    def _get_file_name_path(self, hdf5File):
        # Get the file name and path from the hdfFile
        return os.path.split(hdf5File)

    @wrap_method()
    def validate(self, exposure, positions, hdf5File, period=None):
        # Validate simDetector
        numImages = self._get_num_images(positions)
        sim_params = self.simDetector.validate(exposure, numImages, period)
        runTime = sim_params["runTime"]
        period = sim_params["period"]
        # Validate position plugin
        self.positionPlugin.validate(positions)
        # Validate hdf writer
        filePath, fileName = self._get_file_name_path(hdf5File)
        self.hdf5Writer.validate(filePath, fileName)
        return super(SimDetectorPersonality, self).validate(locals())

    def do_reset(self):
        """Check and attempt to clear any error state, arranging for a
        callback doing self.post(DEvent.ResetSta, resetsta) when progress has
        been made, where resetsta is any device specific reset status
        """
        action = False
        for d in self.children:
            if d.state not in DState.rest():
                action = True
                d.abort(block=False)
        if not action:
            # no abort action, trigger resetsta
            self.post_resetsta(None)
        self.wait_reset = True
        return DState.Resetting, "Aborting devices"

    def do_resetsta(self):
        """Examine configsta for configuration progress, returning
        DState.Resetting if still in progress, or DState.Idle if done.
        """
        child_states = [d.state for d in self.children]
        rest = [s in DState.rest() for s in child_states]
        if self.wait_reset and all(rest):
            self.wait_reset = False
            for d in self.children:
                if d.state in DState.canReset():
                    d.reset(block=False)
            return DState.Resetting, "Resetting devices"
        elif all(rest):
            nofault = [s != DState.Fault for s in child_states]
            assert all(nofault), \
                "Expected all not in fault, got {}".format(child_states)
            return DState.Idle, "Resetting done"
        else:
            todo = len(r for r in rest if not r)
            return DState.Resetting, "Waiting for {} plugins".format(todo)

    def do_config(self, **config_params):        
        """Start doing a configuration using config_params"""
        for d in self.children:
            assert d.state in DState.canConfig(), \
                "Child device {} in state {} is not canConfig"\
                .format(d, d.state)
        # Setup self
        for name, value in config_params.items():
            setattr(self, name, value)
        self.totalSteps = self._get_num_images(self.positions)
        self.stepsPerRun = 1
        self.currentStep = 0
        # Setup simDetector
        self.simDetector.configure(
            self.exposure, self.totalSteps, self.period, block=False)
        # Setup positionPlugin
        self.positionPlugin.configure(self.positions, block=False)
        self.wait_pos = True
        return DState.Configuring, "Configuring plugins"

    def do_configsta(self, child_states):
        """Do the next param in self.config_params, returning
        DState.Configuring if still in progress, or DState.Ready if done.
        """
        rest = [s in DState.rest() for s in child_states]
        if self.wait_pos and self.positionPlugin.state == DState.Ready:
            self.wait_pos = False
            # Setup hdfWriter
            filePath, fileName = self._get_file_name_path(self.hdf5File)
            numExtraDims = len(self.positions)
            posNames = ["", "", ""]
            extraDimSizes = [1, 1, 1]
            if numExtraDims == len(self.positionPlugin.dimensions):
                # This is a non-sparse scan so put in place
                for i, (name, _, _) in enumerate(self.positions):
                    posNames[i] = name
                    extraDimSizes[i] = self.positionPlugin.dimensions[i]
            elif [self.totalSteps] == self.positionPlugin.dimensions:
                # This is a sparse, so unroll to series of points
                posNames[0] = "n"
                extraDimSizes[0] = self.totalSteps
            else:
                raise AssertionError(
                    "Can't unify position number of columns {} with "
                    "positionPlugin dimensions {}"
                    .format(numExtraDims, self.positionPlugin.dimensions))
            self.hdf5Writer.configure(
                filePath, fileName,  numExtraDims, *posNames + extraDimSizes,
                block=False)
            return DState.Configuring, "Configuring hdfWriter"
        elif not self.wait_pos and min(rest):
            # All are in rest states
            ready = [s == DState.Ready for s in child_states]
            assert min(ready), \
                "Expected all ready, got {}".format(child_states)
            return DState.Ready, "Configuring finished"
        else:
            todo = len([r for r in rest if not r])
            return DState.Configuring, "Waiting for {} plugins".format(todo)

    def do_run(self):
        """Start doing a run, stopping when it calls back
        """
        for d in self.children:
            assert d.state in DState.canRun(), \
                "Child device {} in state {} is not canRun"\
                .format(d, d.state)
        self.hdf5Writer.run(block=False)
        self.positionPlugin.run(block=False)
        self.wait_det = True
        return DState.Running, "Starting plugins"

    def do_runsta(self, child_states, child_running):
        """If acquiring then return
        """
        nofault = [s != DState.Fault for s in child_states]
        assert all(nofault), \
            "Expected all not in fault, got {}".format(child_states)
        rest = [s in DState.rest() for s in child_states]
        if self.wait_det and child_running == [False, True, True]:
            self.wait_det = False
            self.simDetector.run(block=False)
            return DState.Running, "Starting simDetector"
        elif all(rest):
            # All are in rest states
            idle = [s == DState.Idle for s in child_states]
            assert all(idle), \
                "Expected all idle, got {}".format(child_states)
            return DState.Idle, "Running finished"
        else:
            todo = len([r for r in rest if not r])
            return DState.Running, "Waiting for {} plugins".format(todo)

    def do_abort(self):
        """Stop acquisition
        """
        for d in self.children:
            d.abort(block=False)
        return DState.Aborting, "Aborting started"

    def do_abortsta(self, child_states):
        """Check we finished
        """
        nofault = [s != DState.Fault for s in child_states]
        assert all(nofault), \
            "Expected all not in fault, got {}".format(child_states)
        rest = [s in DState.rest() for s in child_states]
        if all(rest):
            # All are in rest states
            aborted = [s == DState.Aborted for s in child_states]
            assert all(aborted), \
                "Expected all aborted, got {}".format(child_states)
            return DState.Aborted, "Aborting finished"
        else:
            todo = len(r for r in rest if not r)
            return DState.Running, "Waiting for {} plugins".format(todo)

    def do_pause(self, steps):
        """Start a pause"""
        if self.state == DState.Running:
            # Stop the detector and position plugin
            self.simDetector.abort(block=False)
            self.positionPlugin.abort(block=False)
            # Check how many frames we've produced
            self.last_done = self.hdf5Writer.uniqueId
            message = "Pausing started"
        else:
            assert self.last_done - steps > 0, \
                "Cannot retrace {} steps as we are only on step {}".format(
                    steps, self.last_done)
            self.last_done -= steps
            self.post_pausesta()
            message = "Retracing started"
        self.need_configure = True
        self.currentStep = self.last_done
        return DState.Pausing, message

    def do_pausesta(self):
        """Receive run status events and move to next state when finished"""
        interested = [self.simDetector, self.positionPlugin]
        child_states = [d.state for d in interested]
        rest = [s in DState.rest() for s in child_states]
        if self.need_configure and all(rest):
            self.need_configure = False
            nofault = [s != DState.Fault for s in child_states]
            assert all(nofault), \
                "Expected all not in fault, got {}".format(child_states)
            self.simDetector.configure(
                self.exposure, self.totalSteps - self.last_done, self.period,
                self.last_done, block=False)
            short = [[n, t, d[self.last_done:]] for n, t, d in self.positions]
            self.positionPlugin.configure(short, self.last_done + 1,
                                          block=False)
            return DState.Pausing, "Reconfiguring plugins"
        elif all(rest):
            return DState.Paused, "Retracing finished"
        else:
            todo = len(r for r in rest if not r)
            return DState.Pausing, "Waiting for {} plugins".format(todo)
