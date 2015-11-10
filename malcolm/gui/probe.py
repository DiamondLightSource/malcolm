from PyQt4.Qt import QTreeView, QSize, Qt, QVariant

from malcolm.gui.probemodel import ProbeModel
from malcolm.gui.delegate import Delegate


def probe(device):
    # only run if we need to exec
    if Probe.need_iqt:
        import cothread
        cothread.iqt()
        cothread.input_hook._qapp.setQuitOnLastWindowClosed(False)
        Probe.need_iqt = False
    return Probe(device)

style = """
background-color: rgb(200, 200, 200);
alternate-background-color: rgb(205, 205, 205);
"""


class Probe(QTreeView):
    need_iqt = True

    def __init__(self, device):
        super(Probe, self).__init__()
        model = ProbeModel(device)
        self.setModel(model)
        # set delegate
        self.setItemDelegateForColumn(1, Delegate())
        self.setStyleSheet(style)
        self.setAlternatingRowColors(True)
        # show self
        title = "Probe: {}".format(device.name)
        if title.endswith("Client"):
            title = title[:-len("Client")]
        self.setWindowTitle(title)
        self.setColumnWidth(0, 160)
        self.setColumnWidth(1, 200)
        self.resize(QSize(365, 800))
        # recurse down and expand what is useful
        attributes = model.match(model.index(0, 0), Qt.DisplayRole,
                                 QVariant("attributes"))
        if attributes:
            self.expand(attributes[0])
        self.show()
