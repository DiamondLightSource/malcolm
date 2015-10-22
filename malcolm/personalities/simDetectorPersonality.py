import os

from malcolm.core import PausableDevice, DState, InstanceAttribute, \
    wrap_method, Attribute, VDouble, VString, VTable, SeqStateItem, \
    SeqFunctionItem, Sequence, SeqAttributeReadItem
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
        self._make_sconfig()
        self._make_srun()
        self._make_spause()
        hdf5Writer.add_listener(
            self.on_uid_change, "attributes.uniqueId.value")

    def on_uid_change(self, value, changes):
        if self.state == DState.Running:
            self.currentStep = value

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

    def _make_sconfig(self):
        # make some sequences for config
        seqItems = [
            SeqFunctionItem(
                "Configuring simDetector", self._configure_simDetector),
            SeqFunctionItem(
                "Configuring positionPlugin", self._configure_positionPlugin),
            SeqStateItem(
                "Wait for positionPlugin to configure", self.positionPlugin,
                DState.Ready, DState.rest()),
            SeqFunctionItem(
                "Configuring hdf5Writer", self._configure_hdf5Writer),
            SeqStateItem(
                "Wait for simDetector to configure", self.simDetector,
                DState.Ready, DState.rest()),
            SeqStateItem(
                "Wait for hdf5Writer to configure", self.hdf5Writer,
                DState.Ready, DState.rest()),
        ]
        # Add a configuring object
        self._sconfig = Sequence(
            self.name + ".SConfig", *seqItems)
        for c in self.children:
            c.add_listener(self._sconfig.on_change, "stateMachine.state")
        self._sconfig.add_listener(self.on_sconfig_change, "stateMachine")
        self.add_loop(self._sconfig)

    def on_sconfig_change(self, sm, changes):
        if self.state == DState.Configuring:
            self.post_configsta(sm.state, sm.message)
        elif self.state == DState.Ready and \
                sm.state != self._sconfig.SeqState.Done:
            self.post_error(sm.message)
        elif self.state == DState.Aborting:
            self.post_abortsta()

    def _make_srun(self):
        # make some sequences for config
        seqItems = [
            SeqFunctionItem(
                "Running hdf5Writer", self.hdf5Writer.run,
                block=False),
            SeqFunctionItem(
                "Running positionPlugin", self.positionPlugin.run,
                block=False),
            SeqAttributeReadItem(
                "Wait for hdf5Writer to run",
                self.hdf5Writer.attributes["capture"], True),
            SeqAttributeReadItem(
                "Wait for positionPlugin to run",
                self.positionPlugin.attributes["running"], True),
            SeqFunctionItem(
                "Running simDetector", self.simDetector.run,
                block=False),
            # TODO: need to wait for all of these...
            SeqStateItem(
                "Wait for simDetector to finish", self.simDetector,
                DState.Idle, DState.rest()),
            SeqStateItem(
                "Wait for positionPlugin to finish", self.positionPlugin,
                DState.Idle, DState.rest()),
            SeqStateItem(
                "Wait for hdf5Writer to finish", self.hdf5Writer,
                DState.Idle, DState.rest()),
        ]
        # Add a configuring object
        self._srun = Sequence(
            self.name + ".SRun", *seqItems)
        for c in self.children:
            c.add_listener(self._srun.on_change, "stateMachine.state")
        self.hdf5Writer.add_listener(
            self._srun.on_change, "attributes.capture")
        self.positionPlugin.add_listener(
            self._srun.on_change, "attributes.running")
        self._srun.add_listener(self.on_srun_change, "stateMachine")
        self.add_loop(self._srun)

    def on_srun_change(self, sm, changes):
        if self.state == DState.Running:
            self.post_runsta(sm.state, sm.message)
        elif self.state == DState.Aborting:
            self.post_abortsta()

    def _make_spause(self):
        # make some sequences for config
        seqItems = [
            SeqFunctionItem(
                "Stopping simDetector", self.simDetector.abort,
                block=False),
            SeqFunctionItem(
                "Stopping positionPlugin", self.positionPlugin.abort,
                block=False),
            SeqStateItem(
                "Wait for simDetector to stop", self.simDetector,
                DState.Aborted, DState.rest()),
            SeqStateItem(
                "Wait for positionPlugin to stop", self.positionPlugin,
                DState.Aborted, DState.rest()),
            SeqFunctionItem(
                "Configuring positionPlugin", self._configure_positionPlugin),
            SeqFunctionItem(
                "Configuring simDetector", self._configure_simDetector),
            SeqStateItem(
                "Wait for positionPlugin to configure", self.positionPlugin,
                DState.Ready, DState.rest()),
            SeqStateItem(
                "Wait for simDetector to configure", self.simDetector,
                DState.Ready, DState.rest()),
        ]
        # Add a configuring object
        self._spause = Sequence(
            self.name + ".SPause", *seqItems)
        for c in self.children:
            c.add_listener(self._spause.on_change, "stateMachine.state")
        self._spause.add_listener(self.on_spause_change, "stateMachine")
        self.add_loop(self._spause)

    def on_spause_change(self, sm, changes):
        if self.state == DState.Pausing:
            self.post_pausesta(sm.state, sm.message)
        elif self.state == DState.Aborting:
            self.post_abortsta()

    def _get_num_images(self, positions):
        # Get the length of the first column of positions
        return len(positions[0][2])

    def _get_file_name_path(self, hdf5File):
        # Get the file name and path from the hdfFile
        return os.path.split(hdf5File)

    def _configure_simDetector(self):
        self.simDetector.configure(
            self.exposure, self.totalSteps - self.last_done, self.period,
            self.last_done, block=False)

    def _configure_positionPlugin(self):
        if self.last_done > 0:
            positions = []
            for n, t, d in self.positions:
                positions.append([n, t, d[self.last_done:]])
        else:
            positions = self.positions
        self.positionPlugin.configure(
            positions, self.last_done + 1, self.simDetector.portName,
            block=False)

    def _configure_hdf5Writer(self):
        assert self.positionPlugin.state == DState.Ready, \
            "Position plugin isn't ready"
        filePath, fileName = self._get_file_name_path(self.hdf5File)
        numExtraDims = len(self.positions)
        posNames = ["", "", ""]
        extraDimSizes = [1, 1, 1]
        if numExtraDims == len(self.positionPlugin.dimensions):
            # This is a non-sparse scan so put in place
            for i, (name, _, _) in enumerate(self.positions):
                posNames[i] = name + "_index"
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
            filePath, fileName,  numExtraDims - 1, *posNames + extraDimSizes,
            arrayPort=self.positionPlugin.portName, block=False)

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
                "Child device {} in state {} is not configurable"\
                .format(d, d.state)
        assert self._sconfig.state in self._sconfig.rest_states(), \
            "Can't configure sub-state machine in {} state" \
            .format(self._sconfig.state)
        # Setup self
        for name, value in config_params.items():
            setattr(self, name, value)
        self.totalSteps = self._get_num_images(self.positions)
        self.stepsPerRun = 1
        self.currentStep = 0
        self.last_done = 0
        # Start the sequence
        self._sconfig.start(config_params)
        return DState.Configuring, "Started configuring"

    def do_configsta(self, state, message):
        """Do the next param in self.config_params, returning
        DState.Configuring if still in progress, or DState.Ready if done.
        """
        if state in self._sconfig.rest_states():
            assert state == self._sconfig.SeqState.Done, \
                "Configuring failed: {}".format(message)
            state = DState.Ready
        else:
            state = DState.Configuring
        return state, message

    def do_run(self):
        """Start doing a run, stopping when it calls back
        """
        for d in self.children:
            assert d.state in DState.canRun(), \
                "Child device {} in state {} is not canRun"\
                .format(d, d.state)
        assert self._srun.state in self._srun.rest_states(), \
            "Can't configure sub-state machine in {} state" \
            .format(self._srun.state)
        # Start the sequence
        self._srun.start()
        return DState.Running, "Starting running"

    def do_runsta(self, state, message):
        """If acquiring then return
        """
        if state in self._srun.rest_states():
            assert state == self._srun.SeqState.Done, \
                "Running failed: {}".format(message)
            state = DState.Idle
        else:
            state = DState.Running
        return state, message

    def do_abort(self):
        """Stop acquisition
        """
        if self.state == DState.Configuring:
            if self._sconfig.state not in self._sconfig.rest_states():
                # Abort configure
                self._sconfig.abort()
            else:
                # Statemachine already done, nothing to do
                self.post_abortsta()
        elif self.state == DState.Running:
            # Abort run
            self._srun.abort()
            for d in self.children:
                if d.state in DState.canAbort():
                    d.abort(block=False)
        elif self.state == DState.Pausing:
            # Abort pause
            self._spause.abort()
            for d in self.children:
                if d.state in DState.canAbort():
                    d.abort(block=False)
        return DState.Aborting, "Aborting started"

    def do_abortsta(self):
        """Check we finished
        """
        child_states = [c.state for c in self.children]
        rest = [s in DState.rest() for s in child_states]
        if all(rest):
            # All are in rest states
            aborted = [s == DState.Aborted for s in child_states]
            assert all(aborted), \
                "Expected all aborted, got {}".format(child_states)
            return DState.Aborted, "Aborting finished"
        else:
            # No change
            return None, None

    def do_pause(self, steps):
        """Start a pause"""
        if self.state == DState.Running:
            # Check how many frames we've produced
            self.last_done = self.hdf5Writer.uniqueId
            message = "Pausing started"
        else:
            assert self.last_done - steps > 0, \
                "Cannot retrace {} steps as we are only on step {}".format(
                    steps, self.last_done)
            self.last_done -= steps
            message = "Retracing started"
        self.currentStep = self.last_done
        # Start sequence
        self._spause.start()
        return DState.Pausing, message

    def do_pausesta(self, state, message):
        """Receive run status events and move to next state when finished"""
        if state in self._spause.rest_states():
            assert state == self._spause.SeqState.Done, \
                "Pausing failed: {}".format(message)
            state = DState.Paused
        else:
            state = DState.Pausing
        return state, message
