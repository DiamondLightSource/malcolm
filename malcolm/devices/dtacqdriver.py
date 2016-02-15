from malcolm.core import RunnableDevice, Attribute, wrap_method, PvAttribute, \
    VString, VDouble, VEnum, VInt, VBool, DState, Sequence, \
    SeqAttributeItem, HasConfigSequence

from malcolm.devices import DetectorDriver


class DtacqDriver(HasConfigSequence, RunnableDevice, DetectorDriver):
    class_attributes = dict(
        prefix=Attribute(VString, "PV Prefix for driver"),
        trig_prefix=Attribute(VString, "PV Prefix for trig plugin"),
        roi_prefix=Attribute(VString, "PV Prefix for roi plugin"),
        sample_freq=Attribute(VInt, "Sample frequency of ADC in Hz"),
    )

    def __init__(self, name, prefix, trig_prefix, roi_prefix,
                 sample_freq=10000):
        self.prefix = prefix
        self.trig_prefix = trig_prefix
        self.roi_prefix = roi_prefix
        self.sample_freq = sample_freq
        super(DtacqDriver, self).__init__(name)

    def add_all_attributes(self):
        super(DtacqDriver, self).add_all_attributes()
        p = self.prefix
        tp = self.trig_prefix
        rp = self.roi_prefix
        self.add_attributes(
            # Configure
            exposure=Attribute(
                VDouble, "Exposure time for each frame"),
            period=Attribute(
                VDouble, "Dummy period"),
            arrayCounter=Attribute(
                VInt, "Starting unique ID"),
            postcount=PvAttribute(
                tp + "POSTCOUNT", VInt,
                "How many samples to take after each trigger"),
            roibin=PvAttribute(
                rp + "BinY", VInt,
                "How many samples to bin in each frame",
                rbv_suff="_RBV"),
            roisize=PvAttribute(
                rp + "SizeY", VInt,
                "How many samples for each frame",
                rbv_suff="_RBV"),
            roidiv=PvAttribute(
                rp + "Scale", VInt,
                "Divide output array by this number",
                rbv_suff="_RBV"),
            imageMode=PvAttribute(
                tp + "TriggerMode", VEnum("Single,Multiple,Continuous"),
                "How many images to take when acquire is started"),
            numImages=PvAttribute(
                tp + "TriggerCount", VInt,
                "Number of images to take if imageMode=Multiple"),
            triggerTotal=PvAttribute(
                tp + "TriggerTotal", VInt,
                "Current unique id number for frame",
                rbv_suff="_RBV"),
            arrayCallbacks=PvAttribute(
                p + "ArrayCallbacks", VBool,
                "Whether to produce images or not",
                rbv_suff="_RBV"),
            enableTrig=PvAttribute(
                tp + "EnableCallbacks", VBool,
                "Enable trigger plugin",
                rbv_suff="_RBV"),
            enableRoi=PvAttribute(
                rp + "EnableCallbacks", VBool,
                "Enable roi plugin",
                rbv_suff="_RBV"),
            # Run
            acquire=PvAttribute(
                p + "Acquire", VBool,
                "Demand and readback for starting acquisition",
                put_callback=False),
            capture=PvAttribute(
                tp + "Capture", VBool,
                "Demand and readback for starting trig acquisition",
                put_callback=False),
            # Monitor
            portName=PvAttribute(
                rp + "PortName_RBV", VString,
                "Port name of this trig plugin"),
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
        postcount = int(exposure*self.sample_freq)
        roibin = postcount
        roisize = postcount
        runTime = numImages * exposure
        roidiv = postcount
        triggerTotal = arrayCounter + 1
        runTimeout = runTime + 1.5
        return super(DtacqDriver, self).validate(locals())

    def make_config_sequence(self, **config_params):
        """Return a Sequence object that can be used for configuring"""
        # make some sequences for config
        sconfig = Sequence(
            self.name + ".SConfig",
            SeqAttributeItem(
                "Configuring parameters", self.attributes,
                imageMode="Multiple",
                arrayCallbacks=1,
                enableTrig=1,
                enableRoi=1,
                **config_params)
        )
        return sconfig

    def do_run(self):
        """Start doing a run.
        Return DState.Running, message when started
        """
        self.capture = True
        self.acquire = True
        return DState.Running, "Running started"

    def do_running(self, value, changes):
        """Work out if the changes mean running is complete.
        Return None, message if it isn't.
        Return DState.Idle, message if it is and we are all done
        Return DState.Ready, message if it is and we are partially done
        """
        if "capture.value" in changes and not self.capture:
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
            self.capture = False
        self.post_changes(None, None)
        return DState.Aborting, "Aborting started"

    def do_aborting(self, value, changes):
        """Work out if the changes mean aborting is complete.
        Return None, message if it isn't.
        Return DState.Aborted, message if it is.
        """
        if not self.capture:
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
