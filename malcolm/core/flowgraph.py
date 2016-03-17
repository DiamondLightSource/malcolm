from .device import Device
from .attribute import Attribute
from malcolm.core.vtype import VStringArray, VString, VDouble
from malcolm.core.method import wrap_method


class FlowGraph(Device):

    def add_all_attributes(self):
        super(FlowGraph, self).add_all_attributes()
        self.add_attributes(
            blocks=Attribute(VStringArray, "Child block names"),
            visibility=Attribute(VString, "Visibility block name"),
            X_COORD=Attribute(VDouble, "X co-ordinate for flowgraph centre"),
            Y_COORD=Attribute(VDouble, "Y co-ordinate for flowgraph centre"),
        )

    @wrap_method()
    def _set_coords(self, X_COORD, Y_COORD):
        self.X_COORD = X_COORD
        self.Y_COORD = Y_COORD
