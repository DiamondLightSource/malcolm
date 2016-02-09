import numpy

from malcolm.core import PausableDevice, DState, InstanceAttribute, \
    wrap_method, Attribute, VDouble, VString, VTable, \
    SeqFunctionItem, Sequence, SeqTransitionItem
from malcolm.devices import SimDetector, ProgScan


class LabScan(PausableDevice):
    "2d snake scan"
    class_attributes = dict(
        det1=InstanceAttribute(SimDetector, "SimDetector Device"),
        det2=InstanceAttribute(SimDetector, "SimDetector Device"),
        progScan=InstanceAttribute(ProgScan, "ProgScan Device"),
    )

    def __init__(self, name, det1, det2, progScan):
        super(LabScan, self).__init__(name)
        self.det1 = det1
        self.det2 = det2
        self.progScan = progScan
        self.children = [det1, det2, progScan]
        # Child state machine listeners
        for c in self.children:
            c.add_listener(self.post_changes, "stateMachine")
        self.child_statemachines = [c.stateMachine for c in self.children]
        # Run monitors for currentStep
        progScan.add_listener(
            self.post_changes, "attributes.progress")
        det1.add_listener(
            self.post_changes, "attributes.currentStep")
        det1.add_listener(
            self.post_changes, "attributes.running")
        det2.add_listener(
            self.post_changes, "attributes.running")

    def add_all_attributes(self):
        super(LabScan, self).add_all_attributes()
        self.add_attributes(
            # Configure
            xStart=Attribute(VDouble, "Starting position for X"),
            xStop=Attribute(VDouble, "Stopping position for X"),
            xStep=Attribute(VDouble, "Distance between each point in X"),
            yStart=Attribute(VDouble, "Starting position for Y"),
            yStop=Attribute(VDouble, "Stopping position for Y"),
            yStep=Attribute(VDouble, "Distance between each point in Y"),
            det1Exposure=Attribute(VDouble, "Exposure time for det1 frame"),
            det2Exposure=Attribute(VDouble, "Exposure time for det2 frame"),
            hdf5File1=Attribute(VString, "HDF5 full file path for det1 data"),
            hdf5File2=Attribute(VString, "HDF5 full file path for det2 data"),
            # Readback
            dwellTime=Attribute(VDouble, "Dwell time at each point"),
            positions=Attribute(VTable, "Generated position table")
        )

    def _npoints(self, start, stop, step):
        npoints = int((stop - start + step * 1.0001) / step)
        return npoints

    def _arange(self, start, stop, step):
        arange = numpy.arange(start, stop + step * 0.0001, step)
        return arange

    def _create_positions(self, xStart, xStop, xStep, yStart, yStop, yStep):
        xNumPoints = self._npoints(xStart, xStop, xStep)
        yNumPoints = self._npoints(yStart, yStop, yStep)
        xFwd = self._arange(xStart, xStop, xStep)
        assert len(xFwd) == xNumPoints, \
            "{} != {}".format(len(xFwd), xNumPoints)
        xRev = xFwd[::-1]
        yFwd = self._arange(yStart, yStop, yStep)
        assert len(yFwd) == yNumPoints, \
            "{} != {}".format(len(yFwd), yNumPoints)
        # make the positions table
        xPoints = numpy.zeros(xNumPoints * yNumPoints, dtype=numpy.float64)
        yPoints = numpy.zeros(xNumPoints * yNumPoints, dtype=numpy.float64)
        # start by going forward
        xRow = xFwd
        for i, y in enumerate(yFwd):
            yPoints[i * xNumPoints:(i + 1) * xNumPoints] = y
            xPoints[i * xNumPoints:(i + 1) * xNumPoints] = xRow
            # go the other way for the next row
            if xRow is xFwd:
                xRow = xRev
            else:
                xRow = xFwd
        positions = [
            ("y", VDouble, yPoints, 'mm'),
            ("x", VDouble, xPoints, 'mm'),
        ]
        return positions, xNumPoints, yNumPoints

    @wrap_method()
    def validate(self, xStart=-11.5, xStop=-8.5, xStep=0.5,
                 yStart=-7.5, yStop=-2.5, yStep=1.25, det1Exposure=0.005,
                 det2Exposure=0.5, hdf5File1="/tmp/lab_scan_det1.h5",
                 hdf5File2="/tmp/lab_scan_det2.h5"):
        # Create a positions table
        positions, xNumPoints, yNumPoints = self._create_positions(
            xStart, xStop, xStep, yStart, yStop, yStep)
        xStop = xStart + xStep * (xNumPoints - 1)
        yStop = yStart + yStep * (yNumPoints - 1)
        totalSteps = len(positions[0][2])
        # Validate det1
        dwellTime = max(det1Exposure, det2Exposure)
        sim_params1 = self.det1.validate(
            hdf5File1, det1Exposure, positions, dwellTime)
        sim_params2 = self.det2.validate(
            hdf5File2, det2Exposure, positions, dwellTime)
        # Validate progScan
        prog_params = self.progScan.validate(
            int(dwellTime * 1000),
            xStart, xStep, xNumPoints, 0, True, 3,
            yStart, yStep, yNumPoints, -1, False, 2
        )
        runTime = max(sim_params1["runTime"], sim_params2["runTime"],
                      prog_params["runTime"])
        runTimeout = max(sim_params1["runTimeout"], sim_params2["runTimeout"],
                         prog_params["runTimeout"])
        abortTimeout = prog_params["abortTimeout"]
        return super(LabScan, self).validate(locals())

    def _configure_simDetector(self):
        self.det1.configure(self.hdf5File1, self.det1Exposure, self.positions,
                            self.dwellTime, block=False)
        self.det2.configure(self.hdf5File2, self.det2Exposure, self.positions,
                            self.dwellTime, block=False)

    def _configure_progScan(self):
        xNumPoints = self._npoints(self.xStart, self.xStop, self.xStep)
        yNumPoints = self._npoints(self.yStart, self.yStop, self.yStep)
        self.progScan.configure(
            int(self.dwellTime * 1000),
            self.xStart, self.xStep, xNumPoints, 0, True, 3,
            self.yStart, self.yStep, yNumPoints, -1, False, 2,
            startPoint=self.currentStep + 1, block=False)

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
                "Configuring dets", self._configure_simDetector),
            SeqFunctionItem(
                "Configuring progScan", self._configure_progScan),
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
        assert self.progScan.state == DState.Ready, \
            "ProgScan in state {} is not runnable"\
            .format(self.progScan.state)
        assert self.det1.state in \
            [DState.Ready, DState.Paused], \
            "det1 in state {} is not runnable"\
            .format(self.det1.state)
        assert self.det2.state in \
            [DState.Ready, DState.Paused], \
            "det2 in state {} is not runnable"\
            .format(self.det2.state)
        # If det1 is paused then resume, otherwise run
        if self.det1.state == DState.Paused:
            det1func = self.det1.resume
            det2func = self.det2.resume
        elif self.det1.state == DState.Ready:
            det1func = self.det1.run
            det2func = self.det2.run
        # Add a configuring object
        self._srun = Sequence(
            self.name + ".SRun",
            SeqFunctionItem(
                "Running det1", det1func,
                block=False),
            SeqFunctionItem(
                "Running det2", det2func,
                block=False),
            SeqTransitionItem(
                "Wait for det1 to run",
                self.det1.attributes["running"], True),
            SeqTransitionItem(
                "Wait for det2 to run",
                self.det2.attributes["running"], True),
            SeqFunctionItem(
                "Running progScan", self.progScan.run,
                block=False),
            SeqTransitionItem(
                "Wait for run to finish", self.child_statemachines,
                DState.Idle, DState.rest()))
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
        if value == self.det1.attributes["currentStep"]:
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
        assert self.progScan.state in DState.canAbort(), \
            "progScan in state {} is not abortable"\
            .format(self.progScan.state)
        seq_items = []
        need_prog_abort = self.progScan.state not in DState.canConfig()
        need_det_pause = self.det1.state == DState.Running
        if not need_det_pause:
            assert self.det1.state in DState.canRewind(), \
                "SimDetector state {} isn't paused and can't rewind" \
                .format(self.det1.state)
        if self.state == DState.Ready:
            self._post_rewind_state = DState.Ready
        else:
            self._post_rewind_state = DState.Paused
        # if we need to abort progScan
        if need_prog_abort:
            seq_items.append(
                SeqFunctionItem(
                    "Stopping progScan", self.progScan.abort,
                    block=False))
        # either pause or resume det1
        if need_det_pause:
            seq_items += [
                SeqFunctionItem(
                    "Pausing det1", self.det1.pause,
                    block=False),
                SeqFunctionItem(
                    "Pausing det2", self.det2.pause,
                    block=False)
            ]
        else:
            seq_items += [
                SeqFunctionItem(
                    "Rewinding det1", self.det1.rewind,
                    steps=steps, block=False),
                SeqFunctionItem(
                    "Rewinding det2", self.det2.rewind,
                    steps=steps, block=False)
            ]
        # wait for progScan to stop
        if need_prog_abort:
            seq_items += [
                SeqTransitionItem(
                    "Wait for progScan to stop", self.progScan.stateMachine,
                    DState.Aborted, DState.rest()),
                SeqFunctionItem(
                    "Reset progScan", self.progScan.reset,
                    block=False),
                SeqTransitionItem(
                    "Wait for progScan to reset", self.progScan.stateMachine,
                    DState.Idle, DState.rest())
            ]
        # Add the config stages
        seq_items += [
            SeqTransitionItem(
                "Wait for det1 to rewind", self.det1.stateMachine,
                self._post_rewind_state, DState.doneRewind()),
            SeqTransitionItem(
                "Wait for det2 to rewind", self.det2.stateMachine,
                self._post_rewind_state, DState.doneRewind()),
            SeqFunctionItem(
                "Configuring progScan", self._configure_progScan),
            SeqTransitionItem(
                "Wait for progScan to configure", self.progScan.stateMachine,
                DState.Ready, DState.rest()),
        ]
        # Add a configuring object
        self._spause = Sequence(self.name + ".SPause", *seq_items)
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
