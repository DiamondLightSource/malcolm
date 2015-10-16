from xml.etree import ElementTree as ET

import numpy

from malcolm.core import RunnableDevice, Attribute, wrap_method, PvAttribute, \
    VString, VInt, VBool, DState, VTable, VIntArray, VNumber, Sequence, \
    AttributeSeqItem


class PositionPlugin(RunnableDevice):
    class_attributes = dict(
        prefix=Attribute(VString, "PV Prefix for device"))

    def __init__(self, name, prefix, timeout=None):
        self.prefix = prefix
        super(PositionPlugin, self).__init__(name, timeout)
        self._make_config()

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
            # Run
            running=PvAttribute(
                p + "Running", VBool,
                "Start a run",
                put_callback=False),
            # Monitor
            dimensions=Attribute(
                VIntArray, "Detected dimensionality of positions"),
            uniqueId=PvAttribute(
                p + "UniqueId_RBV", VInt,
                "Current unique id number for frame"),
        )
        self.add_listener(self.on_running_change, "attributes.running")

    def on_running_change(self, running, changes):
        if self.state == DState.Running:
            self.post_runsta()
        elif self.state == DState.Aborting:
            self.post_abortsta()

    def _make_xml(self, config_params):
        # Now calculate dimensionality
        positions = config_params["positions"]
        uniq = [sorted(set(data)) for _, _, data in positions]
        dims = [len(pts) for pts in uniq]
        npts = len(positions[0][2])
        if numpy.prod(dims) == npts:
            # If the product of dimensions is the length of the points, we can
            # assume this is a square scan and write it as such
            self.dimensions = dims
            indexes = uniq
        else:
            # Non square scan, should be written as long list
            self.dimensions = [npts]
            indexes = None
        # Make xml
        root_el = ET.Element("pos_layout")
        dimensions_el = ET.SubElement(root_el, "dimensions")
        names = [column[0] for column in positions]
        for name in names:
            ET.SubElement(dimensions_el, "dimension", name=name)
            if indexes:
                ET.SubElement(dimensions_el, "dimension", name=name + "_index")
        ET.SubElement(dimensions_el, "dimension", name="filePluginClose")
        positions_el = ET.SubElement(root_el, "positions")
        data = [column[2] for column in positions]
        for d in zip(*data):
            attribs = dict(filePluginClose="0")
            for n, v in zip(names, d):
                attribs[n] = str(v)
            if indexes:
                for i, n, v in zip(indexes, names, d):
                    attribs[n + "_index"] = str(i.index(v))
            last = ET.SubElement(positions_el, "position", **attribs)
        last.attrib["filePluginClose"] = "1"
        xml = ET.tostring(root_el)
        # put it in the config_params dict
        config_params["xml"] = xml

    def _make_config(self):
        # make some sequences for config
        s1 = AttributeSeqItem(
            "Deleting old positions",
            delete=True,
        )
        s1.set_extra(post=self._make_xml)
        s2 = AttributeSeqItem(
            "Configuring positions",
            xml=None,                   # from _make_xml above
            enableCallbacks=True,
            **self.validate.arguments  # all the config params
        )
        s2.set_extra(always=["xml"])
        # Add a configuring object
        self._pconfig = Sequence(
            self.name + ".Config", self.attributes, s1, s2)
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
    def validate(self, positions, idStart=1):
        assert len(positions) in range(1, 4), \
            "Can only do 1..3 position attributes"
        for name, typ, data in positions:
            assert issubclass(typ, VNumber), \
                "Only Number attributes can be stored. Got {}".format(typ)
            assert len(data) > 0, \
                "Must have at least one position"
        assert idStart > 0, \
            "Need idStart {} > 0".format(idStart)
        return super(PositionPlugin, self).validate(locals())

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
        self.running = True
        return DState.Running, "Running started"

    def do_runsta(self):
        """If acquiring then return
        """
        if self.running:
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
            self.running = False
        return DState.Aborting, "Aborting started"

    def do_abortsta(self):
        """Check we finished
        """
        if not self.running and \
                self._pconfig.state in self._pconfig.rest_states():
            return DState.Aborted, "Aborting finished"
        else:
            # No change
            return None, None
