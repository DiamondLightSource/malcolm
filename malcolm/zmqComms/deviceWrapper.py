from serialize import deserialize, serialize_ready, serialize_error, \
    serialize_return
import zmq
from zmqProcess import ZmqProcess
from zmq.eventloop.ioloop import PeriodicCallback
import cothread
import logging
log = logging.getLogger(__name__)


class DeviceWrapper(ZmqProcess):

    def __init__(self, name, device_class, be_addr="ipc://frbe.ipc",
                 **device_kwargs):
        super(DeviceWrapper, self).__init__()
        self.name = name
        self.be_addr = be_addr
        self.be_stream = None
        self.device_class = device_class
        self.device_kwargs = device_kwargs

    def setup(self):
        """Sets up PyZMQ and creates all streams."""
        super(DeviceWrapper, self).setup()

        # Make the device object and run it
        self.device = self.device_class(self.name, **self.device_kwargs)
        self.device.start_event_loop()

        # Create the frontend stream and add the message handler
        self.be_stream = self.stream(zmq.DEALER, self.be_addr, bind=False)
        self.be_stream.on_recv(self.handle_be)

        # Say hello
        self.be_send("", serialize_ready(self.name, "pubsocket"))

        # Let cothread get a lookin
        #self.periodic = PeriodicCallback(cothread.Yield, 5, self.loop)
        #self.periodic.start()

    def be_send(self, clientid, data):
        log.debug("be_send {}".format((clientid, data)))
        self.be_stream.send_multipart([clientid, "", data])

    def do_func(self, clientid, f, args):
        log.debug("do_func {} {}".format(f, args))
        try:
            ret = f(**args)
        except Exception as e:
            log.exception("{}: threw exception calling {}".format(self.name, f))
            self.be_send(clientid, serialize_error(e))
        else:
            self.be_send(clientid, serialize_return(ret))

    def do_call(self, clientid, d):
        # check that we have the right type of message
        assert d["type"] == "call", "Expected type=call, got {}".format(d)
        device = d["device"]
        assert device == self.name, "Wrong device name {}".format(device)
        method = d["method"]        # get the function name
        if method == "pleasestopnow":
            # Just stop now
            self.be_send(clientid, serialize_return(self.stop()))
        else:
            # Call a device method
            assert method in self.device.methods, \
                "Invalid function {}".format(method)
            args = d.get("args", {})
            # Run the function
            cothread.Spawn(
                self.do_func, clientid, self.device.methods[method], args)

    def do_get(self, clientid, d):
        # check that we have the right type of message
        assert d["type"] == "get", "Expected type=get, got {}".format(d)
        device = d["device"]
        assert device == self.name, "Wrong device name {}".format(device)
        param = d.get("param")
        parameters = self.device
        if param is not None:
            for p in param.split("."):
                try:
                    parameters = parameters[p]
                except:
                    parameters = parameters.to_dict()[p]
        self.be_send(clientid, serialize_return(parameters))

    def handle_be(self, msg):
        log.debug("handle_be {}".format(msg))
        clientid, _, data = msg
        # Classify what type of method it is
        try:
            d = deserialize(data)
        except Exception as e:
            self.be_send(clientid, serialize_error(e))
            return
        # Now do the identified action
        try:
            getattr(self, "do_" + d["type"])(clientid, d)
        except Exception as e:
            # send error up the chain
            self.be_send(clientid, serialize_error(e))
