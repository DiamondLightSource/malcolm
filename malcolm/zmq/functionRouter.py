from serialize import deserialize, serialize_error, serialize_return, serialize_method
import zmq
from base import ZmqProcess
import logging
log = logging.getLogger(__name__)


class FunctionRouter(ZmqProcess):
    # These functions are allowed to be called from externally
    internal_functions = ["stop", "devices"]

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

    def handle_fe(self, msg):
        log.debug("handle_fe {}".format(msg))
        clientid, _, data = msg
        # check who it's for
        split = deserialize(data)["name"].split(".", 1)
        if len(split) == 1:
            device, function = split[0], ""
        else:
            device, function = split
        if device == "malcolm":
            # internal
            if function in self.internal_functions:
                ret = getattr(self, function)()
                self.fe_send(clientid, serialize_return(ret))
            else:
                # return an error
                e = NameError("Invalid internal function {}".format(function))
                self.fe_send(clientid, serialize_error(e))
        elif device in self._devices:
            # dispatch event to device
            self.be_send(self._devices[device], clientid, data)
        else:
            # return an error
            e = NameError("No device named {} registered".format(device))
            self.fe_send(clientid, serialize_error(e))

    def handle_be(self, msg):
        log.debug("handle_be {}".format(msg))
        deviceid, clientid, _, data = msg
        # check message type
        d = deserialize(data)
        if d["name"] == "ready":
            # initial clientid connect
            device = d["device"]
            assert device not in self._devices, \
                "Device {} already registered".format(device)
            self._devices[device] = deviceid
            # signal pubsub to connect to pubsocket
            self.cs_send(device, d["pubsocket"])
        elif d["name"] in ["return", "error"]:
            # return to the client
            if clientid != "":
                self.fe_send(clientid, data)
        else:
            # log error
            log.warning(
                "Don't know what to do with be message {}".format(data))

    def handle_cs(self, device):
        self.be_send(self._devices[device], serialize_method(
            "{}.{}".format(device, "pubstart")))

    def devices(self):
        return list(self._devices)
