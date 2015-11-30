from enum import Enum
from PyQt4.Qt import QStyledItemDelegate, QStyle, QStyleOptionButton, \
    QApplication, QEvent, QPushButton, QComboBox, QLineEdit, QVariant, Qt
from malcolm.core import VBool, VEnum, Attribute
from malcolm.core.method import Method


class MState(Enum):
    Normal, Hovered, Pressed = range(3)


class Delegate(QStyledItemDelegate):

    def createEditor(self, parent, option, index):
        if index.isValid() and index.column() == 1:
            item = index.internalPointer()
            if isinstance(item.data, Attribute):
                attr = item.data
                if isinstance(attr.typ, VEnum):
                    editor = SpecialComboBox(parent)
                    editor.delegate = self
                    editor.setEditable(True)
                    editor.addItems(attr.typ.labels)
                elif isinstance(attr.typ, VBool):
                    editor = SpecialComboBox(parent)
                    editor.delegate = self
                    editor.setEditable(True)
                    editor.addItems(["False", "True"])
                else:
                    editor = QLineEdit(parent)
                return editor

    def setEditorData(self, editor, index):
        if isinstance(editor, QComboBox):
            i = editor.findText(index.data(Qt.EditRole).toString())
            if i > -1:
                editor.setCurrentIndex(i)
            else:
                editor.setEditText(index.data(Qt.EditRole).toString())
            editor.lineEdit().selectAll()
        else:
            return QStyledItemDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        if isinstance(editor, QComboBox):
            model.setData(index, QVariant(editor.currentText()), Qt.EditRole)
        else:
            return QStyledItemDelegate.setModelData(self, editor, model, index)

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
            style.drawControl(QStyle.CE_PushButton, opt, painter,
                              self.blue_button)
        else:
            if option.state & QStyle.State_Selected:
                # Don't show delegates as highlighted
                option.state = option.state ^ QStyle.State_Selected
            QStyledItemDelegate.paint(self, painter, option, index)

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
        QStyledItemDelegate.editorEvent(self, event, model, option, index)


class SpecialComboBox(QComboBox):
    # Qt outputs an activated signal if you start typing then mouse click on the
    # down arrow. By delaying the activated event until after the mouse click
    # we avoid this problem
    def closeEvent(self, i):
        self.delegate.commitData.emit(self)
        self.delegate.closeEditor.emit(self, QStyledItemDelegate.SubmitModelCache)

    def mousePressEvent(self, event):
        QComboBox.mousePressEvent(self, event)
        self.activated.connect(self.closeEvent)