from malcolm.core.device import Device
from malcolm.core import Attribute
from malcolm.core.vtype import VEnum, VBool, VInt, VTable, VString, VDouble
from malcolm.core.method import ClientMethod
from collections import OrderedDict


class Zebra2Block(Device):

    def __init__(self, name, comms, field_data):
        self.comms = comms
        self.field_data = field_data
        self._configurable = OrderedDict()
        super(Zebra2Block, self).__init__(name)
        # Now add a configuration method
        self.configure = ClientMethod("configure", "Configure blocks",
                                      Zebra2Block.configure)
        self.configure.in_arguments = OrderedDict()
        for name in self._configurable:
            attr = self.attributes[name]
            arg = dict(type=attr.typ, descriptor=attr.descriptor)
            self.configure.in_arguments[name] = arg
        self.add_method(self.configure)

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
        elif typ == "enum":
            block = self.name.split(":", 1)[1]
            labels = self.comms.get_enum_labels(block, field)
            assert labels.keys() == range(len(labels)), \
                "Can't deal with {}".format(labels)
            ret[field] = Attribute(VEnum(labels.values()), field)
        elif typ == "uint":
            ret[field] = Attribute(VInt, field)
        elif typ == "lut":
            ret[field] = Attribute(VString, field)
        elif typ == "position":
            ret[field] = Attribute(VDouble, field)
            ret[field + "_UNITS"] = Attribute(
                VString, field + " position units")
            ret[field + "_SCALE"] = Attribute(
                VString, field + " scale")
            ret[field + "_OFFSET"] = Attribute(
                VString, field + " offset")
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

    def make_in_attribute(self, field, typ):
        # TODO: should be an enum
        attr = Attribute(VString, field)
        self.add_attribute(field, attr)
        self._configurable[field] = attr

    def make_bit_in_attribute(self, field, typ):
        assert typ == "bit_mux", "Field {} Class bit_in Type {} not handled" \
            .format(field, typ)
        self.make_in_attribute(field, typ)

    def make_pos_in_attribute(self, field, typ):
        assert typ == "pos_mux", "Field {} Class pos_in Type {} not handled" \
            .format(field, typ)
        self.make_in_attribute(field, typ)

    def make_out_attribute(self, field, typ):
        self.make_read_attribute(field, typ)
        field = field + "_CAPTURE"
        attr = Attribute(VBool, "Capture {} in PCAP?".format(field))
        self.add_attribute(field, attr)
        self._configurable[field] = attr

    def make_bit_out_attribute(self, field, typ):
        assert typ == "bit", "Field {} Class bit_out Type {} not handled" \
            .format(field, typ)
        self.make_out_attribute(field, typ)

    def make_pos_out_attribute(self, field, typ):
        assert typ == "position", "Field {} Class pos_out Type {} not handled" \
            .format(field, typ)
        self.make_out_attribute(field, typ)

    def make_table_attribute(self, field, typ):
        assert typ == "", "Field {} Class table Type {} not handled" \
            .format(field, typ)
        # TODO: get column headings from server when it supports it
        attr = Attribute(VTable, field)
        self.add_attribute(field, attr)
        self._configurable[field] = attr

    def make_time_attribute(self, field, typ):
        assert typ == "", "Field {} Class table time {} not handled" \
            .format(field, typ)
        attr = Attribute(VDouble, field)
        self.add_attribute(field, attr)
        self._configurable[field] = attr
        attr = Attribute(VEnum("s,ms,us"), field + " time units")
        field = field + "_UNITS"
        self.add_attribute(field, attr)
        self._configurable[field] = attr
