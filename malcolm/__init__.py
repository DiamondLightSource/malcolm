try:
    from malcolm import zmqtransport
except ImportError:
    print "No zmq available"
    pass
try:
    from malcolm import gui
except:
    print "No Qt available"
import malcolm.devices
import malcolm.personalities
