import os
from xml.etree import ElementTree as ET

from malcolm.core import RunnableDevice, Attribute, PvAttribute, DState, \
    wrap_method, VString, VEnum, VInt, VBool, Sequence, \
    SeqAttributeItem


class Hdf5Writer(RunnableDevice):
    class_attributes = dict(
        prefix=Attribute(VString, "PV Prefix for device"))

    def __init__(self, name, prefix, timeout=None):
        self.prefix = prefix
        super(Hdf5Writer, self).__init__(name, timeout)
        self._make_sconfig()

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
            xml=PvAttribute(
                p + "XMLFileName", VString,
                "XML for layout",
                rbv_suff="_RBV", long_string=True),
            arrayPort=PvAttribute(
                p + "NDArrayPort", VString,
                "Port name of array producer",
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
            writeStatus=PvAttribute(
                p + "WriteStatus", VEnum("Ok,Error"),
                "Current status of write"),
            writeMessage=PvAttribute(
                p + "WriteMessage", VString,
                "Error message if writeStatus == Error",
                long_string=True),
            portName=PvAttribute(
                p + "PortName_RBV", VString,
                "Port name of this plugin"),                            
        )
        self.add_listener(self.on_capture_change, "attributes.capture")
        self.add_listener(self.on_writestatus_change,
                          "attributes.writeStatus.value")

    def on_capture_change(self, capture, changes):
        if self.state == DState.Running:
            self.post_runsta()
        elif self.state == DState.Aborting:
            self.post_abortsta()

    def on_writestatus_change(self, writestatus, changes):
        if writestatus == "Error" and self.state not in DState.rest():
            print "**post error"
            self.post_error(self.writeMessage)

    def _make_sconfig(self):
        # make some sequences for config
        s1 = SeqAttributeItem(
            "Configuring parameters", self.attributes,
            enableCallbacks=True,
            fileWriteMode="Stream",
            fileTemplate="%s%s",
            ndAttributeChunk=True,
            swmrMode=True,
            positionMode=True,
            dimAttDatasets=True,
            lazyOpen=True,
            #xml=None,
            # numCapture=0,
            **self.validate.arguments  # all the config params
        )
        s1.set_extra(always=["capture"])
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
    def validate(self, filePath, fileName, numExtraDims=0,
                 posNameDimN="n", posNameDimX="x", posNameDimY="y",
                 extraDimSizeN=1, extraDimSizeX=1, extraDimSizeY=1,
                 arrayPort=None):
        assert os.path.isdir(filePath), \
            "{} is not a directory".format(filePath)
        assert "." in fileName, \
            "File extension for {} should be supplied".format(fileName)
        if filePath[-1] != os.sep:
            filePath += os.sep
        return super(Hdf5Writer, self).validate(locals())

    def _make_xml(self, config_params):
        root_el = ET.Element("hdf5_layout")
        entry_el = ET.SubElement(root_el, "group", name="entry")
        ET.SubElement(entry_el, "attribute", name="NX_class",
                      source="constant", value="NXentry", type="string")
        data_el = ET.SubElement(entry_el, "group", name="data")
        ET.SubElement(data_el, "attribute", name="signal", source="constant",
                      value="det1", type="string")
        ET.SubElement(data_el, "attribute", name="axes", source="constant",
                      value="axis1_demand,axis2_demand,.,.,.", type="string")
        ET.SubElement(data_el, "attribute", name="NX_class", source="constant",
                      value="NXdata", type="string")
        ET.SubElement(data_el, "attribute", name="axis1_demand_indices",
                      source="constant", value="0", type="string")
        ET.SubElement(data_el, "attribute", name="axis2_demand_indices",
                      source="constant", value="1", type="string")

    def do_config(self, **config_params):
        """Start doing a configuration using config_params"""
        assert self._sconfig.state in self._sconfig.rest_states(), \
            "Can't configure sub-state machine in {} state" \
            .format(self._sconfig.state)
        self.capture = False
        # config_params.update(xml=self._make_xml(config_params))
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
            if self._sconfig.state not in self._sconfig.rest_states():
                # Abort configure
                self._sconfig.abort()
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
                self._sconfig.state in self._sconfig.rest_states():
            return DState.Aborted, "Aborting finished"
        else:
            # No change
            return None, None

    def do_reset(self):
        """Check and attempt to clear any error state, arranging for a
        callback doing self.post(DEvent.ResetSta, resetsta) when progress has
        been made, where resetsta is any device specific reset status
        """
        self.capture = False
        self.post_resetsta(None)
        return DState.Resetting, "Resetting started"

    def do_resetsta(self, resetsta):
        """Examine configsta for configuration progress, returning
        DState.Resetting if still in progress, or DState.Idle if done.
        """
        return DState.Idle, "Resetting finished"

