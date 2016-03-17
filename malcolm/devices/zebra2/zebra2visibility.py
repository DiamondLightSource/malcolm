from malcolm.core.device import Device
from malcolm.core import Attribute
from malcolm.core.vtype import VEnum
from malcolm.core.method import ClientMethod
from collections import OrderedDict


class Zebra2Visibility(Device):
    def __init__(self, name, blocks):
        super(Zebra2Visibility, self).__init__(name)
        self._blocks = blocks
        for block in self._blocks.values():
            self.add_visibility_func(block)

    def add_visibility_func(self, block):
        attr = Attribute(VEnum("Hide,Show"), "Does this appear in flowgraph")
        self.add_attribute(block.BLOCKNAME, attr)
        set_name = "_set_visible"

        def set_func(device, **args):
            block._set_visible(**args)

        method = ClientMethod(set_name, set_name, set_func)
        arg = dict(type=attr.typ, descriptor=attr.descriptor)
        method.in_arguments = OrderedDict([(attr.name, arg)])
        setattr(self, set_name, method)
        self.add_method(method)
        attr.tags.append("method:{}".format(set_name))
