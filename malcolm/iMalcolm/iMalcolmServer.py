#!/bin/env dls-python
if __name__ == "__main__":
    # Test
    from pkg_resources import require
    require("pyzmq==13.1.0")
    require("cothread==2.12")
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from malcolm.core.directoryService import DirectoryService, \
    not_process_creatable
import argparse
import IPython
import logging


@not_process_creatable
class IMalcolmServer(DirectoryService):

    def __init__(self):
        args = self.parse_args()
        # assuming loglevel is bound to the string value obtained from the
        # command line argument. Convert to upper case to allow the user to
        # specify --log=DEBUG or --log=debug
        numeric_level = getattr(logging, arguments.log.upper(), None)
        if not isinstance(numeric_level, int):
            raise ValueError('Invalid log level: %s' % args.log)
        logging.basicConfig(level=numeric_level)
        server_string = "zmq://tcp://0.0.0.0:{}".format(args.port)
        super(IMalcolmServer, self).__init__([server_string])
        self.run(block=False)

    def parse_args(self):
        parser = argparse.ArgumentParser(
            description="Interactive server shell for malcolm")
        parser.add_argument('--port', default=5600, help="Port to run on")
        parser.add_argument('--log', default="INFO",
                            help="Lowest level of logs to see. One of: "
                            "ERROR, WARNING, INFO, DEBUG. "
                            "Default is INFO")
        return parser.parse_args()

    def interact(self):
        locals().update(self._device_servers)
        IPython.embed(header="""iMalcolmServer running on {}.
These are the local devices:
{}
""".format(self.server_strings, self.local_devices))

if __name__ == "__main__":
    # Test
    ims = IMalcolmServer()
    ims.create_DummyDet("det")
    ims.interact()
