try:
    from malcolm import zmqtransport
except ImportError:
    print "No zmq available"
    pass
try:
    from malcolm.gui.gui import gui, probe
except ImportError:
    print "No Qt available"
import malcolm.devices
