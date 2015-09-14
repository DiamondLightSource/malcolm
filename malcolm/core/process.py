import multiprocessing
import sys
import weakref
import functools
import inspect

from .loop import EventLoop, TimerLoop, LState
from .serialize import SType
from .method import Method, wrap_method
from .base import weak_method
from .device import Device, not_process_creatable
from .deviceClient import DeviceClient
from malcolm.core.socketInterface import ClientSocket, ServerSocket
from .subscription import ServerSubscription
from .attribute import Attribute


@not_process_creatable
class Process(Device, multiprocessing.Process):

    def __init__(self, server_strings, name, ds_name="DirectoryService",
                 ds_string=None, timeout=None):
        """name is process name
        server_strings is list of "zmq://tcp://172.23.122.23:5600"
        """
        super(Process, self).__init__(name, timeout)
        # Store ds details
        self.ds = None
        self.ds_name = ds_name
        self.ds_string = ds_string
        # Local devices
        self._device_servers = {}
        # Weak references to DeviceClients for remote devices
        self.DeviceClient = DeviceClient
        self._device_clients = weakref.WeakValueDictionary()
        # Server socks
        self._server_socks = {}
        # Weak references to Client socks
        self._client_socks = weakref.WeakValueDictionary()
        # List of spawned cothreads
        self.spawned = []
        # send function -> ServerSubscription
        self.subscriptions = {}
        # Make a router loop
        router = EventLoop(name + ".router")
        router.add_event_handler(SType.Call, self.do_call)
        router.add_event_handler(SType.Get, self.do_get)
        router.add_event_handler(SType.Subscribe, self.do_subscribe)
        router.add_event_handler(SType.Unsubscribe, self.do_unsubscribe)
        router.error_handler = weak_method(self.do_error)
        self.router = router
        self.add_loop(router)
        # populate server strings
        self.server_strings = server_strings
        # Local devices
        self.local_devices = []

    def add_all_attributes(self):
        super(Process, self).add_all_attributes()
        # Add attributes
        self.add_attributes(
            server_strings=Attribute(
                [str], "List of server strings for server socks"),
            device_types=Attribute([str], "Available device types"),
            local_devices=Attribute([str], "Devices we are hosting"),
        )
        # populate device types
        self.device_types = []
        device_types = Device.subclasses()
        for d in device_types:
            # Add it to the device_types attribute
            self.device_types.append(d.__name__)
            if d not in Device.not_process_creatable and not inspect.isabstract(d):
                # Make a method to create an instance of it
                self.make_create_device(d)

    def make_create_device(self, cls):
        @functools.wraps(cls)
        def f(process, name, **kwargs):
            return process.create_device(cls, name, **kwargs)
        # Set the name and create a Method wrapper for it
        f.__name__ = "create_{}".format(cls.__name__)
        class_attributes = getattr(cls, "class_attributes", {})
        method = Method(f, args_from=cls.__init__)
        self.add_method(method, name=Attribute(str, "Device name"),
                        timeout=Attribute(str, "Timeout for any process"),
                        **class_attributes)
        setattr(self, f.__name__, method)

    def create_device(self, cls, name, **kwargs):
        device = cls(name, **kwargs)
        device.create_device = weak_method(self.create_device)
        device.get_device = weak_method(self.get_device)
        self._device_servers[name] = device
        self.add_loop(device)
        self.update_devices()
        return device

    def register_devices(self):
        for device in self.local_devices:
            if device not in self.ds.Device_instances:
                self.ds.register_device(device, self.server_strings)

    def update_devices(self):
        self.local_devices = sorted(self._device_servers)

    def get_device(self, device, server_strings=None):
        """Create a weak reference to a new DeviceClient object (or existing)
        """
        assert self.loop_state() == LState.Running, \
            "Can't get device when process has not been started running"
        if device in self._device_clients:
            return self._device_clients[device]
        elif device in self._device_servers:
            return self._device_servers[device]
        # Calculate server strings if not given
        if server_strings is None:
            assert self.ds is not None, "Can't lookup server string for {} "\
                "as no DirectoryService present".format(device)
            server_strings = self.ds.connection_string(device=device)
        dc = self.DeviceClient(device, self.get_client_sock(server_strings))
        # Don't add loop, we want it to go when no-one needs it
        dc.loop_run()
        self._device_clients[device] = dc
        return dc

    def get_client_sock(self, server_strings):
        # If we already have a client sock, return that
        # TODO: handle localhost conversion here?
        for string in server_strings:
            if string in self._client_socks:
                return self._client_socks[string]
        cs = ClientSocket.make_socket(string)
        assert cs, "Can't make socket for {}".format(string)
        self._client_socks[string] = cs
        cs.loop_run()
        return cs

    def run(self, block=True):
        """Sets up everything and starts the event loops."""
        # If we are in a multiprocessing loop then check that cothread has not
        # been inherited from the forked mainprocess. If it has then we can't
        # use cothread as we will share the same scheduler!
        if type(multiprocessing.current_process()) == type(self):
            # We are in a multiprocessing child process
            assert "cothread" not in sys.modules, \
                "Cothread has already been imported, this will not work!"
        self.loop_run()
        server_strings = []
        for string in self.server_strings:
            ss = ServerSocket.make_socket(string, self.router.inq)
            assert ss is not None, "Can't make socket for {}".format(string)
            self._server_socks[string] = ss
            self.add_loop(ss)
            server_strings.append(ss.name)
        self.server_strings = server_strings
        # Create a client to directory service
        if self.ds_string is not None:
            self.ds = self.get_device(self.ds_name, [self.ds_string])
            # Make a timer to keep checking ds has our devices
            self.add_loop(TimerLoop(self.name + ".dsupdate",
                                    self.register_devices, 10))
        self.quitsig = self.cothread.Pulse()
        if block:
            self.quitsig.Wait()

    @wrap_method()
    def exit(self):
        """Stops the event loops and waits until they're done."""
        # Can't do super, as we've decorated it
        Device.exit.function(self)
        for ct in self.spawned:
            ct.Wait()
        self.quitsig.Signal()

    def _get_device(self, endpoint):
        if "." in endpoint:
            devicename, ename = endpoint.split(".", 1)
        else:
            devicename, ename = endpoint, None
        if devicename in self._device_servers:
            device = self._device_servers[devicename]
        elif devicename == self.name:
            device = self
        else:
            raise AssertionError("Can't find device {}".format(devicename))
        return device, ename

    def do_func(self, send, f, args):
        try:
            ret = f(**args)
        except Exception as e:
            self.log_exception("Error running {}({})".format(f, args))
            send(SType.Error, e)
        else:
            send(SType.Return, ret)

    def do_call(self, send, endpoint, method, args={}):
        device, ename = self._get_device(endpoint)
        assert ename is None, \
            "Must Call with endpoint=<device> and method=<method>. " \
            "Got endpoint={} and method={}".format(endpoint, method)
        endpoint = device.get_endpoint("methods." + method)
        assert callable(endpoint), "Expected function, got {}".format(endpoint)
        if ename == "exit":
            self._device_servers.pop(device.name)
            self.update_devices()
        ct = self.cothread.Spawn(self.do_func, send, endpoint, args)
        self.spawned.append(ct)

    def do_get(self, send, endpoint):
        device, ename = self._get_device(endpoint)
        endpoint = device.get_endpoint(ename)
        send(SType.Return, endpoint)

    def do_subscribe(self, send, endpoint):
        sub = ServerSubscription(*self._get_device(endpoint), send=send)
        self.subscriptions[send] = sub
        self.add_loop(sub)
        return sub

    def do_unsubscribe(self, send):
        if send in self.subscriptions:
            self.subscriptions.pop(send).loop_stop()
        else:
            self.log_error("Unknown send func {}".format(getattr(send, "endpoint", send.__name__)))

    def do_error(self, error, send, *args, **kwargs):
        EventLoop.error_handler(self.router, error, send, *args, **kwargs)
        send(SType.Error, error)
