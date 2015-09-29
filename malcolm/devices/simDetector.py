from malcolm.core import RunnableDevice, Attribute, wrap_method
from malcolm.core.pvattribute import PVAttribute
from malcolm.core.vtype import VString, VDouble, VEnum, VInt, VBool
from malcolm.core.runnableDevice import DState


class SimDetector(RunnableDevice):
    class_attributes = dict(
        prefix=Attribute(VString, "PV Prefix for device"))

    def __init__(self, name, prefix, timeout=None):
        self.prefix = prefix
        super(SimDetector, self).__init__(name, timeout)

    def add_all_attributes(self):
        super(SimDetector, self).add_all_attributes()
        p = self.prefix
        self.add_attributes(
            exposure=PVAttribute(
                p + "AcquireTime", VDouble,
                "Exposure time for each frame",
                rbv_suff="_RBV"),
            period=PVAttribute(
                p + "AcquirePeriod", VDouble,
                "Time between the start of each frame",
                rbv_suff="_RBV"),
            imageMode=PVAttribute(
                p + "ImageMode", VEnum("Single,Multiple,Continuous"),
                "How many images to take when acquire is started",
                rbv_suff="_RBV"),
            numImages=PVAttribute(
                p + "NumImages", VInt,
                "Number of images to take if imageMode=Multiple",
                rbv_suff="_RBV"),
            acquire=PVAttribute(
                p + "Acquire", VBool,
                "Demand and readback for starting acquisition"),
            arrayCounter=PVAttribute(
                p + "ArrayCounter", VInt,
                "Current unique id number for frame",
                rbv_suff="_RBV"),
            arrayCallbacks=PVAttribute(
                p + "ArrayCallbacks", VBool,
                "Whether to produce images or not",
                rbv_suff="_RBV"),
        )
        self.config_params = {}
        self.add_listener(self.on_attribute_change, "attributes")

    def assert_idle(self):
        # This is called as a result of caput callback. Sometimes we get
        # a callback before a monitor update, so explicitly call caget
        # to make sure we get the up to date value of acquire
        acquiring = self.attributes["acquire"].rbv.caget()
        assert not acquiring, \
            "Expected to be not acquiring now..."

    @wrap_method()
    def validate(self, exposure, numImages, period=None):
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

    def on_attribute_change(self, attributes, changes):
        prefixes = set(x.split(".")[0] for x in changes)
        assert len(prefixes) == 1, \
            "Only expected one attribute to change at once, got {}" \
            .format(prefixes)
        attr = prefixes.pop()
        if self.state == DState.Configuring:
            self.post_configsta(attr)
        elif self.state == DState.Ready:
            if self._config_mismatches():
                self.post_error()
        elif attr == "acquire" and self.acquire == 0:
            if self.state == DState.Running:
                self.post_runsta()
            elif self.state == DState.Aborting:
                self.post_abortsta()

    def do_config(self, **config_params):
        """Start doing a configuration using config_params"""
        config_params.update(imageMode="Multiple")
        config_params.update(arrayCounter=0)
        config_params.update(arrayCallbacks=1)
        self.config_params = config_params
        # Work out which attributes need to change and set them
        self.config_changed = {}
        for attr, value in sorted(config_params.items()):
            if getattr(self, attr) != value:
                setattr(self, attr, value)
                self.config_changed[attr] = False
        mess = "Configuring {} attributes".format(len(self.config_changed))
        return DState.Configuring, mess

    def _config_mismatches(self):
        "Check if current config matches required"
        mismatches = []
        for attr, value in sorted(self.config_params.items()):
            if getattr(self, attr) != value:
                mismatches.append(attr)
        return mismatches

    def do_configsta(self, attr):
        """Do the next param in self.config_params, returning
        DState.Configuring if still in progress, or DState.Ready if done.
        """
        if attr in self.config_changed:
            self.config_changed[attr] = True
        todo = len([x for x in self.config_changed.values() if x is False])
        if todo:
            return DState.Configuring, "{} attributes left to do".format(todo)
        else:
            return DState.Ready, "Configuring finished"

    def do_run(self):
        """Start doing a run, stopping when it calls back
        """
        self.attributes["acquire"].update(1, callback=False)
        return DState.Running, "Running started"

    def do_runsta(self):
        """If acquiring then return
        """
        assert not self.acquire, "Shouldn't be acquiring"
        return DState.Idle, "Running finished"

    def do_abort(self):
        """Stop acquisition
        """
        self.attributes["acquire"].update(0, callback=False)
        return DState.Aborting, "Aborting started"

    def do_abortsta(self):
        """Check we finished
        """
        assert not self.acquire, "Shouldn't be acquiring"
        return DState.Aborted, "Aborting finished"
