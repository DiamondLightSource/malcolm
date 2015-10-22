import multiprocessing
import sys
import weakref
import functools
import inspect

from .loop import EventLoop, LState
from .method import Method, wrap_method
from .device import Device, not_process_creatable
from malcolm.core.deviceclient import DeviceClient
from .transport import ClientSocket, ServerSocket, SType
from .subscription import ServerSubscription
from .attribute import Attribute
from .base import weak_method
from .vtype import VStringArray, VString, VDouble, VObject


@not_process_creatable
class Process(Device, multiprocessing.Process):

    def __init__(self, serverStrings, name, ds_name="DirectoryService",
                 ds_string=None, timeout=None):
        """name is process name
        serverStrings is list of "zmq://tcp://172.23.122.23:5600"
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
        self.serverStrings = serverStrings
        # Local devices
        self.localDevices = []

    def add_all_attributes(self):
        super(Process, self).add_all_attributes()
        # Add attributes
        self.add_attributes(
            serverStrings=Attribute(
                VStringArray, "List of server strings for server socks"),
            deviceTypes=Attribute(VStringArray, "Available device types"),
            localDevices=Attribute(VStringArray, "Devices we are hosting"),
        )
        # populate device types
        self.deviceTypes = []
        deviceTypes = Device.subclasses()
        for d in deviceTypes:
            # Add it to the deviceTypes attribute
            self.deviceTypes.append(d.__name__)
            if d not in Device.not_process_creatable and \
                    not inspect.isabstract(d):
                # Make a method to create an instance of it
                self.make_create_device(d)

    def make_create_device(self, cls):
        @functools.wraps(cls)
        def f(self, **kwargs):
            return self.create_device(cls, **kwargs)
        # Set the name and create a Method wrapper for it
        f.__name__ = "create{}".format(cls.__name__)
        class_attributes = getattr(cls, "class_attributes", {})
        method = Method(f, arguments_from=cls.__init__)
        self.add_method(method, name=Attribute(VString, "Device name"),
                        timeout=Attribute(VDouble, "Timeout for any process"),
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

    def update_devices(self):
        # update our localDevices attribute to reflect our Device instances
        self.localDevices = sorted(self._device_servers)
        if self.ds:
            self.on_device_list_changed()

    def on_device_list_changed(self):
        # Make sure our localDevices are pushed to ds
        for dname in self.localDevices + [self.name]:
            if dname not in self.ds.instancesDevice:
                self.ds.register(dname, self.serverStrings)
        # Make sure our instance attributes are correct
        for device in self._device_servers.values() + [self]:
            for ia in device._instance_attributes:
                labels = getattr(
                    self.ds, "instances{}".format(ia.dcls.__name__), [])
                if tuple(labels) != ia.typ.labels:
                    ia.update_type(VObject(labels, weak_method(self.get_device)))

    def get_device(self, device, serverStrings=None):
        """Create a weak reference to a new DeviceClient object (or existing)
        """
        assert self.loop_state() == LState.Running, \
            "Can't get device when process has not been started running"
        if device in self._device_clients:
            return self._device_clients[device]
        elif device in self._device_servers:
            return self._device_servers[device]
        # Calculate server strings if not given
        if serverStrings is None:
            assert self.ds is not None, "Can't lookup server string for {} "\
                "as no DirectoryService present".format(device)
            serverStrings = self.ds.connectionString(device=device)
        dc = self.DeviceClient(device, self.get_client_sock(serverStrings))
        # Don't add loop, we want it to go when no-one needs it
        dc.loop_run()
        self._device_clients[device] = dc
        return dc

    def get_client_sock(self, serverStrings):
        # If we already have a client sock, return that
        for string in serverStrings:
            string = string.replace("localhost", "127.0.0.1")
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
        serverStrings = []
        for string in self.serverStrings:
            ss = ServerSocket.make_socket(string, self.router.inq)
            assert ss is not None, "Can't make socket for {}".format(string)
            self._server_socks[string] = ss
            self.add_loop(ss)
            serverStrings.append(ss.name)
        self.serverStrings = serverStrings
        # Create a client to directory service
        if self.ds_string is not None:
            self.ds = self.get_device(self.ds_name, [self.ds_string])
            # Monitor ds and update all instance attributes
            self.ds.add_listener(self.on_device_list_changed,
                                 "attributes.instanceDevice")
        self.quitsig = self.cothread.Pulse()
        if block:
            self.quitsig.Wait()

    @wrap_method()
    def exit(self):
        """Stops the event loops and waits until they're done."""
        # Can't do super, as we've decorated it
        self.__del__()
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

    def do_func(self, send, f, args=None):
        if args is None:
            args = {}
        try:
            ret = f(**args)
        except Exception as e:
            self.log_exception("Error running {}.{}({})"
                               .format(f.device.name, f.name, args))
            send(SType.Error, e)
        else:
            send(SType.Return, ret)

    def do_call(self, send, endpoint, method, arguments=None):
        device, ename = self._get_device(endpoint)
        assert ename is None, \
            "Must Call with endpoint=<device> and method=<method>. " \
            "Got endpoint={} and method={}".format(endpoint, method)
        endpoint = device.get_endpoint("methods." + method)
        assert callable(endpoint), "Expected function, got {}".format(endpoint)
        if method == "exit" and device.name == self.name:
            send(SType.Return, None)
            # Let the socket send
            # self.cothread.Yield()
            return self.exit()
        elif method == "exit":
            self._device_servers.pop(device.name)
            self.update_devices()
        ct = self.cothread.Spawn(self.do_func, send, endpoint, arguments)
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

    def do_error(self, error, send, *args, **kwargs):
        EventLoop.error_handler(self.router, error, send, *args, **kwargs)
        send(SType.Error, error)
