class ProbeItem(object):
    def __init__(self, name, data, parent_item, parent_row):
        # our name
        self.name = name
        # our value
        self.data = data
        # parent QModelIndex
        self.parent_item = parent_item
        # parent row number
        self.parent_row = parent_row
        # any ProbeItem children
        self.children = []
        # our QModelView index
        self.index = None
