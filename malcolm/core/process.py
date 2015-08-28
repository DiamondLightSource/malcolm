import multiprocessing
import sys
import weakref
import functools

from .loop import EventLoop
from .serialize import SType
from .method import Method, wrap_method
from .device import Device
from .deviceClient import DeviceClient
from .socket import ClientSocket, ServerSocket


class Subscription(EventLoop):

    def __init__(self, device, ename, send, timeout=None):
        name = "subq.{}.{}".format(device.name, ename)
        super(Subscription, self).__init__(name, timeout)
        self.send = send
        self.add_event_handler(None, send)
        self.device = device
        device.add_listener(self.post, ename)

    def loop_stop(self):
        self.send(SType.Return)
        self.device.remove_listener(self.post)
        super(Subscription, self).loop_stop()


class Process(multiprocessing.Process, Device):

    def __init__(self, name, server_strings, remote_processes, timeout=None):
        """name is process name
        remote processes is dict processname -> connection string
        """
        super(Process, self).__init__(name, timeout)
        # Local devices
        self._devices = {}
        # Weak references to DeviceClients for remote devices
        self._device_clients = weakref.WeakValueDictionary()
        # DeviceClients connecting to remote processes
        self._process_clients = {}
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
        self.add_loop(router)
        # Add attributes
        self.add_attributes(
            server_strings=([str], "List of server strings for server socks"),
            device_types=([str], "Available device types"),
            local_devices=([str], "Devices we are hosting"),
            remote_processes=([str], "Remote processes we are watching"),
            remote_devices=([str], "Remote devices we can connect to"),
            device=(str, "Device (or Process) name"),
        )
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

                # Make a method for it
                @functools.wraps(d)
                def f(name, **kwargs):
                    device = d(name, **kwargs)
                    self._devices[name] = device

                # Set the name and wrap it
                f.__name__ = "create_{}".format(d.__name__)
                class_attributes = getattr(d, "class_attributes", {})
                self.add_method(Method(f), **class_attributes)
        # Local devices
        self.local_devices = []
        # populate remote processes and devices
        self.remote_devices = []
        self.remote_processes = []
        for process, server_strings in sorted(remote_processes.items()):
            self.add_remote_process(process, server_strings)

    @wrap_method()
    def connection_string(self, device):
        """Return the server strings for a particular device"""
        for process in self.remote_processes:
            process = self.get_device(process)
            if device == process or device in process.local_devices:
                return process.server_strings

    def update_remote_devices(self, changes=None):
        devices = []
        for process in self.remote_processes:
            process = self.get_device(process)
            devices += process.local_devices
        self.remote_devices = devices

    def get_device(self, device):
        """Create a weak reference to a new DeviceClient object (or existing)"""
        if device in self._device_clients:
            return self._device_clients[device]
        elif device in self._process_clients:
            return self._process_clients[device]
        elif device in self._devices:
            return self._devices[device]
        else:
            # Don't add loop, we want it to go when no-one needs it
            server_strings = self.connection_string(device)
            dc = DeviceClient(device, self.get_client_sock(server_strings))
            dc.loop_run()
            self._device_clients[device] = dc
            return dc

    def get_client_sock(self, server_strings):
        for string in server_strings:
            if string in self._client_socks:
                return self._client_socks[string]
        cs = ClientSocket.make_socket(string)
        self._client_socks[string] = cs
        return cs

    @wrap_method()
    def add_remote_process(self, device, server_strings):
        """Tell this process about a remove process to start watching"""
        if device not in self._process_clients:
            dc = DeviceClient(device, self.get_client_sock(server_strings))
            self._process_clients[device] = dc
            dc.add_listener(self.update_remote_devices,
                            "attributes.local_devices")
            self.add_loop(dc)

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
        if devicename in self._devices:
            device = self._devices[devicename]
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
            self._devices.pop(device.name)
        ct = self.cothread.Spawn(self.do_func, send, endpoint, args)
        self.process.spawned.append(ct)

    def do_get(self, send, endpoint):
        endpoint = self._get_endpoint(*self._get_device(endpoint))
        send(SType.Return, endpoint)

    def do_subscribe(self, send, endpoint):
        device, ename = self._get_device(endpoint)
        subq = Subscription(device, ename, send)
        self.subscriptions[send] = subq
        self.process.add_loop(subq)

    def do_unsubscribe(self, send):
        subq = self.subscriptions.pop(send)
        subq.loop_stop()
        subq.loop_wait()
        self.process.remove_loop(subq)

    def do_error(self, error, send, *args, **kwargs):
        EventLoop(self.router, error, send, *args, **kwargs)
        send(SType.Error, error)
