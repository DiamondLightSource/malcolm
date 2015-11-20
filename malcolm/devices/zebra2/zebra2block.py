from malcolm.core.device import Device
from malcolm.core import Attribute
from malcolm.core.vtype import VEnum, VBool, VInt, VTable, VString, VDouble


class Zebra2Block(Device):

    def __init__(self, name, comms, field_data):
        self.comms = comms
        self.field_data = field_data
        self._configurable = []
        super(Zebra2Block, self).__init__(name)
        # Now add a configuration method
        

    def add_all_attributes(self):
        super(Zebra2Block, self).add_all_attributes()
        for field, (cls, typ) in self.field_data.items():
            f = getattr(self, "make_{}_attribute".format(cls))
            f(field, typ)

    def make_read_attribute(self, field, typ):
        if typ == "action":
            attribute = Attribute(VBool, field)
        elif typ == "bit":
            attribute = Attribute(VBool, field)
        elif typ == "enum":
            block = self.name.split(":", 1)[1]
            labels = self.comms.get_enum_labels(block, field)
            assert labels.keys() == range(len(labels)), \
                "Can't deal with {}".format(labels)
            attribute = Attribute(VEnum(labels.values()), field)
        elif typ == "uint":
            attribute = Attribute(VInt, field)
        elif typ == "lut":
            attribute = Attribute(VString, field)
        elif typ == "position":
            attribute = Attribute(VDouble, field)
        elif typ == "scaled_time":
            attribute = Attribute(VDouble, field)
        else:
            raise AssertionError(
                "Field {} Type {} not recognised".format(field, typ))
        self.add_attribute(field, attribute)

    def make_write_attribute(self, field, typ):
        self.make_read_attribute(field, typ)
        # TODO: add action method

    def make_param_attribute(self, field, typ):
        self.make_read_attribute(field, typ)
        self._configurable.append(field)

    def make_bit_in_attribute(self, field, typ):
        assert typ == "bit_mux", "Field {} Class bit_in Type {} not handled" \
            .format(field, typ)
        self.add_attribute(field, Attribute(VString, field))
        self._configurable.append(field)

    def make_bit_out_attribute(self, field, typ):
        assert typ == "bit", "Field {} Class bit_out Type {} not handled" \
            .format(field, typ)
        self.add_attribute(field, Attribute(VBool, field))

    def make_pos_in_attribute(self, field, typ):
        assert typ == "pos_mux", "Field {} Class pos_in Type {} not handled" \
            .format(field, typ)
        # TODO: should be an enum
        self.add_attribute(field, Attribute(VString, field))
        self._configurable.append(field)

    def make_pos_out_attribute(self, field, typ):
        assert typ == "position", "Field {} Class pos_out Type {} not handled" \
            .format(field, typ)
        self.add_attribute(field, Attribute(VInt, field))

    def make_table_attribute(self, field, typ):
        assert typ == "", "Field {} Class table Type {} not handled" \
            .format(field, typ)
        # TODO: get column headings from server when it supports it
        self.add_attribute(field, Attribute(VTable, field))
        self._configurable.append(field)
