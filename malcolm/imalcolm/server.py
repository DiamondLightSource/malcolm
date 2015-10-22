from malcolm.core.directoryservice import DirectoryService, \
    not_process_creatable
import argparse
import logging


@not_process_creatable
class IMalcolmServer(DirectoryService):

    def __init__(self):
        args = self.parse_args()
        # assuming loglevel is bound to the string value obtained from the
        # command line argument. Convert to upper case to allow the user to
        # specify --log=DEBUG or --log=debug
        numeric_level = getattr(logging, args.log.upper(), None)
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
        header = """iMalcolmServer running on {}.
These are the local devices:
{}
""".format(self.serverStrings, self.localDevices)
        try:
            import IPython
        except ImportError:
            import code
            code.interact(header, local=locals())
        else:
            IPython.embed(header=header)
