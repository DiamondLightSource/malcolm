from malcolm.core import RunnableDevice, Attribute, wrap_method, PvAttribute, \
    VString, VDouble, VEnum, VInt, VBool, DState, Sequence, \
    SeqAttributeItem, HasConfigSequence

from malcolm.devices import DetectorDriver


class SimDetectorDriver(HasConfigSequence, RunnableDevice, DetectorDriver):
    class_attributes = dict(
        prefix=Attribute(VString, "PV Prefix for device"))

    def __init__(self, name, prefix):
        self.prefix = prefix
        super(SimDetectorDriver, self).__init__(name)

    def add_all_attributes(self):
        super(SimDetectorDriver, self).add_all_attributes()
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
        self.add_listener(self.post_changes, "attributes")

    @wrap_method()
    def validate(self, exposure, numImages, period=None, arrayCounter=0):
        """Check whether a set of configuration parameters is valid or not. Each
        parameter name must match one of the names in self.attributes. This set
        of parameters should be checked in isolation, no device state should be
        taken into account. It is allowed from any DState and raises an error
        if the set of configuration parameters is invalid. It should return
        some metrics on the set of parameters as well as the actual parameters
        that should be used, e.g.
        {"runTime": 1.5, arg1=2, arg2="arg2default"}
        """
        if period is None:
            period = exposure
        assert exposure <= period, \
            "Exposure {} should be <= period {}".format(exposure, period)
        runTime = numImages * period
        runTimeout = runTime + 1.5
        return super(SimDetectorDriver, self).validate(locals())

    def make_config_sequence(self, **config_params):
        """Return a Sequence object that can be used for configuring"""
        # make some sequences for config
        sconfig = Sequence(
            self.name + ".SConfig",
            SeqAttributeItem(
                "Configuring parameters", self.attributes,
                imageMode="Multiple",
                arrayCallbacks=1,
                **config_params)
        )
        return sconfig

    def do_run(self):
        """Start doing a run.
        Return DState.Running, message when started
        """
        self.acquire = True
        return DState.Running, "Running started"

    def do_running(self, value, changes):
        """Work out if the changes mean running is complete.
        Return None, message if it isn't.
        Return DState.Idle, message if it is and we are all done
        Return DState.Ready, message if it is and we are partially done
        """
        if "acquire.value" in changes and not self.acquire:
            return DState.Idle, "Running finished"
        else:
            # No change
            return None, None

    def do_abort(self):
        """Start doing an abort.
        Return DState.Aborting, message when started
        """
        if self.state == DState.Configuring:
            # Abort configure
            self._sconfig.abort()
        elif self.state == DState.Running:
            # Abort run
            self.acquire = False
        self.post_changes(None, None)
        return DState.Aborting, "Aborting started"

    def do_aborting(self, value, changes):
        """Work out if the changes mean aborting is complete.
        Return None, message if it isn't.
        Return DState.Aborted, message if it is.
        """
        if not self.acquire:
            return DState.Aborted, "Aborting finished"
        else:
            # No change
            return None, None

    def do_reset(self):
        """Start doing a reset from aborted or fault state.
        Return DState.Resetting, message when started
        """
        self.post_changes(None, None)
        return DState.Resetting, "Resetting started"

    def do_resetting(self, value, changes):
        """Work out if the changes mean resetting is complete.
        Return None, message if it isn't.
        Return DState.Idle, message if it is.
        """
        return DState.Idle, "Resetting finished"
