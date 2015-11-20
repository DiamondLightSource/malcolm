from .device import Device
from .attribute import Attribute
from malcolm.core.vtype import VStringArray


class FlowGraph(Device):

    def add_all_attributes(self):
        super(FlowGraph, self).add_all_attributes()
        self.add_attributes(
            blocks=Attribute(VStringArray, "Child block names")
        )
