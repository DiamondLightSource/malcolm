import os

import numpy

from malcolm.core import PausableDevice, DState, InstanceAttribute, \
    wrap_method, Attribute, VDouble, VString, VTable, \
    SeqFunctionItem, Sequence, SeqTransitionItem
from malcolm.devices import SimDetector, ProgScan


class ArpesScan(PausableDevice):
    "2d snake scan"
    class_attributes = dict(
        simDetector=InstanceAttribute(SimDetector, "SimDetector Device"),
        progScan=InstanceAttribute(ProgScan, "ProgScan Device"),
    )

    def __init__(self, name, simDetector, progScan):
        super(ArpesScan, self).__init__(name)
        self.simDetector = simDetector
        self.progScan = progScan
        self.children = [simDetector, progScan]
        # Child state machine listeners
        for c in self.children:
            c.add_listener(self.post_changes, "stateMachine")
        self.child_statemachines = [c.stateMachine for c in self.children]
        # Run monitors for currentStep
        progScan.add_listener(
            self.post_changes, "attributes.progress")
        simDetector.add_listener(
            self.post_changes, "attributes.currentStep")
        simDetector.add_listener(
            self.post_changes, "attributes.running")

    def add_all_attributes(self):
        super(ArpesScan, self).add_all_attributes()
        self.add_attributes(
            # Configure
            xStart=Attribute(VDouble, "Starting position for X"),
            xStop=Attribute(VDouble, "Stopping position for X"),
            xStep=Attribute(VDouble, "Distance between each point in X"),
            yStart=Attribute(VDouble, "Starting position for Y"),
            yStop=Attribute(VDouble, "Stopping position for Y"),
            yStep=Attribute(VDouble, "Distance between each point in Y"),
            exposure=Attribute(VDouble, "Exposure time for each frame"),
            hdf5File=Attribute(VString, "HDF5 full file path to write"),
            # Readback
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
    def validate(self, xStart=0, xStop=0.5, xStep=0.05,
                 yStart=0, yStop=0.1, yStep=0.02, exposure=0.075, 
                 hdf5File="/tmp/foo.h5"):
        # Create a positions table
        positions, xNumPoints, yNumPoints = self._create_positions(
            xStart, xStop, xStep, yStart, yStop, yStep)
        xStop = xStart + xStep * (xNumPoints - 1)
        yStop = yStart + yStep * (yNumPoints - 1)
        totalSteps = len(positions[0][2])
        # Validate simDetector
        sim_params = self.simDetector.validate(
            hdf5File, exposure, positions)
        # Validate progScan
        prog_params = self.progScan.validate(
            int(exposure * 1000),
            xStart, xStep, xNumPoints, 0, True, 3,
            yStart, yStep, yNumPoints, -1, False, 2
        )
        runTime = max(sim_params["runTime"], prog_params["runTime"])
        runTimeout = max(sim_params["runTimeout"], prog_params["runTimeout"])
        return super(ArpesScan, self).validate(locals())

    def _configure_simDetector(self):
        self.simDetector.configure(self.hdf5File, self.exposure,
                                   self.positions, block=False)

    def _configure_progScan(self):
        xNumPoints = self._npoints(self.xStart, self.xStop, self.xStep)
        yNumPoints = self._npoints(self.yStart, self.yStop, self.yStep)
        self.progScan.configure(
            int(self.exposure * 1000),
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
                "Configuring simDetector", self._configure_simDetector),
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
        assert self.simDetector.state in \
            [DState.Ready, DState.Paused], \
            "simDetector in state {} is not runnable"\
            .format(self.simDetector.state)
        # If simDetector is paused then resume, otherwise run
        if self.simDetector.state == DState.Paused:
            simDetectorFunc = self.simDetector.resume
        elif self.simDetector.state == DState.Ready:
            simDetectorFunc = self.simDetector.run
        # Add a configuring object
        self._srun = Sequence(
            self.name + ".SRun",
            SeqFunctionItem(
                "Running simDetector", simDetectorFunc,
                block=False),
            SeqTransitionItem(
                "Wait for simDetector to run",
                self.simDetector.attributes["running"], True),
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
        if value == self.simDetector.attributes["currentStep"]:
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
        need_det_pause = self.simDetector.state == DState.Running
        if not need_det_pause:
            assert self.simDetector.state in DState.canRewind(), \
                "SimDetector state {} isn't paused and can't rewind" \
                .format(self.simDetector.state)
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
        # either pause or resume simDetector
        if need_det_pause:
            seq_items.append(
                SeqFunctionItem(
                    "Pausing simDetector", self.simDetector.pause,
                    block=False))
        else:
            seq_items.append(
                SeqFunctionItem(
                    "Rewinding simDetector", self.simDetector.rewind,
                    steps=steps, block=False))
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
                "Wait for simDetector to rewind", self.simDetector.stateMachine,
                self._post_rewind_state, DState.doneRewind),
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
