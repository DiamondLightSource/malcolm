import multiprocessing
import sys

from .loop import HasLoops, EventLoop
from .serialize import SType


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


class Process(multiprocessing.Process, HasLoops):

    def __init__(self, name, timeout=None):
        super(Process, self).__init__(name, timeout)
        self.server_socks = []
        self.client_socks = []
        self.device_servers = {}
        self.device_clients = {}
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

    def _add_sock(self, sock, socks):
        socks.append(sock)
        self.add_loop(sock)

    def add_server_sock(self, sock):
        self._add_sock(sock, self.server_socks)

    def add_client_sock(self, sock):
        self._add_sock(sock, self.client_socks)

    def _remove_sock(self, sock, socks):
        socks.remove(sock)
        self.remove_loop(sock)

    def remove_server_sock(self, sock):
        self._remove_sock(sock, self.server_socks)

    def remove_client_sock(self, sock):
        self._remove_sock(sock, self.client_socks)

    def _add_device(self, device, devices):
        assert device.name not in self.device_servers.keys() + \
            self.device_clients.keys(), \
            "Already have a device called {}".format(device.name)
        devices[device.name] = device
        self.add_loop(device)

    def add_device_server(self, device):
        self._add_device(device, self.device_servers)

    def add_device_client(self, device):
        self._add_device(device, self.device_clients)

    def _remove_device(self, device, devices):
        devices.pop(device.name)
        self.remove_loop(device)

    def remove_device_server(self, device):
        self._remove_device(device, self.device_servers)

    def remove_device_client(self, device):
        self._remove_device(device, self.device_clients)

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
        super(Process, self).loop_run()
        self.quitsig = self.cothread.Pulse()
        if block:
            self.quitsig.Wait()

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
        if devicename in self.device_servers:
            device = self.device_servers[devicename]
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
        endpoint = self._get_endpoint(*self._get_device(endpoint))
        assert callable(endpoint), "Expected function, got {}".format(endpoint)
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
