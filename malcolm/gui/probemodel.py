from PyQt4.Qt import QAbstractItemModel, QModelIndex, Qt, QVariant, QBrush, \
    QColor

from malcolm.core.attribute import Attribute
from malcolm.core.statemachine import StateMachine
from malcolm.core.subscription import ServerSubscription
from malcolm.gui.probeitem import ProbeItem

# https://www.daniweb.com/programming/software-development/threads/312211/pyqt4-treemodel-example


class ProbeModel(QAbstractItemModel):

    def __init__(self, device):
        super(ProbeModel, self).__init__()
        # map ob.name -> ProbeItem instance
        self.device_items = {}
        self.root_items = list(self.populate_items(device))
        self.device = device
        self.sub = ServerSubscription(device, "", self.on_change)
        self.sub.loop_run()

    def populate_items(self, ob, parent_item=None, parent_name=[],
                       parent_row=0):
        if hasattr(ob, "to_dict"):
            ob = ob.to_dict()
        # If we have children
        if hasattr(ob, "keys"):
            # items we have created
            for row, (cname, cval) in enumerate(ob.items()):
                # create value index
                item = ProbeItem(cname, cval, parent_item, parent_row)
                item.index = self.createIndex(row, 1, item)
                # add self into map
                name = parent_name + [cname]
                self.device_items[".".join(name)] = item
                # add any children
                item.children = list(
                    self.populate_items(cval, item, name, row))
                yield item
                self.update_parents(item)

    def on_change(self, typ, value, changes):
        for c, val in changes.items():
            item = self.device_items[c]
            item.data = val
            self.dataChanged.emit(item.index, item.index)
            self.update_parents(item)

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
                return QVariant(item.name)
        else:
            # value
            if role == Qt.DisplayRole:
                return self.format_data(item.data)
            elif role == Qt.BackgroundRole:
                return QBrush(QColor(64, 64, 64))
            elif role == Qt.ForegroundRole:
                return QBrush(QColor(96, 255, 96))

    def format_data(self, ob):
        if isinstance(ob, Attribute):
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
        if orientation == Qt.Horizontal:
            label = ["name", "value"][section]
            return QVariant(label)
