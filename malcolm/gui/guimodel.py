from PyQt4.Qt import QAbstractItemModel, QModelIndex, Qt, QVariant, QBrush, \
    QColor

from malcolm.core.attribute import Attribute
from malcolm.core.statemachine import StateMachine
from malcolm.core.subscription import ServerSubscription
from malcolm.gui.guiitem import GuiItem
from malcolm.core.method import Method
from malcolm.core.alarm import AlarmSeverity, Alarm
from collections import OrderedDict
from malcolm.core.vtype import VBool

# https://www.daniweb.com/programming/software-development/threads/312211/pyqt4-treemodel-example


class GuiModel(QAbstractItemModel):

    def __init__(self, device, probe=False):
        QAbstractItemModel.__init__(self)
        # map ob.name -> GuiItem instance
        self.probe = probe
        self.device_items = {}
        if probe:
            self.root_items = self.populate_items(device)
        else:
            self.root_items = []
            if hasattr(device, "stateMachine"):
                self.root_items.append(self.populate_stateMachine(device))
            self.method_items = self.populate_methods(device)
            self.root_items += self.method_items
            self.root_items.append(self.populate_attributes(device))
        self.device = device
        self.sub = ServerSubscription(device, "", self.on_change)
        self.sub.loop_run()

    def populate_methods(self, device):
        off = len(self.root_items)
        ret = []
        for mname, mval in device.methods.items():
            if not self.probe and mname in ("exit", "validate"):
                continue
            row = len(ret)
            # make an item for each method
            parent_item = self.make_item(row + off, mname, mval)
            # now make a child item for each argument
            for aname, aval in mval.arguments.items():
                if aname != "block":
                    row = len(parent_item.children)
                    name_list = ["methods", mname, "arguments", aname]
                    item = self.make_item(
                        row, aname, aval, ".".join(name_list), parent_item)
                    parent_item.children.append(item)
                    self.populate_items(aval, name_list, item)
            ret.append(parent_item)
        return ret

    def populate_stateMachine(self, device):
        row = len(self.root_items)
        stateMachine_item = self.make_item(row, "stateMachine",
                                           device.stateMachine)
        self.populate_items(device.stateMachine, ["stateMachine"],
                            stateMachine_item)
        return stateMachine_item

    def populate_attributes(self, device):
        row = len(self.root_items)
        attributes_item = self.make_item(row, "attributes")
        self.populate_items(device.attributes, ["attributes"], attributes_item)
        return attributes_item

    def make_item(self, row, name, val="", fullname=None, parent_item=None):
        # create value index
        item = GuiItem(name, val, parent_item, row)
        item.index = self.createIndex(row, 1, item)
        # add self into map
        if fullname:
            self.device_items[fullname] = item
        return item

    def populate_items(self, ob, parent_name=[], parent_item=None):
        if hasattr(ob, "to_dict"):
            ob = ob.to_dict()
        # If we have children
        ret = []
        if hasattr(ob, "keys"):
            # items we have created
            for row, (cname, cval) in enumerate(ob.items()):
                name_list = parent_name + [cname]
                item = self.make_item(row, cname, cval, ".".join(name_list),
                                      parent_item)
                if parent_item is not None:
                    parent_item.children.append(item)
                # add any children
                self.populate_items(cval, name_list, item)
                self.update_parents(item)
                ret.append(item)
        return ret

    def on_change(self, typ, value, changes):
        for c, val in changes.items():
            if c in self.device_items:
                item = self.device_items[c]
                item.data = val
                self.dataChanged.emit(item.index, item.index)
                self.update_parents(item)
            if c == "stateMachine.state":
                # redraw method buttons
                for item in self.method_items:
                    self.dataChanged.emit(item.index, item.index)

    def update_parents(self, item):
        # keep traversing up until we find something we should regenerate
        if item.parent_item and item.parent_item.name == "attributes":
            self.dataChanged.emit(item.index, item.index)
        elif item.name == "stateMachine":
            self.dataChanged.emit(item.index, item.index)
        elif item.parent_item:
            self.update_parents(item.parent_item)

    def index(self, row, column, parent=QModelIndex()):
        # Check row and column in range
        if row < 0 or row >= self.rowCount(parent) or \
                column < 0 or column >= self.columnCount(parent):
            return QModelIndex()
        if not parent.isValid():
            # If parent isn't valid, we're being asked for our root item
            child_item = self.root_items[row]
        else:
            # Otherwise fetch it from the index
            parent_item = parent.internalPointer()
            child_item = parent_item.children[row]
        # Now make an index
        index = self.createIndex(row, column, child_item)
        return index

    def parent(self, index):
        # Check valid index
        if not index.isValid():
            return QModelIndex()
        child_item = index.internalPointer()
        # Check child's parent exists
        if child_item.parent_item is None:
            return QModelIndex()
        # Return an index for us
        index = self.createIndex(child_item.parent_row, 0,
                                 child_item.parent_item)
        return index

    def rowCount(self, parent):
        if parent.column() > 0:
            return 0
        if not parent.isValid():
            return len(self.root_items)
        else:
            parent_item = parent.internalPointer()
            rows = len(parent_item.children)
            return rows

    def columnCount(self, parent):
        return 2

    def data(self, index, role):
        if not index.isValid():
            return None
        # Get item
        item = index.internalPointer()
        if index.column() == 0:
            # name
            if role == Qt.DisplayRole:
                if item.dirty:
                    return QVariant(item.name + " *")
                else:
                    return QVariant(item.name)
        else:
            # value
            if role == Qt.DisplayRole:
                return self.format_data(item)
            elif role == Qt.EditRole:
                return self.format_data(item)
            elif role == Qt.BackgroundRole:
                if self.isArgument(item) or self.isWriteable(item):
                    # alternating background as specified by stylesheet
                    return None
                else:
                    # and a bit darker
                    return QBrush(QColor(0, 0, 0, 176))
            elif role == Qt.ToolTipRole:
                txts = ["value: {}".format(self.format_data(item))]
                for attr in ("descriptor", "type", "alarm", "timeStamp"):
                    if hasattr(item.data, attr):
                        txts.append("{}: {}".format(attr, getattr(item.data, attr)))
                return "\n\n".join(txts)
            elif role == Qt.ForegroundRole:
                alarm = getattr(item.data, "alarm", None)
                severity = getattr(alarm, "severity", AlarmSeverity.noAlarm)
                if self.isArgument(item) or self.isWriteable(item):
                    return QBrush(QColor(0, 0, 196))
                elif severity == AlarmSeverity.noAlarm:
                    return QBrush(QColor(96, 255, 96))
                elif severity == AlarmSeverity.minorAlarm:
                    return QBrush(QColor(255, 241, 0))
                elif severity == AlarmSeverity.majorAlarm:
                    return QBrush(QColor(255, 0, 0))
                else:
                    return QBrush(QColor(255, 240, 255))

    def isArgument(self, item):
        if self.probe:
            # method.argument.value
            isargument = item.parent_item and item.parent_item.parent_item and isinstance(
                item.parent_item.parent_item.data, Method)
        else:
            # method.argument
            isargument = item.parent_item and isinstance(
                item.parent_item.data, Method)
        return isargument

    def isWriteable(self, item):
        if self.probe:
            # attribute.value
            iswriteable = item.parent_item and isinstance(
                item.parent_item.data, Attribute) and item.parent_item.data.put_method_name()
        else:
            # attribute
            iswriteable = isinstance(item.data, Attribute) and item.data.put_method_name()
        return iswriteable

    def setData(self, index, value, role=Qt.EditRole):
        if role == Qt.EditRole:
            if index.isValid():
                item = index.internalPointer()
                if self.isArgument(item):
                    newvalue = str(value.toString())
                    if isinstance(item.data.typ, VBool):
                        newvalue = newvalue.lower() != "false"
                    if newvalue != str(item.argvalue):
                        item.argvalue = newvalue
                        item.dirty = True
                        label = index.sibling(index.row(), 0)
                        self.dataChanged.emit(label, index)
                        return True
                elif self.isWriteable(item):
                    newvalue = str(value.toString())
                    if isinstance(item.data.typ, VBool):
                        newvalue = newvalue.lower() != "false"
                    import cothread
                    cothread.Spawn(self.do_put, index, newvalue)
                    return True
                elif isinstance(item.data, Method):
                    args = {}
                    for child_item in item.children:
                        child_item.dirty = False
                        args[child_item.name] = child_item.argvalue
                    childleft = self.index(0, 0, index)
                    childright = self.index(1, len(item.children) - 1, index)
                    self.dataChanged.emit(childleft, childright)
                    item.argvalue = "Running"
                    self.dataChanged.emit(index, index)
                    import cothread
                    cothread.Spawn(self.run_method, index, **args)
                    return True
        return False

    def run_method(self, index, **args):
        item = index.internalPointer()
        method = item.data
        try:
            # TODO: something with ret here
            ret = method(**args)
        except:
            method.log_exception("Exception raised from gui")
        finally:
            item.argvalue = None
            self.dataChanged.emit(index, index)

    def do_put(self, index, value):
        item = index.internalPointer()
        if self.probe:
            item = item.parent_item
        attr = item.data
        try:
            # TODO: something with ret here
            ret = attr.update(value)
        except:
            attr.log_exception("Exception raised from gui")

    def flags(self, index):
        flags = QAbstractItemModel.flags(self, index)
        if index.isValid() and index.column() == 1:
            item = index.internalPointer()
            if self.isArgument(item) or self.isWriteable(item) or isinstance(item.data, Method):
                flags |= Qt.ItemIsEditable
        return flags

    def format_data(self, item):
        ob = item.data
        if self.isArgument(item):
            return str(item.argvalue)
        elif isinstance(ob, Attribute):
            # Report value
            return str(ob.value)
        elif isinstance(ob, StateMachine):
            # Report state, message
            return "{}: {}".format(ob.state.name, ob.message)
        elif isinstance(ob, list):
            return "\n".join(str(o) for o in ob)
        else:
            return str(ob)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            label = ["name", "value"][section]
            return label
        return QVariant()
