class GuiItem(object):
    def __init__(self, name, data, parent_item, parent_row):
        # our name
        self.name = name
        # our value
        self.data = data
        # parent QModelIndex
        self.parent_item = parent_item
        # parent row number
        self.parent_row = parent_row
        # any GuiItem children
        self.children = []
        # our QModelView index
        self.index = None
        # whether we need a star after the name
        self.dirty = False
        # argument value
        if hasattr(data, "value"):
            self.argvalue = data.value
        else:
            self.argvalue = None
