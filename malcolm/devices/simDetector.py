from malcolm.core import RunnableDevice, Attribute, wrap_method, PvAttribute, \
    VString, VDouble, VEnum, VInt, VBool, DState, Sequence, \
    SeqAttributeItem


class SimDetector(RunnableDevice):
    class_attributes = dict(
        prefix=Attribute(VString, "PV Prefix for device"))

    def __init__(self, name, prefix, timeout=None):
        self.prefix = prefix
        super(SimDetector, self).__init__(name, timeout)
        self._make_sconfig()

    def add_all_attributes(self):
        super(SimDetector, self).add_all_attributes()
        p = self.prefix
        self.add_attributes(
            # Configure
            exposure=PvAttribute(
                p + "AcquireTime", VDouble,
                "Exposure time for each frame",
                rbv_suff="_RBV"),
            period=PvAttribute(
                p + "AcquirePeriod", VDouble,
                "Time between the start of each frame",
                rbv_suff="_RBV"),
            imageMode=PvAttribute(
                p + "ImageMode", VEnum("Single,Multiple,Continuous"),
                "How many images to take when acquire is started",
                rbv_suff="_RBV"),
            numImages=PvAttribute(
                p + "NumImages", VInt,
                "Number of images to take if imageMode=Multiple",
                rbv_suff="_RBV"),
            arrayCounter=PvAttribute(
                p + "ArrayCounter", VInt,
                "Current unique id number for frame",
                rbv_suff="_RBV"),
            arrayCallbacks=PvAttribute(
                p + "ArrayCallbacks", VBool,
                "Whether to produce images or not",
                rbv_suff="_RBV"),
            # Run
            acquire=PvAttribute(
                p + "Acquire", VBool,
                "Demand and readback for starting acquisition",
                put_callback=False),
            # Monitor
            portName=PvAttribute(
                p + "PortName_RBV", VString,
                "Port name of this plugin"),
        )
        self.add_listener(self.on_acquire_change, "attributes.acquire")

    def on_acquire_change(self, acquire, changes):
        if self.state == DState.Running:
            self.post_runsta()
        elif self.state == DState.Aborting:
            self.post_abortsta()

    def _make_sconfig(self):
        # make some sequences for config
        s1 = SeqAttributeItem(
            "Configuring parameters", self.attributes,
            imageMode="Multiple",
            arrayCallbacks=1,
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
    def validate(self, exposure, numImages, period=None, arrayCounter=0):
        if period is None:
            period = exposure
        assert exposure >= period, \
            "Exposure {} should be >= period {}".format(exposure, period)
        runTime = numImages * period
        return super(SimDetector, self).validate(locals())

    def do_reset(self):
        """Check and attempt to clear any error state, arranging for a
        callback doing self.post(DEvent.ResetSta, resetsta) when progress has
        been made, where resetsta is any device specific reset status
        """
        self.post_resetsta(None)
        return DState.Resetting, "Resetting started"

    def do_resetsta(self, resetsta):
        """Examine configsta for configuration progress, returning
        DState.Resetting if still in progress, or DState.Idle if done.
        """
        return DState.Idle, "Resetting finished"

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
        self.acquire = True
        return DState.Running, "Running started"

    def do_runsta(self):
        """If acquiring then return
        """
        if self.acquire:
            # No change
            return None, None
        else:
            return DState.Idle, "Running finished"

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
        else:
            # Abort run
            self.acquire = False
        return DState.Aborting, "Aborting started"

    def do_abortsta(self):
        """Check we finished
        """
        if not self.acquire and \
                self._sconfig.state in self._sconfig.rest_states():
            return DState.Aborted, "Aborting finished"
        else:
            # No change
            return None, None
