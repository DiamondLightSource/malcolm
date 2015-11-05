import os

from malcolm.core import PausableDevice, DState, InstanceAttribute, \
    wrap_method, Attribute, VDouble, VString, VTable, \
    SeqFunctionItem, Sequence, SeqTransitionItem, VIntArray
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
        # Child state machine listeners
        for c in self.children:
            c.add_listener(self.post_changes, "stateMachine")
        self.child_statemachines = [c.stateMachine for c in self.children]
        # Run monitors
        hdf5Writer.add_listener(
            self.post_changes, "attributes.uniqueId")
        hdf5Writer.add_listener(
            self.post_changes, "attributes.capture")
        positionPlugin.add_listener(
            self.post_changes, "attributes.running")

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
            # Monitor
            dimensions=Attribute(
                VIntArray, "Detected dimensionality of positions"),
        )

    def _validate_hdf5Writer(self, hdf5File, positions, dimensions,
                             totalSteps):
        filePath, fileName = os.path.split(hdf5File)
        numExtraDims = len(positions)
        if numExtraDims == len(dimensions):
            # This is a non-sparse scan so put in place
            dimNames = []
            dimSizes = []
            dimUnits = []
            for i, (name, _, _, unit) in enumerate(positions):
                dimNames.append(name + "_index")
                dimSizes.append(dimensions[i])
                dimUnits.append(unit)
        elif [totalSteps] == dimensions:
            # This is a sparse, so unroll to series of points
            dimNames = ["n"]
            dimSizes = [totalSteps]
            dimUnits = [""]
        else:
            raise AssertionError(
                "Can't unify position number of columns {} with "
                "dimensions {}".format(numExtraDims, dimensions))
        return self.hdf5Writer.validate(
            filePath, fileName,  dimNames, dimSizes, dimUnits)

    @wrap_method()
    def validate(self, exposure, positions, hdf5File, period=None):
        # Validate simDetector
        totalSteps = len(positions[0][2])
        sim_params = self.simDetector.validate(exposure, totalSteps, period)
        runTime = sim_params["runTime"]
        runTimeout = sim_params["runTimeout"]
        period = sim_params["period"]
        # Validate position plugin
        dimensions = self.positionPlugin.validate(positions)["dimensions"]
        # Validate hdf writer
        self._validate_hdf5Writer(hdf5File, positions, dimensions, totalSteps)
        return super(SimDetectorPersonality, self).validate(locals())

    def _configure_simDetector(self):
        self.simDetector.configure(
            self.exposure, self.totalSteps - self.currentStep, self.period,
            self.currentStep, block=False)

    def _configure_positionPlugin(self):
        if self.currentStep > 0:
            positions = []
            for n, t, d, u in self.positions:
                positions.append([n, t, d[self.currentStep:], u])
        else:
            positions = self.positions
        assert self.simDetector.portName is not None, \
            "Expected simDetector.portName != None"
        self.positionPlugin.configure(
            positions, self.currentStep + 1, self.simDetector.portName,
            block=False)

    def _configure_hdf5Writer(self):
        params = self._validate_hdf5Writer(self.hdf5File, self.positions,
                                           self.dimensions, self.totalSteps)
        params = {k: v for k, v in params.items()
                  if k in self.hdf5Writer.configure.arguments}
        assert self.positionPlugin.portName is not None, \
            "Expected positionPlugin.portName != None"
        params.update(arrayPort=self.positionPlugin.portName, block=False)
        self.hdf5Writer.configure(**params)

    def do_config(self, **config_params):
        """Start doing a configuration using config_params.
        Return DState.Configuring, message when started
        """
        for d in self.children:
            assert d.state in DState.canConfig(), \
                "Child device {} in state {} is not configurable"\
                .format(d, d.state)
        # Setup self
        for name, value in config_params.items():
            setattr(self, name, value)
        self.stepsPerRun = 1
        self.currentStep = 0
        # make some sequences for config
        self._sconfig = Sequence(
            self.name + ".SConfig",
            SeqFunctionItem(
                "Configuring simDetector", self._configure_simDetector),
            SeqFunctionItem(
                "Configuring positionPlugin", self._configure_positionPlugin),
            SeqFunctionItem(
                "Configuring hdf5Writer", self._configure_hdf5Writer),
            SeqTransitionItem(
                "Wait for plugins to configure", self.child_statemachines,
                DState.Ready, DState.rest()),
        )
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

    def do_run(self):
        """Start doing a run.
        Return DState.Running, message when started
        """
        plugins = [self.simDetector.stateMachine,
                   self.positionPlugin.stateMachine]
        for d in plugins:
            assert d.state in DState.canRun(), \
                "Child device {} in state {} is not canRun"\
                .format(d.name, d.state)
        seq_items = [
            SeqFunctionItem(
                "Running positionPlugin", self.positionPlugin.run,
                block=False)]
        # If hdf writer is not already running then run it
        if self.hdf5Writer.state != DState.Running:
            seq_items += [
                SeqFunctionItem(
                    "Running hdf5Writer", self.hdf5Writer.run,
                    block=False),
                SeqTransitionItem(
                    "Wait for hdf5Writer to run",
                    self.hdf5Writer.attributes["capture"], True),
            ]
        # Now add the rest
        seq_items += [
            SeqTransitionItem(
                "Wait for positionPlugin to run",
                self.positionPlugin.attributes["running"], True),
            SeqFunctionItem(
                "Running simDetector", self.simDetector.run,
                block=False),
            SeqTransitionItem(
                "Wait for run to finish", self.child_statemachines,
                DState.Idle, DState.rest()),
        ]
        # Add a configuring object
        self._srun = Sequence(self.name + ".SRun", *seq_items)
        # Start the sequence
        item_done, msg = self._srun.start()
        if item_done:
            # Arrange for a callback to process the next item
            self.post_changes(None, None)
        return DState.Running, msg

    def do_running(self, value, changes):
        """Work out if the changes mean running is complete.
        Return None, message if it isn't.
        Return DState.Idle, message if it is and we are all done
        Return DState.Ready, message if it is and we are partially done
        """
        # Update progress
        if value == self.hdf5Writer.attributes["uniqueId"]:
            self.currentStep = value.value
        running, item_done, msg = self._srun.process(value, changes)
        if running is False:
            # Finished
            return DState.Idle, "Running done"
        elif item_done:
            # Arrange for a callback to process the next item
            self.post_changes(None, None)
        # Still going
        return DState.Running, msg

    def do_abort(self):
        """Stop acquisition
        """
        if self.state == DState.Configuring:
            self._sconfig.abort()
        elif self.state == DState.Running:
            self._srun.abort()
        elif self.state == DState.Rewinding:
            self._spause.abort()
        for d in self.children:
            if d.state in DState.canAbort():
                d.abort(block=False)
        return DState.Aborting, "Aborting started"

    def do_aborting(self, value, changes):
        """Work out if the changes mean aborting is complete.
        Return None, message if it isn't.
        Return DState.Aborted, message if it is.
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

    def do_reset(self):
        """Start doing a reset from aborted or fault state.
        Return DState.Resetting, message when started
        """
        # Abort any items that need to be aborted
        for d in self.children:
            if d.state not in DState.rest():
                d.abort(block=False)
        # Add a resetting object
        self._sreset = Sequence(
            self.name + ".SReset",
            SeqTransitionItem(
                "Wait for plugins to be at rest", self.children,
                DState.rest()),
            SeqFunctionItem(
                "Reset hdf5Writer", self.hdf5Writer.reset,
                block=False),
            SeqFunctionItem(
                "Reset simDetector", self.simDetector.reset,
                block=False),
            SeqFunctionItem(
                "Reset positionPlugin", self.positionPlugin.reset,
                block=False),
            SeqTransitionItem(
                "Wait for plugins to be at rest", self.children,
                DState.rest()),
        )
        # Start the sequence
        item_done, msg = self._sreset.start()
        if item_done:
            # Arrange for a callback to process the next item
            self.post_changes(None, None)
        return DState.Resetting, msg

    def do_resetting(self, value, changes):
        """Work out if the changes mean resetting is complete.
        Return None, message if it isn't.
        Return DState.Idle, message if it is.
        """
        running, item_done, msg = self._sreset.process(value, changes)
        if running is False:
            # Finished
            child_states = [d.state for d in self.children]
            nofault = [s != DState.Fault for s in child_states]
            assert all(nofault), \
                "Expected all not in fault, got {}".format(child_states)
            return DState.Idle, "Resetting done"
        elif item_done:
            # Arrange for a callback to process the next item
            self.post_changes(None, None)
        # Still going
        return DState.Resetting, msg

    def do_rewind(self, steps=None):
        """Start a pause"""
        # make some sequences for config
        plugins = [self.simDetector.stateMachine,
                   self.positionPlugin.stateMachine]
        for d in plugins:
            assert d.state in DState.canAbort(), \
                "Child device {} in state {} is not abortable"\
                .format(d, d.state)
        seq_items = []
        # if we need to abort
        if self.simDetector.state not in DState.canConfig() or \
                self.positionPlugin.state not in DState.canConfig():
            seq_items += [
                SeqFunctionItem(
                    "Stopping simDetector", self.simDetector.abort,
                    block=False),
                SeqFunctionItem(
                    "Stopping positionPlugin", self.positionPlugin.abort,
                    block=False),
                SeqTransitionItem(
                    "Wait for plugins to stop", plugins,
                    DState.Aborted, DState.rest()),
                SeqFunctionItem(
                    "Reset simDetector", self.simDetector.reset,
                    block=False),
                SeqFunctionItem(
                    "Reset positionPlugin", self.positionPlugin.reset,
                    block=False),
                SeqTransitionItem(
                    "Wait for plugins to reset", plugins,
                    DState.Idle, DState.rest())
            ]
        # Add the config stages
        seq_items += [
            SeqFunctionItem(
                "Configuring positionPlugin", self._configure_positionPlugin),
            SeqFunctionItem(
                "Configuring simDetector", self._configure_simDetector),
            SeqTransitionItem(
                "Wait for plugins to configure", plugins,
                DState.Ready, DState.rest()),
        ]
        # Add a configuring object
        self._spause = Sequence(self.name + ".SPause", *seq_items)
        if self.state == DState.Ready:
            self._post_rewind_state = DState.Ready
        else:
            self._post_rewind_state = DState.Paused
        if steps is not None:
            assert self.currentStep - steps > 0, \
                "Cannot retrace {} steps as we are only on step {}".format(
                    steps, self.currentStep)
            self.currentStep -= steps
        # Start the sequence
        item_done, msg = self._spause.start()
        if item_done:
            # Arrange for a callback to process the next item
            self.post_changes(None, None)
        return DState.Rewinding, msg

    def do_rewinding(self, value, changes):
        """Receive run status events and move to next state when finished"""
        running, item_done, msg = self._spause.process(value, changes)
        if running is False:
            # Finished
            return self._post_rewind_state, "Rewinding done"
        elif item_done:
            # Arrange for a callback to process the next item
            self.post_changes(None, None)
        # Still going
        return None, msg
