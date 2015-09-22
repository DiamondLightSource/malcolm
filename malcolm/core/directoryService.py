from collections import OrderedDict

from .process import Process
from .method import wrap_method
from .attribute import Attribute
from .deviceClient import DeviceClient
from .device import not_process_creatable
from .vtype import VString, VStringArray


@not_process_creatable
class DirectoryService(Process):

    def __init__(self, server_strings, name="DirectoryService", timeout=None):
        super(DirectoryService, self).__init__(server_strings, name,
                                               timeout=timeout)
        # Connection strings dict
        self._connection_strings = {}
        # registered devices deviceClient instances
        self._registered_devices = OrderedDict()

    def add_all_attributes(self):
        super(DirectoryService, self).add_all_attributes()
        # Add attributes for instances of each device type
        for typ in self.deviceTypes:
            a = Attribute(
                VStringArray, "All registered {} instances".format(typ), [])
            self.add_attribute("instances" + typ, a)

    @wrap_method(
        device=Attribute(VString, "Device name")
    )
    def connectionString(self, device):
        """Return the server strings for a particular device"""
        if device in self._device_servers:
            return self.serverStrings
        elif device in self._connection_strings:
            return self._connection_strings[device]
        raise AssertionError("{} not in {} or {}"
                             .format(device, self._connection_strings.keys(), self._device_servers.keys()))

    @wrap_method(
        device=Attribute(VString, "Device name"),
        serverStrings=Attribute(
            VStringArray, "Server strings for connection"),
    )
    def register(self, device, serverStrings):
        # Store connection strings
        self._connection_strings[device] = serverStrings
        # Store a deviceClient
        dc = DeviceClient(device, self.get_client_sock(serverStrings),
                          monitor=False, timeout=1)
        self.add_loop(dc)
        self._registered_devices[device] = dc
        # When its connection status changes, update our device list
        dc.add_listener(
            self.update_devices, "attributes.device_client_connected")

    def update_devices(self, connected=None, changes=None):
        super(DirectoryService, self).update_devices()
        instances = OrderedDict()
        for typ in self.deviceTypes:
            instances[typ] = []
        # Store device name in each of its subclass lists
        for device in self._registered_devices.values():
            if device.connected:
                for subclass in device.tags:
                    instances[subclass].append(device.name)
            else:
                # no longer connected, pop it
                self.remove_loop(self._registered_devices.pop(device.name))
        # Do the same for local devices
        for device in self._device_servers.values() + [self]:
            for subclass in device.baseclasses():
                instances[subclass.__name__].append(device.name)
        # Push these to attributes
        for typ, devices in instances.items():
            self.attributes["instances" + typ].update(sorted(devices))
