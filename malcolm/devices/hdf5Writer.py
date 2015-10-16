import os

from malcolm.core import RunnableDevice, Attribute, PvAttribute, DState, \
    wrap_method, VString, VEnum, VInt, VBool, Sequence, \
    AttributeSeqItem


class Hdf5Writer(RunnableDevice):
    class_attributes = dict(
        prefix=Attribute(VString, "PV Prefix for device"))

    def __init__(self, name, prefix, timeout=None):
        self.prefix = prefix
        super(Hdf5Writer, self).__init__(name, timeout)
        self._make_config()

    def add_all_attributes(self):
        super(Hdf5Writer, self).add_all_attributes()
        p = self.prefix
        self.add_attributes(
            # Configure
            enableCallbacks=PvAttribute(
                p + "EnableCallbacks", VBool,
                "Enable plugin to run when we get a new frame",
                rbv_suff="_RBV"),
            fileWriteMode=PvAttribute(
                p + "FileWriteMode", VEnum("Single,Capture,Stream"),
                "Write single, capture then write, or stream as captured",
                rbv_suff="_RBV"),
            filePath=PvAttribute(
                p + "FilePath", VString,
                "Directory to write files into",
                rbv_suff="_RBV", long_string=True),
            fileName=PvAttribute(
                p + "FileName", VString,
                "Filename within directory",
                rbv_suff="_RBV", long_string=True),
            fileTemplate=PvAttribute(
                p + "FileTemplate", VString,
                "File template of full file path",
                rbv_suff="_RBV", long_string=True),
            posNameDimN=PvAttribute(
                p + "PosNameDimN", VString,
                "Attribute that position plugin will write DimN index into",
                rbv_suff="_RBV"),
            posNameDimX=PvAttribute(
                p + "PosNameDimX", VString,
                "Attribute that position plugin will write DimN index into",
                rbv_suff="_RBV"),
            posNameDimY=PvAttribute(
                p + "PosNameDimY", VString,
                "Attribute that position plugin will write DimN index into",
                rbv_suff="_RBV"),
            ndAttributeChunk=PvAttribute(
                p + "NDAttributeChunk", VBool,
                "How many frames between flushing attribute arrays",
                rbv_suff="_RBV"),
            swmrMode=PvAttribute(
                p + "SWMRMode", VBool,
                "Whether to write single writer multiple reader files",
                rbv_suff="_RBV"),
            positionMode=PvAttribute(
                p + "PositionMode", VBool,
                "Whether to write in block got from attributes PosName<dim>",
                rbv_suff="_RBV"),
            dimAttDatasets=PvAttribute(
                p + "DimAttDatasets", VBool,
                "Whether to write attributes in same dimensionality as data",
                rbv_suff="_RBV"),
            numExtraDims=PvAttribute(
                p + "NumExtraDims", VInt,
                "How many extra dimensions. "
                "0=(N,...), 1=(X,N,...), 2=(Y,X,N,...)",
                rbv_suff="_RBV"),
            extraDimSizeN=PvAttribute(
                p + "ExtraDimSizeN", VInt,
                "Size of extra dimesion N",
                rbv_suff="_RBV"),
            extraDimSizeX=PvAttribute(
                p + "ExtraDimSizeX", VInt,
                "Size of extra dimesion X",
                rbv_suff="_RBV"),
            extraDimSizeY=PvAttribute(
                p + "ExtraDimSizeY", VInt,
                "Size of extra dimesion Y",
                rbv_suff="_RBV"),
            lazyOpen=PvAttribute(
                p + "LazyOpen", VBool,
                "If true then don't require a dummy frame to get dims",
                rbv_suff="_RBV"),
            numCapture=PvAttribute(
                p + "NumCapture", VInt,
                "Number of frames to capture",
                rbv_suff="_RBV"),
            # Run
            capture=PvAttribute(
                p + "Capture", VBool,
                "Start a capture",
                put_callback=False),
            # Monitor
            uniqueId=PvAttribute(
                p + "UniqueId_RBV", VInt,
                "Current unique id number for frame"),
        )
        self.add_listener(self.on_capture_change, "attributes.capture")

    def on_capture_change(self, capture, changes):
        if self.state == DState.Running:
            self.post_runsta()
        elif self.state == DState.Aborting:
            self.post_abortsta()

    def _make_config(self):
        # make some sequences for config
        s1 = AttributeSeqItem(
            "Configuring parameters",
            enableCallbacks=True,
            fileWriteMode="Stream",
            fileTemplate="%s%s",
            ndAttributeChunk=True,
            swmrMode=True,
            positionMode=True,
            dimAttDatasets=True,
            lazyOpen=True,
            # numCapture=0,
            **self.validate.arguments  # all the config params
        )
        # Add a configuring object
        self._pconfig = Sequence(self.name + ".Config", self.attributes, s1)
        self.add_listener(self._pconfig.on_change, "attributes")
        self._pconfig.add_listener(self.on_pconfig_change, "stateMachine")
        self.add_loop(self._pconfig)

    def on_pconfig_change(self, sm, changes):
        if self.state == DState.Configuring:
            self.post_configsta(sm.state, sm.message)
        elif self.state == DState.Ready and \
                sm.state != self._pconfig.SeqState.Ready:
            self.post_error(sm.message)
        elif self.state == DState.Aborting:
            self.post_abortsta()

    @wrap_method()
    def validate(self, filePath, fileName, numExtraDims=0,
                 posNameDimN="n", posNameDimX="x", posNameDimY="y",
                 extraDimSizeN=1, extraDimSizeX=1, extraDimSizeY=1):
        assert os.path.isdir(filePath), \
            "{} is not a directory".format(filePath)
        assert "." in fileName, \
            "File extension for {} should be supplied".format(fileName)
        if filePath[-1] != os.sep:
            filePath += os.sep
        fullPath = filePath + fileName
        assert not os.path.isfile(fullPath), \
            "{} already exists".format()
        return super(Hdf5Writer, self).validate(locals())

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
        assert self._pconfig.state in self._pconfig.rest_states(), \
            "Can't configure sub-state machine in {} state" \
            .format(self._pconfig.state)
        self._pconfig.start(config_params)
        return DState.Configuring, "Started configuring"

    def do_configsta(self, state, message):
        """Do the next param in self.config_params, returning
        DState.Configuring if still in progress, or DState.Ready if done.
        """
        if state in self._pconfig.rest_states():
            assert state == self._pconfig.SeqState.Ready, \
                "Configuring failed: {}".format(message)
            state = DState.Ready
        else:
            state = DState.Configuring
        return state, message

    def do_run(self):
        """Start doing a run, stopping when it calls back
        """
        self.capture = True
        return DState.Running, "Running started"

    def do_runsta(self):
        """If acquiring then return
        """
        if self.capture:
            # No change
            return None, None
        else:
            return DState.Idle, "Running finished"

    def do_abort(self):
        """Stop acquisition
        """
        if self.state == DState.Configuring:
            if self._pconfig.state not in self._pconfig.rest_states():
                # Abort configure
                self._pconfig.abort()
            else:
                # Statemachine already done, nothing to do
                self.post_abortsta()
        else:
            # Abort run
            self.capture = False
        return DState.Aborting, "Aborting started"

    def do_abortsta(self):
        """Check we finished
        """
        if not self.capture and \
                self._pconfig.state in self._pconfig.rest_states():
            return DState.Aborted, "Aborting finished"
        else:
            # No change
            return None, None
