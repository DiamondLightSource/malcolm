from malcolm.core.device import Device
from malcolm.core import Attribute
from malcolm.core.vtype import VEnum, VBool
from malcolm.core.method import ClientMethod
from collections import OrderedDict


class Zebra2Visibility(Device):
    def __init__(self, name, blocks):
        super(Zebra2Visibility, self).__init__(name)
        self._blocks = blocks
        for block in self._blocks.values():
            self.add_visibility_func(block)

    def make_group(self, name):
        if name not in self.attributes:
            attr = Attribute(VBool, name)
            self.add_attribute(name, attr)

    def add_visibility_func(self, block):
        groupname = block.BLOCKNAME.rstrip("1234567890")
        tags = ["widget:toggle"]
        if groupname != block.BLOCKNAME:
            self.make_group(groupname)
            tags += ["group:%s" % groupname]
        attr = Attribute(VEnum("Hide,Show"), "Does this appear in flowgraph",
                         tags=tags)
        self.add_attribute(block.BLOCKNAME, attr)
        setattr(self, block.BLOCKNAME, "Hide")
        set_name = "_set_%s_visible" % block.BLOCKNAME

        def set_func(device, **args):
            block._set_visible(args[block.BLOCKNAME])

        method = ClientMethod(set_name, set_name, set_func)
        arg = dict(type=attr.typ, descriptor=attr.descriptor)
        method.in_arguments = OrderedDict([(attr.name, arg)])
        setattr(self, set_name, method)
        self.add_method(method)
        attr.tags.append("method:{}".format(set_name))

        def update_attr(value, changes):
            attr.update(value)

        block.add_listener(update_attr, "attributes.VISIBLE.value")
