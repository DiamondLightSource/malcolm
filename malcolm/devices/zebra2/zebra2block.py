from malcolm.core.device import Device
from malcolm.core import Attribute
from malcolm.core.vtype import VEnum, VBool, VInt, VTable, VString, VDouble
from malcolm.core.method import ClientMethod, wrap_method
from collections import OrderedDict


class Zebra2Block(Device):

    def __init__(self, name, block, i, comms, field_data, parent):
        self.comms = comms
        self.field_data = field_data
        self._configurable = OrderedDict()
        self.block = block
        self.i = str(i)
        self.parent = parent
        super(Zebra2Block, self).__init__(name)
        # Now add a setter method for each param
        for attr in self._configurable.values():
            self.make_setter(attr)

    def make_setter(self, attr):
        param = attr.name
        set_name = "_set_{}".format(param)
        isbool = type(attr.typ) == VBool

        def set_func(device, **args):
            value = args[param]
            setattr(device, param, value)
            if isbool:
                value = int(args[param])
            device.comms.set_field(
                self.block + self.i, param.replace(":", "."), value)

        method = ClientMethod(set_name, set_name, set_func)
        arg = dict(type=attr.typ, descriptor=attr.descriptor)
        method.in_arguments = OrderedDict([(param, arg)])
        setattr(self, set_name, method)
        self.add_method(method)
        attr.tags.append("method:{}".format(set_name))

    def configure(self, **params):
        for param, val in params.items():
            self.comms.set_field(self.block + self.i, param, val)

    def add_all_attributes(self):
        super(Zebra2Block, self).add_all_attributes()
        for field, (cls, typ) in self.field_data.items():
            f = getattr(self, "make_{}_attribute".format(cls))
            f(field, typ)
        # Add the gui things
        self.add_attributes(
            X_COORD=Attribute(VDouble, "X co-ordinate for flowgraph"),
            Y_COORD=Attribute(VDouble, "Y co-ordinate for flowgraph"),
            VISIBLE=Attribute(VEnum("Hide,Show"),
                              "Does this appear in flowgraph",
                              tags=["widget:choice"]),
            BLOCKNAME=Attribute(VString, "Block name for connections"),
            ICON=Attribute(VString, "Path to icon")
        )
        self.X_COORD = 0
        self.Y_COORD = 0
        self.VISIBLE = 0
        self.BLOCKNAME = self.block + self.i
        # TODO: fixme to be relative when we are hosting web gui
        url = self.process.serverStrings[0].replace("ws://", "http://")
        self.ICON = "{}/icons/{}.svg".format(url, self.block)

    @wrap_method()
    def _set_visible(self, VISIBLE):
        # make a strong version of proxy, yuck!
        self = self.__weakref__.__repr__.__self__
        self.VISIBLE = VISIBLE
        if VISIBLE == "Hide":
            for field in self.attributes:
                # If there are any other blocks connected to a field in the
                # block then set that field to be disconnected
                disconnects = self.parent._muxes.get((self, field), [])
                # Now disconnect any of our mux inputs
                if field in self.field_data and \
                        self.field_data[field][0] in ("bit_mux", "pos_mux"):
                    disconnects.append((self, field))
                # Do the disconnects
                for listen_block, mux_field in disconnects:
                    attr = listen_block.attributes[mux_field]
                    zero = attr.typ.labels[0]
                    setter = getattr(listen_block, attr.put_method_name())
                    setter(zero)
            self.X_COORD = 0
            self.Y_COORD = 0
        else:
            self.X_COORD = self.parent.X_COORD
            self.Y_COORD = self.parent.Y_COORD

    @wrap_method()
    def _set_coords(self, X_COORD, Y_COORD):
        self.X_COORD = X_COORD
        self.Y_COORD = Y_COORD

    def make_group(self, name):
        if name not in self.attributes:
            attr = Attribute(VBool, name)
            self.add_attribute(name, attr)

    def make_attribute(self, field, typ, writeable):
        ret = OrderedDict()
        desc = self.comms.get_desc(".".join((self.block, field)))
        if writeable:
            widget = "widget:textinput"
        else:
            widget = "widget:textupdate"
        if typ == "action":
            ret[field] = Attribute(VBool, desc, tags=["widget:toggle"])
        elif typ == "bit":
            if writeable:
                widget = "widget:toggle"
            else:
                widget = "widget:led"
            ret[field] = Attribute(VBool, desc, tags=[widget])
        elif typ == "enum":
            if writeable:
                widget = "widget:combo"
            enums = self.comms.get_enum_labels(".".join((self.block, field)))
            ret[field] = Attribute(VEnum(enums), desc, tags=[widget])
        elif typ in ["int", "uint"]:
            ret[field] = Attribute(VInt, desc, tags=[widget])
        elif typ == "lut":
            ret[field] = Attribute(VString, desc, tags=["widget:textinput"])
        elif typ == "position":
            ret[field] = Attribute(VDouble, desc, tags=[widget])
            ret[field + ":UNITS"] = Attribute(
                VString, field + " position units", tags=[widget])
            ret[field + ":SCALE"] = Attribute(
                VDouble, field + " scale", tags=[widget])
            ret[field + ":OFFSET"] = Attribute(
                VDouble, field + " offset", tags=[widget])
        elif typ == "time":
            ret[field] = Attribute(VDouble, desc, tags=[widget])
            ret[field + ":UNITS"] = Attribute(
                VEnum("s,ms,us"), field + " time units", tags=["widget:combo"])
        else:
            raise AssertionError(
                "Field {} Type {} not recognised".format(field, typ))
        for name, attr in ret.items():
            self.add_attribute(name, attr)
        return ret

    def make_param_attribute(self, field, typ):
        self.make_group("Parameters")
        ret = self.make_attribute(field, typ, writeable=True)
        for attr in ret.values():
            attr.tags.append("group:Parameters")
        self._configurable.update(ret)

    def make_read_attribute(self, field, typ):
        self.make_group("Readbacks")
        ret = self.make_attribute(field, typ, writeable=False)
        for attr in ret.values():
            attr.tags.append("group:Readbacks")

    def make_write_attribute(self, field, typ):
        self.make_param_attribute(field, typ)

    def make_time_attribute(self, field, typ):
        assert typ == "", "Field {} Class time Type {} not handled" \
            .format(field, typ)
        self.make_param_attribute(field, "time")

    def make_bit_out_attribute(self, field, typ):
        assert typ == "", "Field {} Class bit_out Type {} not handled" \
            .format(field, typ)
        self.make_group("Outputs")
        ret = self.make_attribute(field, "bit", writeable=False)
        ret[field].tags.append("flowgraph:outport:bit")
        for attr in ret.values():
            attr.tags.append("group:Outputs")
        # TODO: allow capture

    def make_pos_out_attribute(self, field, typ):
        self.make_group("Outputs")
        ret = self.make_attribute(field, "position", writeable=False)
        ret[field].tags.append("flowgraph:outport:pos")
        for name, attr in ret.items():
            if ":" in name:
                self._configurable[name] = attr
            attr.tags.append("group:Outputs")
        if typ != "const":
            enums = self.comms.get_enum_labels(
                ".".join((self.block, field, "CAPTURE")))
            attr = Attribute(VEnum(enums), "Capture {} in PCAP?".format(field),
                             tags=["widget:combo"])
            self.add_attribute(field + ":CAPTURE", attr)
            self._configurable[field + ":CAPTURE"] = attr
            attr = Attribute(VInt, field + " cached data to capture from",
                            tags=["widget:textinput"])
            self.add_attribute(field + ":DATA_DELAY", attr)
            self._configurable[field + ":DATA_DELAY"] = attr

    def make_ext_out_attribute(self, field, typ):
        self.make_group("Outputs")
        enums = self.comms.get_enum_labels(
            ".".join((self.block, field, "CAPTURE")))
        field = field + ":CAPTURE"
        attr = Attribute(VEnum(enums), "Capture {} in PCAP?".format(field),
                         tags=["widget:combo"])
        self.add_attribute(field, attr)
        self._configurable[field] = attr
        attr.tags.append("group:Outputs")

    def make_bit_mux_attribute(self, field, typ):
        self.make_group("Inputs")
        # TODO: caching won't catch this!
        desc = self.comms.get_desc(".".join((self.block, field)))
        enums = self.comms.get_enum_labels(".".join((self.block, field)))
        attr = Attribute(VEnum(enums), desc,
                         tags=["flowgraph:inport:pos", "widget:combo",
                               "group:Inputs"])
        self.add_attribute(field, attr)
        self._configurable[field] = attr
        self.add_attribute(field + ":VAL", Attribute(
            VBool, field + " current value", tags=["widget:led"]))
        attr = Attribute(VInt, field + " clock ticks delay",
                         tags=["widget:textinput", "group:Inputs"])
        self.add_attribute(field + ":DELAY", attr)
        self._configurable[field + ":DELAY"] = attr

    def make_pos_mux_attribute(self, field, typ):
        self.make_group("Inputs")
        # TODO: caching won't catch this!
        desc = self.comms.get_desc(".".join((self.block, field)))
        enums = self.comms.get_enum_labels(".".join((self.block, field)))
        attr = Attribute(VEnum(enums), desc,
                         tags=["flowgraph:inport:pos", "widget:combo",
                               "group:Inputs"])
        self.add_attribute(field, attr)
        self._configurable[field] = attr
        self.add_attribute(field + ":VAL", Attribute(
            VDouble, field + " current value", tags=["widget:textupdate",
                                                     "group:Inputs"]))

    def make_table_attribute(self, field, typ):
        assert typ == "", "Field {} Class table Type {} not handled" \
            .format(field, typ)
        # TODO: get column headings from server when it supports it
        self.make_group("Parameters")
        desc = self.comms.get_desc(".".join((self.block, field)))
        attr = Attribute(VTable, desc, tags=["widget:table",
                                             "group:Parameters"])
        self.add_attribute(field, attr)
        self._configurable[field] = attr
