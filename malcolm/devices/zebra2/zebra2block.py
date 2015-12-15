from malcolm.core.device import Device
from malcolm.core import Attribute
from malcolm.core.vtype import VEnum, VBool, VInt, VTable, VString, VDouble
from malcolm.core.method import ClientMethod
from collections import OrderedDict


class Zebra2Block(Device):

    def __init__(self, name, comms, field_data, bits, positions):
        self.comms = comms
        self.field_data = field_data
        self.bits = bits
        self.positions = positions
        self._configurable = OrderedDict()
        super(Zebra2Block, self).__init__(name)
        # Now add a setter method for each param
        for attr in self._configurable.values():
            self.make_setter(self.name.split(":")[-1], attr)

    def make_setter(self, block, attr):
        param = attr.name
        set_name = "set_{}".format(param)
        isbool = type(attr.typ) == VBool

        def set_func(device, **args):
            value = args[param]
            if isbool:
                value = int(args[param])
            device.comms.set_field(block, param.replace(":", "."), value)
            setattr(device, param, value)

        method = ClientMethod(set_name, set_name, set_func)
        arg = dict(type=attr.typ, descriptor=attr.descriptor)
        method.in_arguments = OrderedDict([(param, arg)])
        setattr(self, set_name, method)
        self.add_method(method)
        attr.tags.append("method:{}".format(set_name))

    def configure(self, **params):
        for param, val in params.items():
            self.comms.set_field(self.name.split(":")[-1], param, val)

    def add_all_attributes(self):
        super(Zebra2Block, self).add_all_attributes()
        for field, (cls, typ) in self.field_data.items():
            f = getattr(self, "make_{}_attribute".format(cls))
            f(field, typ)

    def make_read_attribute(self, field, typ):
        ret = OrderedDict()
        if typ == "action":
            ret[field] = Attribute(VBool, field)
        elif typ == "bit":
            ret[field] = Attribute(VBool, field)
        elif typ == "bit_mux":
            ret[field] = Attribute(VEnum(self.bits), field)
            self.add_attribute(field + ":VAL", Attribute(
                VBool, field + " current value"))
        elif typ == "enum":
            block = self.name.split(":", 1)[1]
            labels = self.comms.get_enum_labels(block, field)
            ret[field] = Attribute(VEnum(labels), field)
        elif typ == "uint":
            ret[field] = Attribute(VInt, field)
        elif typ == "lut":
            ret[field] = Attribute(VString, field)
        elif typ == "position":
            ret[field] = Attribute(VDouble, field)
            ret[field + ":UNITS"] = Attribute(
                VString, field + " position units")
            ret[field + ":SCALE"] = Attribute(
                VString, field + " scale")
            ret[field + ":OFFSET"] = Attribute(
                VString, field + " offset")
        elif typ == "pos_mux":
            ret[field] = Attribute(VEnum(self.positions), field)
            self.add_attribute(field + ":VAL", Attribute(
                VDouble, field + " current value"))
        elif typ == "time":
            ret[field] = Attribute(VDouble, field)
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

    def make_out_attribute(self, field, typ):
        ret = self.make_read_attribute(field, typ)
        for name, attr in ret.items():
            if ":" in name:
                self._configurable[name] = attr
        field = field + ":CAPTURE"
        attr = Attribute(VBool, "Capture {} in PCAP?".format(field))
        self.add_attribute(field, attr)
        self._configurable[field] = attr

    def make_bit_out_attribute(self, field, typ):
        assert typ == "", "Field {} Class bit_out Type {} not handled" \
            .format(field, typ)
        self.make_out_attribute(field, "bit")

    def make_pos_out_attribute(self, field, typ):
        assert typ == "", "Field {} Class pos_out Type {} not handled" \
            .format(field, typ)
        self.make_out_attribute(field, "position")

    def make_table_attribute(self, field, typ):
        assert typ == "", "Field {} Class table Type {} not handled" \
            .format(field, typ)
        # TODO: get column headings from server when it supports it
        attr = Attribute(VTable, field)
        self.add_attribute(field, attr)
        self._configurable[field] = attr

    def make_short_table_attribute(self, field, typ):
        self.make_table_attribute(field, typ)

    def make_time_attribute(self, field, typ):
        assert typ == "", "Field {} Class table time {} not handled" \
            .format(field, typ)
        attr = Attribute(VDouble, field)
        self.add_attribute(field, attr)
        self._configurable[field] = attr
        attr = Attribute(VEnum("s,ms,us"), field + " time units")
        field = field + ":UNITS"
        self.add_attribute(field, attr)
        self._configurable[field] = attr
