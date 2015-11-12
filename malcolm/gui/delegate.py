from enum import Enum
from PyQt4.Qt import QStyledItemDelegate, QStyle, QStyleOptionButton, \
    QApplication, QEvent, QPushButton
from malcolm.core.method import Method


class MState(Enum):
    Normal, Hovered, Pressed = range(3)



class Delegate(QStyledItemDelegate):

    def paint(self, painter, option, index):
        # If we are looking at a method then draw a button
        # http://www.qtcentre.org/threads/26916-inserting-custom-Widget-to-listview?p=128623#post128623
        if not hasattr(self, "blue_button"):
            self.blue_button = QPushButton()
            self.blue_button.setStyleSheet("color: rgb(0, 0, 196)")
        if index.isValid() and \
                isinstance(index.internalPointer().data, Method):
            item = index.internalPointer()
            opt = QStyleOptionButton()
            style = QApplication.style()
            # If method is running, draw sunken
            if item.argvalue:
                opt.state |= QStyle.State_Enabled
                opt.state |= QStyle.State_Sunken
            # if method is allowed, draw blue
            elif self.method_allowed(item):
                opt.state |= QStyle.State_Enabled
                style = self.blue_button.style()
            # if we are hovering, draw highlight
            if option.state & QStyle.State_MouseOver:
                opt.state |= QStyle.State_MouseOver
            opt.rect = option.rect
            opt.text = index.internalPointer().name
            style.drawControl(QStyle.CE_PushButton, opt, painter, self.blue_button)
        else:
            if option.state & QStyle.State_Selected:
                # Don't show delegates as highlighted
                option.state = option.state ^ QStyle.State_Selected
            super(Delegate, self).paint(painter, option, index)

    def method_allowed(self, item):
        sm = getattr(item.data.device, "stateMachine", None)
        valid_states = item.data.valid_states
        return sm is None or valid_states is None or sm.state in valid_states

    def editorEvent(self, event, model, option, index):
        if index.isValid() and isinstance(index.internalPointer().data, Method):
            # TODO: Drag seems to do the wrong thing here...
            if event.type() in [QEvent.MouseButtonPress,
                                QEvent.MouseButtonDblClick]:
                if self.method_allowed(index.internalPointer()):
                    model.setData(index, 0)
                return True
        return super(QStyledItemDelegate, self).editorEvent(event, model,
                                                            option, index)
