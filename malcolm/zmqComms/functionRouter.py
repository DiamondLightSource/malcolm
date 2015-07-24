from serialize import deserialize, serialize_error, serialize_return, \
    serialize_call
import zmq
from base import ZmqProcess
from malcolm.core import wrap_method, Method
import logging
import datetime
log = logging.getLogger(__name__)


class FunctionRouter(ZmqProcess):
    def __init__(self, fe_addr="ipc://frfe.ipc", be_addr="ipc://frbe.ipc",
                 cs_addr="inproc://cachesig"):
        super(FunctionRouter, self).__init__()
        self.fe_addr = fe_addr
        self.be_addr = be_addr
        self.cs_addr = cs_addr
        self.fe_stream = None
        self.be_stream = None
        self.cs_stream = None
        self._devices = {}
        self.methods = Method.describe_methods(self)

    def setup(self):
        """Sets up PyZMQ and creates all streams."""
        super(FunctionRouter, self).setup()

        # Create the frontend stream and add the message handler
        self.fe_stream = self.stream(zmq.ROUTER, self.fe_addr, bind=True)
        self.fe_stream.on_recv(self.handle_fe)

        # Create the backend stream and add the message handler
        self.be_stream = self.stream(zmq.ROUTER, self.be_addr, bind=True)
        self.be_stream.on_recv(self.handle_be)

        # Create the cache signal stream and add the message handler
        self.cs_stream = self.stream(zmq.PAIR, self.cs_addr, bind=True)
        self.cs_stream.on_recv(self.handle_cs)

    def fe_send(self, clientid, data):
        log.debug("fe_send {}".format((clientid, data)))
        self.fe_stream.send_multipart([clientid, "", data])

    def be_send(self, deviceid, clientid, data):
        log.debug("be_send {}".format((deviceid, clientid, data)))
        self.be_stream.send_multipart([deviceid, clientid, "", data])

    def cs_send(self, device, pubsocket):
        self.cs_stream.send_multipart([device, pubsocket])

    def do_call(self, clientid, d, data):
        # check that we have the right type of message
        assert d["type"] == "call", "Expected type=call, got {}".format(d)
        device = d["device"]
        method = d["method"]        # get the function name
        if device == "malcolm":
            assert method in self.methods, \
                "Invalid internal method {}".format(method)
            ret = self.methods[method]()
            self.fe_send(clientid, serialize_return(ret))
        else:
            assert device in self._devices, \
                "No device named {} registered".format(device)
            # dispatch event to device
            self.be_send(self._devices[device], clientid, data)

    def do_get(self, clientid, d, data):
        # check that we have the right type of message
        assert d["type"] == "get", "Expected type=get, got {}".format(d)
        device = d["device"]
        if device == "malcolm":
            param = d.get("param")
            parameters = self
            if param is not None:
                for p in param.split("."):
                    try:
                        parameters = parameters[p]
                    except:
                        parameters = parameters.to_dict()[p]
            self.fe_send(clientid, serialize_return(parameters))
        else:
            assert device in self._devices, \
                "No device named {} registered".format(device)
            # dispatch event to device
            self.be_send(self._devices[device], clientid, data)

    def handle_fe(self, msg):
        log.debug("handle_fe {}".format(msg))
        clientid, _, data = msg
        # Classify what type of method it is
        try:
            d = deserialize(data)
        except Exception as e:
            self.fe_send(clientid, serialize_error(e))
            return
        # Now do the identified action
        try:
            getattr(self, "do_" + d["type"])(clientid, d, data)
        except Exception as e:
            # send error up the chain
            self.fe_send(clientid, serialize_error(e))

    def do_ready(self, deviceid, clientid, d, data):
        # initial clientid connect
        device = d["device"]
        assert device not in self._devices, \
            "Device {} already registered".format(device)
        self._devices[device] = deviceid
        # signal pubsub to connect to pubsocket
        self.cs_send(device, d["pubsocket"])

    def do_return(self, deviceid, clientid, d, data):
        if clientid != "":
            self.fe_send(clientid, data)

    def do_error(self, deviceid, clientid, d, data):
        self.fe_send(clientid, data)

    def handle_be(self, msg):
        log.debug("handle_be {}".format(msg))
        deviceid, clientid, _, data = msg
        # Classify what type of method it is
        try:
            d = deserialize(data)
        except Exception as e:
            self.be_send(deviceid, clientid, serialize_error(e))
            return
        # Now do the identified action
        try:
            getattr(self, "do_" + d["type"])(deviceid, clientid, d, data)
        except Exception as e:
            # send error up the chain
            self.be_send(deviceid, clientid, serialize_error(e))

    def handle_cs(self, device):
        self.be_send(
            self._devices[device], "", serialize_call(device, "pubstart"))

    @wrap_method(only_in=None)
    def devices(self):
        "List all available malcolm devices"
        return list(self._devices)

    @wrap_method(only_in=None)
    def pleasestopnow(self):
        "Stop the router and all of the devices attached to it"
        # stop all of our devices
        for device, deviceid in self._devices.items():
            self.be_send(deviceid, "", serialize_call(device, "pleasestopnow"))
        # Let our event loop run just long enough to send the message
        then = datetime.timedelta(milliseconds=1)
        self.loop.add_timeout(then, self.stop)

    def to_dict(self):
        d = dict(methods=self.methods)
        return d