try:
    from malcolm import zmqtransport
except ImportError:
    print "No zmq available"
    pass
#try:
from malcolm.gui.gui import gui, probe
#except:
#    print "No Qt available"
import malcolm.devices
import malcolm.personalities
