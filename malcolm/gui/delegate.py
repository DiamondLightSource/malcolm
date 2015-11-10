from PyQt4.Qt import QStyledItemDelegate, QPalette, QColor, Qt, QStyle


class Delegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if option.state & QStyle.State_Selected:
            # Don't show delegates as highlighted
            option.state = option.state ^ QStyle.State_Selected
        super(Delegate, self).paint(painter, option, index)
