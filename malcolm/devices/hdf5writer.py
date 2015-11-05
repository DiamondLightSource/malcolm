import os
from xml.etree import ElementTree as ET

from malcolm.core import RunnableDevice, Attribute, PvAttribute, DState, \
    wrap_method, VString, VEnum, VInt, VBool, Sequence, \
    SeqAttributeItem, VStringArray, VIntArray, HasConfigSequence


class Hdf5Writer(HasConfigSequence, RunnableDevice):
    class_attributes = dict(
        prefix=Attribute(VString, "PV Prefix for device"),
        readbacks=Attribute(VBool, "Whether this detector produces position "
                            "readbacks rather than data"))

    def __init__(self, name, prefix, readbacks=False, timeout=None):
        self.prefix = prefix
        self.readbacks = readbacks
        super(Hdf5Writer, self).__init__(name, timeout)

    def add_all_attributes(self):
        super(Hdf5Writer, self).add_all_attributes()
        p = self.prefix
        self.add_attributes(
            # Configure
            dimNames=Attribute(
                VStringArray, "List of names of dimensions to write"),
            dimSizes=Attribute(
                VIntArray, "List of sizes of dimensions"),
            dimUnits=Attribute(
                VStringArray, "List of units for dimensions (defaults to mm)"),
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
        self.add_listener(self.post_changes, "attributes")

    @wrap_method()
    def validate(self, filePath, fileName, dimNames, dimSizes,
                 dimUnits=None, arrayPort=None):
        """Check whether a set of configuration parameters is valid or not. Each
        parameter name must match one of the names in self.attributes. This set
        of parameters should be checked in isolation, no device state should be
        taken into account. It is allowed from any DState and raises an error
        if the set of configuration parameters is invalid. It should return
        some metrics on the set of parameters as well as the actual parameters
        that should be used, e.g.
        {"runTime": 1.5, arg1=2, arg2="arg2default"}
        """
        assert os.path.isdir(filePath), \
            "{} is not a directory".format(filePath)
        assert "." in fileName, \
            "File extension for {} should be supplied".format(fileName)
        if filePath[-1] != os.sep:
            filePath += os.sep
        assert len(dimNames) == len(dimSizes), \
            "Mismatch in sizes of dimNames {} and dimSizes {}" \
            .format(dimNames, dimSizes)
        if dimUnits is None:
            dimUnits = ["mm" for x in dimNames]
        else:
            assert len(dimNames) == len(dimUnits), \
                "Mismatch in sizes of dimNames {} and dimUnits {}" \
                .format(dimNames, dimUnits)
        assert len(dimNames) > 0, \
            "Need >0 dimNames, got {}".format(dimNames)
        return super(Hdf5Writer, self).validate(locals())

    def _make_xml(self, dimNames, dimUnits):
        root_el = ET.Element("hdf5_layout")
        entry_el = ET.SubElement(root_el, "group", name="entry")
        ET.SubElement(entry_el, "attribute", name="NX_class",
                      source="constant", value="NXentry", type="string")
        # Make a dataset for the data
        data_el = ET.SubElement(entry_el, "group", name="data")
        ET.SubElement(data_el, "attribute", name="signal", source="constant",
                      value="det1", type="string")
        pad_dims = ['.'] * 5
        for i, dim in enumerate(dimNames):
            pad_dims[i] = "{}_demand".format(dim)
        ET.SubElement(data_el, "attribute", name="axes", source="constant",
                      value=",".join(pad_dims), type="string")
        ET.SubElement(data_el, "attribute", name="NX_class", source="constant",
                      value="NXdata", type="string")
        # Add in the indices into the dimensions array that our axes refer to
        for i, dim in enumerate(dimNames):
            ET.SubElement(data_el, "attribute",
                          name="{}_demand_indices".format(dim),
                          source="constant", value=str(i), type="string")
        # Add in our demand positions
        for dim, units in zip(dimNames, dimUnits):
            axis_el = ET.SubElement(
                data_el, "dataset", name="{}_demand".format(dim),
                source="ndattribute", ndattribute=dim)
            ET.SubElement(axis_el, "attribute", name="units",
                          source="constant", value=units, type="string")
        if self.readbacks:
            # Add in our readback values
            for dim, units in zip(dimNames, dimUnits):
                axis_el = ET.SubElement(
                    data_el, "dataset", name="{}_readback".format(dim),
                    source="ndattribute", ndattribute="{}_rbv".format(dim))
                ET.SubElement(axis_el, "attribute", name="units",
                              source="constant", value=units, type="string")
            # Our figure of merit is the delta
            merit = "delta"
        else:
            # Add in the actual data array
            det1_el = ET.SubElement(data_el, "dataset", name="det1",
                                    source="detector", det_default="true")
            ET.SubElement(det1_el, "attribute", name="NX_class",
                          source="constant", value="SDS", type="string")
            merit = "NDArrayUniqueId"
        # Now add some figure of merit
        merit_el = ET.SubElement(entry_el, "group", name=merit)
        ET.SubElement(merit_el, "attribute", name="signal", source="constant",
                      value=merit, type="string")
        ET.SubElement(merit_el, "attribute", name="NX_class",
                      source="constant", value="NXdata", type="string")
        ET.SubElement(merit_el, "dataset", name=merit, source="ndattribute",
                      ndattribute=merit)
        for dim in dimNames:
            ET.SubElement(merit_el, "hardlink", name="{}_demand".format(dim),
                          target="/entry/data/{}_demand".format(dim))
        NDAttributes_el = ET.SubElement(entry_el, "group", name="NDAttributes",
                                        ndattr_default="true")
        ET.SubElement(NDAttributes_el, "attribute", name="NX_class",
                      source="constant", value="NXcollection", type="string")
        xml = '<?xml version="1.0" ?>' + ET.tostring(root_el)
        return xml

    def make_config_sequence(self, **config_params):
        """Return a Sequence object that can be used for configuring"""
        # Make sure we aren't capturing
        if self.capture:
            self.capture = False
        # Calculate posNames
        dimNames = config_params["dimNames"]
        dimSizes = config_params["dimSizes"]
        dimUnits = config_params["dimUnits"]
        config_params.update(
            xml=self._make_xml(dimNames, dimUnits),
            numExtraDims=len(dimNames) - 1
        )
        # pad dimNames and sizes
        dimNames = [x + "_index" for x in dimNames]
        dimNames += [''] * (3 - len(dimNames))
        dimSizes = list(dimSizes) + [1] * (3 - len(dimSizes))
        config_params.update(
            posNameDimN=dimNames[0], extraDimSizeN=dimSizes[0],
            posNameDimX=dimNames[1], extraDimSizeX=dimSizes[1],
            posNameDimY=dimNames[2], extraDimSizeY=dimSizes[2],
        )
        # make some sequences for config
        # Add a configuring object
        sconfig = Sequence(
            self.name + ".SConfig",
            SeqAttributeItem(
                "Configuring positional placement", self.attributes,
                positionMode=True,
            ),
            SeqAttributeItem(
                "Configuring parameters", self.attributes,
                enableCallbacks=True,
                fileWriteMode="Stream",
                fileTemplate="%s%s",
                ndAttributeChunk=True,
                swmrMode=True,
                dimAttDatasets=True,
                lazyOpen=True,
                numCapture=0,
                **config_params
            ),
        )
        return sconfig

    def do_run(self):
        """Start doing a run.
        Return DState.Running, message when started
        """
        self.capture = True
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
        return DState.Aborting, "Aborting started"

    def do_aborting(self, value, changes):
        """Work out if the changes mean aborting is complete.
        Return None, message if it isn't.
        Return DState.Aborted, message if it is.
        """
        if not self.capture and not self._sconfig.running:
            return DState.Aborted, "Aborting finished"
        else:
            # No change
            return None, None

    def do_reset(self):
        """Start doing a reset from aborted or fault state.
        Return DState.Resetting, message when started
        """
        self.capture = False
        self.post_resetting(None, None)
        return DState.Resetting, "Resetting started"

    def do_resetting(self, value, changes):
        """Work out if the changes mean resetting is complete.
        Return None, message if it isn't.
        Return DState.Idle, message if it is.
        """
        return DState.Idle, "Resetting finished"
