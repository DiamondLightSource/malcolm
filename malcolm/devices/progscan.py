from malcolm.core import RunnableDevice, Attribute, PvAttribute, DState, \
    wrap_method, VString, VEnum, VBool, VInt, VDouble, SeqAttributeItem, \
    Sequence


class ProgScan(RunnableDevice):
    class_attributes = dict(
        prefix=Attribute(VString, "PV Prefix for device"))

    def __init__(self, name, prefix, timeout=None):
        self.prefix = prefix
        super(ProgScan, self).__init__(name, timeout)
        self._make_sconfig()

    def add_all_attributes(self):
        super(ProgScan, self).add_all_attributes()
        p = self.prefix
        self.add_attributes(
            # Run
            scanStart=PvAttribute(
                p + "SCAN:START", VBool,
                "Start a scan",
                put_callback=False),
            # Abort
            scanAbort=PvAttribute(
                p + "SCAN:ABORT", VBool,
                "Abort a scan"),
            # Monitor
            progState=PvAttribute(
                p + "PROG:STATE",
                VEnum("Idle,Scanning,Prog error,Prog failed,Failed"),
                "State of current run"),
        )
        # Add per motor
        for i in range(1, 4):
            p = "{}M{}:".format(self.prefix, i)
            m = "m{}{{}}".format(i)
            # Configure
            self.add_attribute(
                m.format("Start"),
                PvAttribute(
                    p + "START:POS", VDouble,
                    "Starting position in this dimension",
                    rbv_suff=":RBV"))
            self.add_attribute(
                m.format("Step"),
                PvAttribute(
                    p + "STEP:SIZE", VDouble,
                    "Increment by this for each move in this dimension",
                    rbv_suff=":RBV"))
            self.add_attribute(
                m.format("NumPoints"),
                PvAttribute(
                    p + "NPOINTS", VInt,
                    "Number of points in this dimension",
                    rbv_suff=":RBV"))
            self.add_attribute(
                m.format("Dwell"),
                PvAttribute(
                    p + "DWELL", VInt,
                    "Dwell time in ms after each move. -1 means none",
                    rbv_suff=":RBV"))
            self.add_attribute(
                m.format("Alternate"),
                PvAttribute(
                    p + "ALTERNATE", VBool,
                    "Whether to reverse alternate rows in this dimension",
                    rbv_suff=":RBV"))
            self.add_attribute(
                m.format("Order"),
                PvAttribute(
                    p + "ORDER", VInt,
                    "Which axis to do first, second, third",
                    rbv_suff=":RBV"))
            # Readback
            self.add_attribute(
                m.format("PointsDone"),
                PvAttribute(
                    p + "POINT", VInt,
                    "How many points are done in the current iteration"))
            self.add_attribute(
                m.format("ScansDone"),
                PvAttribute(
                    p + "SCAN", VInt,
                    "How many complete scans of this dimension are done"))
        self.add_listener(self.on_runsta_change, "attributes.progState")
        self.add_listener(self.on_runsta_change, "attributes.scanStart")

    def on_runsta_change(self, runsta, changes):
        if self.state == DState.Running:
            self.post_runsta()
        elif self.state == DState.Aborting:
            self.post_abortsta()

    def _make_sconfig(self):
        # make some sequences for config
        s1 = SeqAttributeItem(
            "Configuring parameters", self.attributes,
            **self.validate.arguments  # all the config params
        )
        # Add a configuring object
        self._sconfig = Sequence(self.name + ".Config", s1)
        self.add_listener(self._sconfig.on_change, "attributes")
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

    @wrap_method()
    def validate(self, m1Start, m1Step, m1NumPoints, m1Dwell,
                 m1Alternate=False, m1Order=3,
                 m2Start=0, m2Step=0, m2NumPoints=0, m2Dwell=0,
                 m2Alternate=False, m2Order=2,
                 m3Start=0, m3Step=0, m3NumPoints=0, m3Dwell=0,
                 m3Alternate=False, m3Order=1):
        # TODO: movetime is estimated at 1s here, this is wrong...
        runTime = m1NumPoints * (m1Dwell * 0.001 + 1)
        runTime += m2NumPoints * (m2Dwell * 0.001 + 1)
        runTime += m3NumPoints * (m3Dwell * 0.001 + 1)
        return super(ProgScan, self).validate(locals())

    def do_config(self, **config_params):
        """Start doing a configuration using config_params"""
        assert self._sconfig.state in self._sconfig.rest_states(), \
            "Can't configure sub-state machine in {} state" \
            .format(self._sconfig.state)
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
        self.scanStart = True
        return DState.Running, "Running started"

    def do_runsta(self):
        """If acquiring then return
        """
        if self.scanStart and self.progState == "Scanning":
            # No change
            return None, None
        else:
            assert self.progState in ("Idle", "Scanning"), \
                "Expected {}, got {}".format(("Idle", "Scanning"),
                                             self.progState)
            return DState.Idle, "Running finished"

    def do_abort(self):
        """Stop acquisition
        """
        self.scanAbort = True
        self.post_abortsta()
        return DState.Aborting, "Aborting started"

    def do_abortsta(self):
        """Check we finished
        """
        return DState.Aborted, "Aborting finished"

    def do_reset(self):
        """Check and attempt to clear any error state, arranging for a
        callback doing self.post(DEvent.ResetSta, resetsta) when progress has
        been made, where resetsta is any device specific reset status
        """
        self.scanAbort = True
        self.post_resetsta()
        return DState.Resetting, "Resetting started"

    def do_resetsta(self):
        """Examine configsta for configuration progress, returning
        DState.Resetting if still in progress, or DState.Idle if done.
        """
        return DState.Idle, "Resetting finished"
