from collections import OrderedDict

from .process import Process
from .method import wrap_method
from .attribute import Attribute
from .deviceClient import DeviceClient


class DirectoryService(Process):

    def __init__(self, server_strings, name="DirectoryService", timeout=None):
        super(DirectoryService, self).__init__(server_strings, name,
                                               timeout=timeout)
        # Connection strings dict
        self._connection_strings = {}
        # registered devices deviceClient instances
        self._registered_devices = OrderedDict()
        # Add attributes for instances of each device type
        for typ in self.device_types:
            a = Attribute([str], "All registered {} instances".format(typ), [])
            self.add_attribute(typ + "_instances", a)

    @wrap_method(
        device=Attribute(str, "Device name")
    )
    def connection_string(self, device):
        """Return the server strings for a particular device"""
        return self._connection_strings[device]

    @wrap_method(
        device=Attribute(str, "Device name"),
        server_strings=Attribute([str], "Server strings for connection"),
    )
    def register_device(self, device, server_strings):
        # Store connection strings
        self._connection_strings[device] = server_strings
        # Store a deviceClient
        dc = DeviceClient(device, self.get_client_sock(server_strings),
                          monitor=False, timeout=1)
        dc.loop_run()
        self._registered_devices[device] = dc
        # When its connection status changes, update our device list
        dc.add_listener(self.update_devices, "attributes.device_client_connected")

    def update_devices(self, changes=None):
        instances = OrderedDict()
        for typ in self.device_types:
            instances[typ] = []
        # Store device name in each of its subclass lists
        for device in self._registered_devices.values():
            if device.connected:
                for subclass in device.tags:
                    instances[subclass].append(device.name)
            else:
                # no longer connected, pop it
                self._registered_devices.pop(device.name)
        # Push these to attributes
        for typ, devices in instances.items():
            self.attributes[typ + "_instances"].update(devices)
