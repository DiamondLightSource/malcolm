from xml.etree import ElementTree as ET

from malcolm.core import RunnableDevice, Attribute, wrap_method, PvAttribute, \
    VString, VInt, VBool, DState, VTable, VIntArray, VNumber, Sequence, \
    SeqAttributeItem, HasConfigSequence


class PositionPlugin(HasConfigSequence, RunnableDevice):
    class_attributes = dict(
        prefix=Attribute(VString, "PV Prefix for device"))

    def __init__(self, name, prefix):
        self.prefix = prefix
        super(PositionPlugin, self).__init__(name)

    def add_all_attributes(self):
        super(PositionPlugin, self).add_all_attributes()
        p = self.prefix
        self.add_attributes(
            # Configure
            positions=Attribute(
                VTable,
                "Position table, column headings are attribute names"),
            enableCallbacks=PvAttribute(
                p + "EnableCallbacks", VBool,
                "Enable plugin to run when we get a new frame",
                rbv_suff="_RBV"),
            delete=PvAttribute(
                p + "Delete", VBool,
                "Delete all positions in the buffer"),
            xml=PvAttribute(
                p + "Filename", VString,
                "Filename of xml or xml text",
                rbv_suff="_RBV", long_string=True),
            idStart=PvAttribute(
                p + "IDStart", VInt,
                "First uid value to look for",
                rbv_suff="_RBV"),
            arrayPort=PvAttribute(
                p + "NDArrayPort", VString,
                "Port name of array producer",
                rbv_suff="_RBV"),
            # Run
            running=PvAttribute(
                p + "Running", VBool,
                "Start a run",
                put_callback=False),
            # Monitor
            uniqueId=PvAttribute(
                p + "UniqueId_RBV", VInt,
                "Current unique id number for frame"),
            portName=PvAttribute(
                p + "PortName_RBV", VString,
                "Port name of this plugin"),
        )
        self.add_listener(self.post_changes, "attributes")

    def _make_xml(self, positions):
        # Make xml
        root_el = ET.Element("pos_layout")
        dimensions_el = ET.SubElement(root_el, "dimensions")
        names = [column[0] for column in positions]
        for name in names:
            ET.SubElement(dimensions_el, "dimension", name=name)
        ET.SubElement(dimensions_el, "dimension", name="FilePluginClose")
        positions_el = ET.SubElement(root_el, "positions")
        data = [column[2] for column in positions]
        for d in zip(*data):
            attribs = dict(FilePluginClose="0")
            for n, v in zip(names, d):
                attribs[n] = str(v)
            last = ET.SubElement(positions_el, "position", **attribs)
        last.attrib["FilePluginClose"] = "1"
        xml = ET.tostring(root_el)
        return xml

    def _validate_positions(self, positions):
        for _, typ, data, _ in positions:
            assert issubclass(typ, VNumber), \
                "Only Number attributes can be stored. Got {}".format(typ)
            assert len(data) > 0, \
                "Must have at least one position"

    @wrap_method()
    def validate(self, positions, idStart=1, arrayPort=None):
        """Check whether a set of configuration parameters is valid or not. Each
        parameter name must match one of the names in self.attributes. This set
        of parameters should be checked in isolation, no device state should be
        taken into account. It is allowed from any DState and raises an error
        if the set of configuration parameters is invalid. It should return
        some metrics on the set of parameters as well as the actual parameters
        that should be used, e.g.
        {"runTime": 1.5, arg1=2, arg2="arg2default"}
        """
        self._validate_positions(positions)
        assert idStart > 0, "Need idStart {} > 0".format(idStart)
        return super(PositionPlugin, self).validate(locals())

    def make_config_sequence(self, **valid_params):
        """Return a Sequence object that can be used for configuring"""
        # Add a configuring object
        sconfig = Sequence(
            self.name + ".SConfig",
            SeqAttributeItem(
                "Deleting old positions", self.attributes,
                delete=True,
            ).always_set(["delete"]),
            SeqAttributeItem(
                "Configuring positions", self.attributes,
                enableCallbacks=True,
                xml=self._make_xml(valid_params["positions"]),
                **valid_params
            ).always_set(["xml"])
        )
        return sconfig

    def do_run(self):
        """Start doing a run.
        Return DState.Running, message when started
        """
        self.running = True
        return DState.Running, "Running started"

    def do_running(self, value, changes):
        """Work out if the changes mean running is complete.
        Return None, message if it isn't.
        Return DState.Idle, message if it is and we are all done
        Return DState.Ready, message if it is and we are partially done
        """
        if "running.value" in changes and not self.running:
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
            self.running = False
        self.post_changes(None, None)
        return DState.Aborting, "Aborting started"

    def do_aborting(self, value, changes):
        """Work out if the changes mean aborting is complete.
        Return None, message if it isn't.
        Return DState.Aborted, message if it is.
        """
        if not self.running:
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
