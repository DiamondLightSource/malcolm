import multiprocessing
import sys
import weakref
import functools

from .loop import EventLoop
from .serialize import SType
from .method import Method, wrap_method
from .base import weak_method
from .device import Device
from .deviceClient import DeviceClient
from .socket import ClientSocket, ServerSocket
from malcolm.core.subscription import Subscription


class Process(multiprocessing.Process, Device):

    def __init__(self, server_strings, name, ds_name="DirectoryService",
                 ds_string=None, timeout=None):
        """name is process name
        server_strings is list of "zmq://tcp://172.23.122.23:5600"
        """
        super(Process, self).__init__(name, timeout)
        # Add attributes
        self.add_attributes(
            server_strings=([str], "List of server strings for server socks"),
            device_types=([str], "Available device types"),
            local_devices=([str], "Devices we are hosting"),
        )
        # Local devices
        self._device_servers = {}
        # Weak references to DeviceClients for remote devices
        self._device_clients = weakref.WeakValueDictionary()
        # Server socks
        self._server_socks = {}
        # Weak references to Client socks
        self._client_socks = weakref.WeakValueDictionary()
        # List of spawned cothreads
        self.spawned = []
        # send function -> Subscription
        self.subscriptions = {}
        # Make a router loop
        router = EventLoop(name + ".router")
        router.add_event_handler(SType.Call, self.do_call)
        router.add_event_handler(SType.Get, self.do_get)
        router.add_event_handler(SType.Subscribe, self.do_subscribe)
        router.add_event_handler(SType.Unsubscribe, self.do_unsubscribe)
        router.error_handler = self.do_error
        self.router = router
        self.add_loop(router)
        # populate server strings
        self.server_strings = server_strings
        for string in server_strings:
            ss = ServerSocket.make_socket(string, self.inq)
            self._server_socks[string] = ss
            self.add_loop(ss)
        # populate device types
        self.device_types = []
        device_types = Device.all_subclasses()
        for d in device_types:
            if d not in [Device, Process]:
                # Add it to the device_types attribute
                self.device_types.append(d.__name__)
                # Make a method to create an instance of it
                f = functools.partial(self.create_device, d)
                # Make it look like the original
                functools.update_wrapper(f, d)
                # Set the name and create a Method wrapper for it
                f.__name__ = "create_{}".format(d.__name__)
                class_attributes = getattr(d, "class_attributes", {})
                self.add_method(Method(f), **class_attributes)
        # Local devices
        self.local_devices = []
        # Create a client to directory service
        if ds_string is not None:
            self.ds = self.get_device(ds_name, [ds_string])
        else:
            self.ds = None

    def create_device(self, cls, name, *args, **kwargs):
        device = cls(name, **kwargs)
        device.create_device = weak_method(self.create_device)
        device.get_device = weak_method(self.get_device)
        self._device_servers[name] = device
        return device

    def get_device(self, device, server_strings=None):
        """Create a weak reference to a new DeviceClient object (or existing)
        """
        if device in self._device_clients:
            return self._device_clients[device]
        elif device in self._device_servers:
            return self._device_servers[device]
        # Calculate server strings if not given
        if server_strings is None:
            assert self.ds is not None, "Can't lookup server string for {} "\
                "as no DirectoryService present".format(device)
            server_strings = self.ds.connection_string(device)
        dc = DeviceClient(device, self.get_client_sock(server_strings))
        # Don't add loop, we want it to go when no-one needs it
        dc.loop_run()
        self._device_clients[device] = dc
        return dc

    def get_client_sock(self, server_strings):
        # If we already have a client sock, return that
        for string in server_strings:
            if string in self._client_socks:
                return self._client_socks[string]
        cs = ClientSocket.make_socket(string)
        self._client_socks[string] = cs
        return cs

    def run(self, block=True):
        """Sets up everything and starts the event loops."""
        # If we are in a multiprocessing loop then check that cothread has not
        # been inherited from the forked mainprocess. If it has then we can't
        # use cothread as we will share the same scheduler!
        if type(multiprocessing.current_process()) == type(self):
            # We are in a multiprocessing child process
            cothread_imports = [x for x in sys.modules
                                if x.startswith("cothread")]
            assert len(cothread_imports) == 0, \
                "Cothread has already been imported, this will not work!"
        self.add_methods()
        self.loop_run()
        self.quitsig = self.cothread.Pulse()
        if block:
            self.quitsig.Wait()

    @wrap_method()
    def exit(self):
        """Stops the event loops and waits until they're done."""
        self.loop_stop()
        self.loop_wait()
        for ct in self.spawned:
            ct.Wait()
        self.quitsig.Signal()

    def _get_device(self, endpoint):
        if "." in endpoint:
            devicename, ename = endpoint.split(".", 1)[0]
        else:
            devicename, ename = endpoint, None
        if devicename in self._device_servers:
            device = self._device_servers[devicename]
        elif devicename == self.name:
            device = self
        else:
            raise AssertionError("Can't find device {}".format(devicename))
        return device, ename

    def _get_endpoint(self, device, ename):
        endpoint = device
        if ename is not None:
            for e in ename.split("."):
                endpoint = endpoint.to_dict()[e]
        return endpoint

    def do_func(self, send, f, args):
        try:
            ret = f(**args)
        except Exception as e:
            send(SType.Error, e)
        else:
            send(SType.Return, ret)

    def do_call(self, send, endpoint, args={}):
        device, ename = self._get_device(endpoint)
        endpoint = self._get_endpoint(device, ename)
        assert callable(endpoint), "Expected function, got {}".format(endpoint)
        if ename == "exit":
            self._device_servers.pop(device.name)
        ct = self.cothread.Spawn(self.do_func, send, endpoint, args)
        self.process.spawned.append(ct)

    def do_get(self, send, endpoint):
        endpoint = self._get_endpoint(*self._get_device(endpoint))
        send(SType.Return, endpoint)

    def do_subscribe(self, send, endpoint):
        sub = Subscription(*self._get_device(endpoint), send)
        self.subscriptions[send] = sub
        self.add_loop(sub)

    def do_unsubscribe(self, send):
        self.subscriptions.pop(send).loop_stop()

    def do_error(self, error, send, *args, **kwargs):
        EventLoop.error_handler(self.router, error, send, *args, **kwargs)
        send(SType.Error, error)
