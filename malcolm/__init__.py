try:
    from malcolm import zmqtransport
except ImportError:
    print "No zmq available"

try:
    from malcolm import wstransport
except ImportError:
    print "No ws available"

try:
    from malcolm.gui.gui import gui, probe
except ImportError:
    print "No Qt available"

import malcolm.devices

