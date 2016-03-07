from malcolm.core.device import Device
from malcolm.core import Attribute
from malcolm.core.vtype import VEnum, VBool, VInt, VTable, VString, VDouble
from malcolm.core.method import ClientMethod, wrap_method
from collections import OrderedDict


class Zebra2Block(Device):

    def __init__(self, name, block, i, comms, field_data):
        self.comms = comms
        self.field_data = field_data
        self._configurable = OrderedDict()
        self.block = block
        self.i = str(i)
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
            USE=Attribute(VBool, "Does this appear in flowgraph"),
            BLOCKNAME=Attribute(VString, "Block name for connections"),
        )
        self.X_COORD = 0
        self.Y_COORD = 0
        self.USE = 0
        self.BLOCKNAME = self.block + self.i

    @wrap_method()
    def _set_coords(self, X_COORD, Y_COORD):
        self.X_COORD = X_COORD
        self.Y_COORD = Y_COORD

    def make_read_attribute(self, field, typ):
        ret = OrderedDict()
        desc = self.comms.get_desc(".".join((self.block, field)))
        if typ == "action":
            ret[field] = Attribute(VBool, desc)
        elif typ == "bit":
            ret[field] = Attribute(VBool, desc,
                                   tags=["flowgraph:outport:bit"])
        elif typ == "enum":
            enums = self.comms.get_enum_labels(".".join((self.block, field)))
            ret[field] = Attribute(VEnum(enums), desc)
        elif typ in ["int", "uint"]:
            ret[field] = Attribute(VInt, desc)
        elif typ == "lut":
            ret[field] = Attribute(VString, desc)
        elif typ == "position":
            ret[field] = Attribute(VDouble, desc,
                                   tags=["flowgraph:outport:pos"])
            ret[field + ":UNITS"] = Attribute(
                VString, field + " position units")
            ret[field + ":SCALE"] = Attribute(
                VString, field + " scale")
            ret[field + ":OFFSET"] = Attribute(
                VString, field + " offset")
        elif typ == "time":
            ret[field] = Attribute(VDouble, desc)
            ret[field + ":UNITS"] = Attribute(
                VString, field + " time units")
        else:
            raise AssertionError(
                "Field {} Type {} not recognised".format(field, typ))
        for name, attr in ret.items():
            self.add_attribute(name, attr)
        return ret

    def make_write_attribute(self, field, typ):
        self.make_read_attribute(field, typ)
        # TODO: add action method

    def make_param_attribute(self, field, typ):
        ret = self.make_read_attribute(field, typ)
        self._configurable.update(ret)

    def make_bit_mux_attribute(self, field, typ):
        # TODO: caching won't catch this!
        desc = self.comms.get_desc(".".join((self.block, field)))
        enums = self.comms.get_enum_labels(".".join((self.block, field)))
        attr = Attribute(VEnum(enums), desc, tags=["flowgraph:inport:pos"])
        self.add_attribute(field, attr)
        self._configurable[field] = attr
        self.add_attribute(field + ":VAL", Attribute(
            VBool, field + " current value"))
        attr = Attribute(VInt, field + " clock ticks delay")
        self.add_attribute(field + ":DELAY", attr)
        self._configurable[field + ":DELAY"] = attr

    def make_pos_mux_attribute(self, field, typ):
        # TODO: caching won't catch this!
        desc = self.comms.get_desc(".".join((self.block, field)))
        enums = self.comms.get_enum_labels(".".join((self.block, field)))
        attr = Attribute(VEnum(enums), desc, tags=["flowgraph:inport:pos"])
        self.add_attribute(field, attr)
        self._configurable[field] = attr
        self.add_attribute(field + ":VAL", Attribute(
            VDouble, field + " current value"))

    def make_bit_out_attribute(self, field, typ):
        assert typ == "", "Field {} Class bit_out Type {} not handled" \
            .format(field, typ)
        self.make_read_attribute(field, "bit")
        # TODO: allow capture

    def make_pos_out_attribute(self, field, typ):
        ret = self.make_read_attribute(field, "position")
        for name, attr in ret.items():
            if ":" in name:
                self._configurable[name] = attr
        if typ != "const":
            enums = self.comms.get_enum_labels(
                ".".join((self.block, field, "CAPTURE")))
            field = field + ":CAPTURE"
            attr = Attribute(VEnum(enums), "Capture {} in PCAP?".format(field))
            self.add_attribute(field, attr)
            self._configurable[field] = attr

    def make_ext_out_attribute(self, field, typ):
        enums = self.comms.get_enum_labels(
            ".".join((self.block, field, "CAPTURE")))
        field = field + ":CAPTURE"
        attr = Attribute(VEnum(enums), "Capture {} in PCAP?".format(field))
        self.add_attribute(field, attr)
        self._configurable[field] = attr

    def make_table_attribute(self, field, typ):
        assert typ == "", "Field {} Class table Type {} not handled" \
            .format(field, typ)
        # TODO: get column headings from server when it supports it
        desc = self.comms.get_desc(".".join((self.block, field)))
        attr = Attribute(VTable, desc)
        self.add_attribute(field, attr)
        self._configurable[field] = attr

    def make_short_table_attribute(self, field, typ):
        self.make_table_attribute(field, typ)

    def make_time_attribute(self, field, typ):
        assert typ == "", "Field {} Class table time {} not handled" \
            .format(field, typ)
        desc = self.comms.get_desc(".".join((self.block, field)))
        attr = Attribute(VDouble, desc)
        self.add_attribute(field, attr)
        self._configurable[field] = attr
        attr = Attribute(VEnum("s,ms,us"), field + " time units")
        field = field + ":UNITS"
        self.add_attribute(field, attr)
        self._configurable[field] = attr
