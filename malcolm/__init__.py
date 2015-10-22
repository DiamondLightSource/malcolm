try:
    from malcolm import zmqtransport
except ImportError:
    print "No zmq available"
    pass
import malcolm.devices
import malcolm.personalities
