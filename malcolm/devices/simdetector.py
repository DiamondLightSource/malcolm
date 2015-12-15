import os

import numpy

from malcolm.core import PausableDevice, DState, InstanceAttribute, \
    wrap_method, Attribute, VDouble, VString, VTable, \
    SeqFunctionItem, Sequence, SeqTransitionItem, VIntArray, VInt
from malcolm.devices import SimDetectorDriver, Hdf5Writer, PositionPlugin

def_positions = [
    ("y", VDouble, numpy.repeat(numpy.arange(6, 9), 5) * 0.1, 'mm'),
    ("x", VDouble, numpy.tile(numpy.arange(5), 3) * 0.1, 'mm'),
]


class SimDetector(PausableDevice):
    class_attributes = dict(
        simDetectorDriver=InstanceAttribute(SimDetectorDriver, "SimDetectorDriver Device"),
        hdf5Writer=InstanceAttribute(Hdf5Writer, "Hdf5Writer Device"),
        positionPlugin=InstanceAttribute(
            PositionPlugin, "PositionPlugin Device"),
    )

    def __init__(self, name, simDetectorDriver, positionPlugin, hdf5Writer):
        super(SimDetector, self).__init__(name)
        self.simDetectorDriver = simDetectorDriver
        self.positionPlugin = positionPlugin
        self.hdf5Writer = hdf5Writer
        self.children = [simDetectorDriver, positionPlugin, hdf5Writer]
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
        super(SimDetector, self).add_all_attributes()
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
        dimNames = []
        dimUnits = []
        names = [c[0] for c in positions]
        indexNames = [n for n in names if n.endswith("_index")]
        for name, _, _, unit in positions:
            if not name.endswith("_index"):
                dimNames.append(name)
                if unit:
                    dimUnits.append(unit)
                else:
                    dimUnits.append("mm")
        assert len(dimNames) == len(dimensions), \
            "Can't unify position number of index columns {} with " \
            "dimensions {}".format(len(dimNames), dimensions)
        return self.hdf5Writer.validate(
            filePath, fileName, dimNames, dimUnits, indexNames, dimensions)

    @wrap_method()
    def validate(self, hdf5File, exposure, positions=def_positions,
                 period=None):
        # Validate self
        dimensions, positions = self._add_position_indexes(positions)
        # Validate simDetectorDriver
        totalSteps = len(positions[0][2])
        sim_params = self.simDetectorDriver.validate(exposure, totalSteps, period)
        runTime = sim_params["runTime"]
        runTimeout = sim_params["runTimeout"]
        period = sim_params["period"]
        # Validate position plugin
        self.positionPlugin.validate(positions)
        # Validate hdf writer
        self._validate_hdf5Writer(hdf5File, positions, dimensions, totalSteps)
        return super(SimDetector, self).validate(locals())

    def _add_position_indexes(self, positions):
        # which columns are index columns?
        names = [column[0] for column in positions]
        indexes = [n for n in names if n.endswith("_index")]
        non_indexes = [n for n in names if not n.endswith("_index")]
        expected_indexes = ["{}_index".format(n) for n in non_indexes]
        # check if indexes are supplied
        if indexes == expected_indexes or indexes == ["n_index"]:
            # just get dimensionality from these indexes
            dims = [max(d) + 1 for n, _, d, _ in positions if n in indexes]
            index_columns = [c for c in positions if n in indexes]
        else:
            # detect dimensionality of non_index columns
            uniq = [sorted(set(d))
                    for n, _, d, _ in positions if n in non_indexes]
            dims = [len(pts) for pts in uniq]
            npts = len(positions[0][2])
            if numpy.prod(dims) != npts:
                # This is a sparse scan, should be written as long list
                dims = [npts]
                index_columns = [
                    ("n_index", VInt, numpy.arange(npts, dtype=numpy.int32), '')]
            else:
                # Create position table
                index_columns = []
                for name, sort in zip(non_indexes, uniq):
                    index = "{}_index".format(name)
                    # select the correct named column
                    data = [d for n, _, d, _ in positions if n == name][0]
                    # work out their index in the unique sorted list
                    data = numpy.array([sort.index(x)
                                        for x in data], dtype=numpy.int32)
                    index_columns.append((index, VInt, data, ''))
        positions = [c for c in positions if n in non_indexes] + index_columns
        return dims, positions

    def _configure_simDetectorDriver(self):
        self.simDetectorDriver.configure(
            self.exposure, self.totalSteps - self.currentStep, self.period,
            self.currentStep, block=False)

    def _configure_positionPlugin(self):
        if self.currentStep > 0:
            positions = []
            for n, t, d, u in self.positions:
                positions.append([n, t, d[self.currentStep:], u])
        else:
            positions = self.positions
        assert self.simDetectorDriver.portName is not None, \
            "Expected simDetectorDriver.portName != None"
        self.positionPlugin.configure(
            positions, self.currentStep + 1, self.simDetectorDriver.portName,
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
                "Configuring simDetectorDriver", self._configure_simDetectorDriver),
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
        plugins = [self.simDetectorDriver.stateMachine,
                   self.positionPlugin.stateMachine]
        for d in plugins:
            assert d.state == DState.Ready, \
                "Child device {} in state {} is not runnable"\
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
                "Running simDetectorDriver", self.simDetectorDriver.run,
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
        self.post_changes(None, None)
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
            no_fault = [s != DState.Fault for s in child_states]
            assert all(no_fault), \
                "Expected no fault, got {}".format(child_states)
            return DState.Aborted, "Aborting finished"
        else:
            # No change
            return None, None

    def do_reset(self):
        """Start doing a reset from aborted or fault state.
        Return DState.Resetting, message when started
        """
        seq_items = []
        # Abort any items that need to be aborted
        need_wait = []
        need_reset = []
        for d in self.children:
            if d.state not in DState.rest():
                d.abort(block=False)
                need_wait.append(d.stateMachine)
                need_reset.append(d)
            elif d.state in DState.canReset():
                need_reset.append(d)
        if need_wait:
            seq_items.append(SeqTransitionItem(
                "Wait for plugins to stop aborting",
                need_wait, DState.rest()))
        if need_reset:
            for d in need_reset:
                seq_items.append(SeqFunctionItem(
                    "Reset {}".format(d.name), d.reset,
                    block=False))
            seq_items.append(SeqTransitionItem(
                "Wait for plugins to stop resetting",
                [d.stateMachine for d in need_reset], DState.rest()))
        # Add a resetting object
        if seq_items:
            self._sreset = Sequence(self.name + ".SReset", *seq_items)
            # Start the sequence
            item_done, msg = self._sreset.start()
            if item_done:
                # Arrange for a callback to process the next item
                self.post_changes(None, None)
        else:
            self._sreset = None
            msg = "Started resetting"
            self.post_changes(None, None)
        return DState.Resetting, msg

    def do_resetting(self, value, changes):
        """Work out if the changes mean resetting is complete.
        Return None, message if it isn't.
        Return DState.Idle, message if it is.
        """
        if self._sreset is None:
            return DState.Idle, "Resetting done"
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
        plugins = [self.simDetectorDriver.stateMachine,
                   self.positionPlugin.stateMachine]
        for d in plugins:
            assert d.state in DState.canAbort(), \
                "Child device {} in state {} is not abortable"\
                .format(d, d.state)
        seq_items = []
        # if we need to abort
        if self.simDetectorDriver.state not in DState.canConfig() or \
                self.positionPlugin.state not in DState.canConfig():
            seq_items += [
                SeqFunctionItem(
                    "Stopping simDetectorDriver", self.simDetectorDriver.abort,
                    block=False),
                SeqFunctionItem(
                    "Stopping positionPlugin", self.positionPlugin.abort,
                    block=False),
                SeqTransitionItem(
                    "Wait for plugins to stop", plugins,
                    DState.Aborted, DState.rest()),
                SeqFunctionItem(
                    "Reset simDetectorDriver", self.simDetectorDriver.reset,
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
                "Configuring simDetectorDriver", self._configure_simDetectorDriver),
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
