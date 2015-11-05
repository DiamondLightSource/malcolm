from PyQt4.Qt import QTreeWidget, QTreeWidgetItem, QSize


class QDevice(QTreeWidget):
    def __init__(self, device):
        import cothread
        cothread.iqt()
        super(QDevice, self).__init__()
        self.device = device
        # create columns
        self.setColumnCount(2)
        self.setHeaderLabels(["Attribute", "Value"])
        # add statemachine
        top = QTreeWidgetItem(self)
        top.setText(0, "StateMachine")
        self.stateMachine = {}
        for name, value in self.device.stateMachine.to_dict().items():
            # Add an item with a label
            item = QTreeWidgetItem(top)
            item.setText(0, name)
            item.setText(1, repr(value))
            self.stateMachine[name] = item
        # add listener
        self.device.add_listener(self.update_stateMachine, "stateMachine")
        # add a top level item for attributes
        top = QTreeWidgetItem(self)
        top.setText(0, "Attributes")
        self.attributes = {}
        # add attributes
        for name, attr in device.attributes.items():
            # Add an item with a label
            item = QTreeWidgetItem(top)
            item.setText(0, name)
            item.setText(1, repr(attr.value))
            self.attributes[name] = item
        # add listener
        self.device.add_listener(self.update_attributes, "attributes")
        # show self
        self.setWindowTitle(self.device.name)
        self.setColumnWidth(0, 160)
        self.setColumnWidth(1, 200)
        self.resize(QSize(365, 800))
        self.expandAll()
        self.show()

    def update_stateMachine(self, value, changes):
        for c, val in changes.items():
            if c in self.stateMachine:
                self.stateMachine[c].setText(1, repr(val))

    def update_attributes(self, value, changes):
        for c, val in changes.items():
            split = c.split(".")
            if len(split) == 2 and split[1] == "value":
                self.attributes[split[0]].setText(1, repr(val))
