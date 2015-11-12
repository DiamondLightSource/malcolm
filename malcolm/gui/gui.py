from PyQt4.Qt import QTreeView, QSize, Qt, QVariant, QEvent

from malcolm.gui.guimodel import GuiModel
from malcolm.gui.delegate import Delegate


def gui(device):
    return Gui(device, "Gui")


def probe(device):
    return Gui(device, "Probe", probe=True)


style = """
background-color: rgb(200, 200, 200);
alternate-background-color: rgb(205, 205, 205);
"""


class Gui(QTreeView):
    need_iqt = True

    def __init__(self, device, title, probe=False):
        if Gui.need_iqt:
            import cothread
            cothread.iqt()
            cothread.input_hook._qapp.setQuitOnLastWindowClosed(False)
            Gui.need_iqt = False
        super(Gui, self).__init__()
        self.device = device
        self.probe = probe
        self.make_model()
        device.add_listener(self.make_model, "attributes.deviceClientConnected.value")
        # set delegate
        self.delegate = Delegate()
        self.setItemDelegateForColumn(1, self.delegate)
        self.setStyleSheet(style)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(self.AllEditTriggers)
        # show self
        title = "{}: {}".format(title, device.name)
        if title.endswith("Client"):
            title = title[:-len("Client")]
        self.setWindowTitle(title)
        self.setColumnWidth(0, 160)
        self.setColumnWidth(1, 200)
        self.resize(QSize(365, 800))
        self.show()

    def make_model(self, value=True, changes=None):
        if value:
            model = GuiModel(self.device, self.probe)
            self.setModel(model)
            # recurse down and expand what is useful
            for search in ["attributes", "configure", "rewind"]:
                matches = model.match(model.index(0, 0), Qt.DisplayRole,
                                      QVariant(search))
                for m in matches:
                    self.expand(m)
