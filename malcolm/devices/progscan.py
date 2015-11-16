from malcolm.core import RunnableDevice, Attribute, PvAttribute, DState, \
    wrap_method, VString, VEnum, VBool, VInt, VDouble, SeqAttributeItem, \
    Sequence, HasConfigSequence


class ProgScan(HasConfigSequence, RunnableDevice):
    class_attributes = dict(
        prefix=Attribute(VString, "PV Prefix for device"))

    def __init__(self, name, prefix):
        self.prefix = prefix
        super(ProgScan, self).__init__(name)

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
        self.add_listener(self.post_changes, "attributes")

    @wrap_method()
    def validate(self, m1Start, m1Step, m1NumPoints, m1Dwell,
                 m1Alternate=False, m1Order=3,
                 m2Start=0, m2Step=0, m2NumPoints=0, m2Dwell=0,
                 m2Alternate=False, m2Order=2,
                 m3Start=0, m3Step=0, m3NumPoints=0, m3Dwell=0,
                 m3Alternate=False, m3Order=1):
        """Check whether a set of configuration parameters is valid or not. Each
        parameter name must match one of the names in self.attributes. This set
        of parameters should be checked in isolation, no device state should be
        taken into account. It is allowed from any DState and raises an error
        if the set of configuration parameters is invalid. It should return
        some metrics on the set of parameters as well as the actual parameters
        that should be used, e.g.
        {"runTime": 1.5, arg1=2, arg2="arg2default"}
        """
        # TODO: movetime is estimated at 1s here, this is wrong...
        runTime = m1NumPoints * (m1Dwell * 0.001 + 1)
        runTime += m2NumPoints * (m2Dwell * 0.001 + 1)
        runTime += m3NumPoints * (m3Dwell * 0.001 + 1)
        return super(ProgScan, self).validate(locals())

    def make_config_sequence(self, **config_params):
        """Return a Sequence object that can be used for configuring"""
        # Add a configuring object
        sconfig = Sequence(
            self.name + ".SConfig",
            SeqAttributeItem(
                "Configuring parameters", self.attributes,
                **config_params
            )
        )
        return sconfig

    def do_run(self):
        """Start doing a run.
        Return DState.Running, message when started
        """
        self.scanStart = True
        return DState.Running, "Running started"

    def do_running(self, value, changes):
        """Work out if the changes mean running is complete.
        Return None, message if it isn't.
        Return DState.Idle, message if it is and we are all done
        Return DState.Ready, message if it is and we are partially done
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
        """Start doing an abort.
        Return DState.Aborting, message when started
        """
        if self.state == DState.Configuring:
            # Abort configure
            self._sconfig.abort()
        elif self.state == DState.Running:
            # Abort run
            self.scanAbort = True
        self.post_changes(None, None)
        return DState.Aborting, "Aborting started"

    def do_aborting(self, value, changes):
        """Work out if the changes mean aborting is complete.
        Return None, message if it isn't.
        Return DState.Aborted, message if it is.
        """
        if self.progState != "Scanning":
            return DState.Aborted, "Aborting finished"
        else:
            # No change
            return None, None

    def do_reset(self):
        """Start doing a reset from aborted or fault state.
        Return DState.Resetting, message when started
        """
        self.scanAbort = True
        self.post_changes(None, None)
        return DState.Resetting, "Resetting started"

    def do_resetting(self, value, changes):
        """Work out if the changes mean resetting is complete.
        Return None, message if it isn't.
        Return DState.Idle, message if it is.
        """
        return DState.Idle, "Resetting finished"
