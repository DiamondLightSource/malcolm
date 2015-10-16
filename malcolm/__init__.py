try:
    from malcolm import zmqTransport
except ImportError:
    print "No zmq available"
    pass
import malcolm.devices
import malcolm.personalities
