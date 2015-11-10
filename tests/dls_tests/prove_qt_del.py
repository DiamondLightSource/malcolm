#!/usr/bin/env dls-python

from PyQt4 import QtGui


class Preview(QtGui.QWidget):
    def __init__(self, parent):
        QtGui.QWidget.__init__(self, parent)

    def __del__(self):
        print("Deleting Preview")


class PreviewWindow(QtGui.QMainWindow):
    def __init__(self):
        QtGui.QMainWindow.__init__(self)

        self.widget = Preview(self)
        self.setCentralWidget(self.widget)

    def __del__(self):
        print("Deleting PreviewWindow")

if __name__ == "__main__":
    app = QtGui.QApplication(["Dimension Preview"])
    window = PreviewWindow()
    window.show()
    app.exec_()
