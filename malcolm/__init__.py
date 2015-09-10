try:
    from malcolm import zmqComms
except ImportError:
    print "No zmq available"
    pass
import malcolm.devices
