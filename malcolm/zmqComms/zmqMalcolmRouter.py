from malcolm.zmqComms.zmqSerialize import deserialize, serialize_error, \
    serialize_return, serialize_call, SType
import zmq
from zmqProcess import ZmqProcess
from malcolm.core import wrap_method, Method
import logging
log = logging.getLogger(__name__)


class ZmqMalcolmRouter(ZmqProcess):

    def __init__(self, fe_addr="ipc://frfe.ipc", be_addr="ipc://frbe.ipc",
                 timeout=None):
        super(ZmqMalcolmRouter, self).__init__(timeout)
        self.fe_addr = fe_addr
        self.be_addr = be_addr
        self.fe_stream = None
        self.be_stream = None
        self._devices = {}
        self.methods = Method.describe_methods(self)

    def setup(self):
        """Sets up PyZMQ and creates all streams."""
        super(ZmqMalcolmRouter, self).setup()

        # Create the frontend stream and add the message handler
        self.fe_stream = self.stream(zmq.ROUTER, self.fe_addr, bind=True)
        self.fe_stream.on_recv(self.handle_fe)
        log.info("Binding client facing socket on {}".format(self.fe_addr))

        # Create the backend stream and add the message handler
        self.be_stream = self.stream(zmq.ROUTER, self.be_addr, bind=True)
        self.be_stream.on_recv(self.handle_be)
        log.info("Binding device facing socket on {}".format(self.be_addr))

    def fe_send(self, clientid, data):
        log.debug("fe_send {}".format((clientid, data)))
        self.fe_stream.send_multipart([clientid, data])

    def be_send(self, deviceid, clientid, data):
        log.debug("be_send {}".format((deviceid, clientid, data)))
        self.be_stream.send_multipart([deviceid, clientid, data])

    def do_call(self, clientid, d, data):
        # check that we have the right type of message
        device, method = d["method"].split(".", 1)
        if device == "malcolm":
            assert method in self.methods, \
                "Invalid internal method {}".format(method)
            ret = self.methods[method]()
            self.fe_send(clientid, serialize_return(d["id"], ret))
        else:
            assert device in self._devices, \
                "No device named {} registered".format(device)
            # dispatch event to device
            self.be_send(self._devices[device], clientid, data)

    def do_get(self, clientid, d, data):
        # check that we have the right type of message
        param = d["param"]
        if "." in param:
            device, param = param.split(".", 1)
        else:
            device, param = param, None
        if device == "malcolm":
            parameters = self
            if param is not None:
                for p in param.split("."):
                    try:
                        parameters = parameters[p]
                    except:
                        parameters = parameters.to_dict()[p]
            self.fe_send(clientid, serialize_return(d["id"], parameters))
        else:
            assert device in self._devices, \
                "No device named {} registered".format(device)
            # dispatch event to device
            self.be_send(self._devices[device], clientid, data)

    def handle_fe(self, msg):
        log.debug("handle_fe {}".format(msg))
        clientid, data = msg
        # Classify what type of method it is
        try:
            d = deserialize(data)
        except Exception as e:
            self.fe_send(clientid, serialize_error(-1, e))
        else:
            # Now do the identified action
            try:
                func = {
                    SType.Call: self.do_call,
                    SType.Get: self.do_get,
                }[d["type"]]
                func(clientid, d, data)
            except Exception as e:
                # send error up the chain
                log.exception(e)
                self.fe_send(clientid, serialize_error(d["id"], e))

    def do_value(self, deviceid, clientid, d, data):
        assert "id" in d, "No id in {}".format(d)
        self.fe_send(clientid, data)

    def do_ready(self, deviceid, clientid, d, data):
        # initial clientid connect
        device = d["device"]
        assert device not in self._devices, \
            "Device {} already registered".format(device)
        log.info("Device {} connected".format(device))
        self._devices[device] = deviceid

    def do_return(self, deviceid, clientid, d, data):
        assert "id" in d, "No id in {}".format(d)
        if clientid != "":
            self.fe_send(clientid, data)

    def do_error(self, deviceid, clientid, d, data):
        assert "id" in d, "No id in {}".format(d)
        self.fe_send(clientid, data)

    def handle_be(self, msg):
        log.debug("handle_be {}".format(msg))
        deviceid, clientid, data = msg
        # Classify what type of method it is
        try:
            d = deserialize(data)
        except Exception as e:
            self.be_send(deviceid, clientid, serialize_error(-1, e))
            return
        # Now do the identified action
        try:
            func = {
                SType.Value: self.do_value,
                SType.Ready: self.do_ready,
                SType.Return: self.do_return,
                SType.Error: self.do_error,
            }[d["type"]]
            func(deviceid, clientid, d, data)
        except Exception as e:
            # send error up the chain
            log.exception(e)
            self.be_send(deviceid, clientid, serialize_error(-1, e))

    @wrap_method(only_in=None)
    def devices(self):
        "List all available malcolm devices"
        return list(self._devices)

    @wrap_method(only_in=None)
    def pleasestopnow(self):
        "Stop the router and all of the devices attached to it"
        # stop all of our devices
        for device, deviceid in self._devices.items():
            self.be_send(
                deviceid, "", serialize_call(-1, device + ".pleasestopnow"))
        self.stop()

    def to_dict(self):
        d = dict(methods=self.methods)
        return d
