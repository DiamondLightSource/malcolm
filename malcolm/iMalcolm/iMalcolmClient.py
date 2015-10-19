#!/bin/env dls-python
if __name__ == "__main__":
    # Test
    from pkg_resources import require
    require("pyzmq==13.1.0")
    require("cothread==2.12")
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))

from malcolm.core.process import Process
from malcolm.core.deviceClient import DeviceClient
import argparse
import logging


class IDeviceClient(DeviceClient):

    def do_call(self, endpoint, *args, **kwargs):
        self.last = ""

        def print_call(sm, changes=None):
            msg = "{}: {}".format(sm.state.name, sm.message)
            if self.last != msg:
                print msg
                self.last = msg

        self.add_listener(print_call, "stateMachine")
        try:
            return super(IDeviceClient, self).do_call(endpoint, *args, **kwargs)
        except KeyboardInterrupt:
            super(IDeviceClient, self).do_call("abort")
        finally:
            self.remove_listener(print_call)


def make_client():
    parser = argparse.ArgumentParser(
        description="Interactive client shell for malcolm")
    parser.add_argument('server',
                        help="Server string for connection to malcolm "
                        "directory server like 172.23.243.13:5600")
    parser.add_argument('--log', default="INFO",
                        help="Lowest level of logs to see. One of: "
                        "ERROR, WARNING, INFO, DEBUG. "
                        "Default is INFO")
    args = parser.parse_args()
    # assuming loglevel is bound to the string value obtained from the
    # command line argument. Convert to upper case to allow the user to
    # specify --log=DEBUG or --log=debug
    numeric_level = getattr(logging, args.log.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError('Invalid log level: %s' % args.log)
    logging.basicConfig(level=numeric_level)
    ds_string = "zmq://tcp://{}".format(args.server)
    client = Process([], "iMalcolmClient", ds_string=ds_string)
    client.DeviceClient = IDeviceClient
    return client


def main():
    self = make_client()
    self.run(block=False)
    all_devices = self.ds.instancesDevice
    header = """Welcome to iMalcolmClient.
You are connected to: {}
These devices are available:
{}
Type self.get_device("<device_name>") to get a device client
Try:
det = self.get_device("det")
det.configure(exposure=0.1, nframes=10)
det.run()
""".format(self.ds_string, all_devices)
    import numpy
    try:
        import IPython
    except ImportError:
        import code
        code.interact(header, local=locals())
    else:
        IPython.embed(header=header)

if __name__ == "__main__":
    # Entry point
    main()
