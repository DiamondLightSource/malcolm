import cothread
import inspect

from serialize import deserialize, serialize_ready, serialize_error, serialize_return
import zmq
from base import ZmqProcess
import logging
log = logging.getLogger(__name__)


class FunctionRunner(ZmqProcess):

    def __init__(self, name, device_class, be_addr="ipc://frbe.ipc", **device_kwargs):
        super(FunctionRunner, self).__init__()
        self.name = name
        self.be_addr = be_addr
        self.be_stream = None
        self.functions = dict(stop=self.stop)
        self.device_class = device_class
        self.device_kwargs = device_kwargs

    def setup(self):
        """Sets up PyZMQ and creates all streams."""
        super(FunctionRunner, self).setup()

        # Make the device object and run it
        self.device = self.device_class(self.name, **self.device_kwargs)
        self.device.start_event_loop()

        # Add decorated functions to list of available functions
        for fname, f in inspect.getmembers(self.device,
                                           predicate=inspect.ismethod):
            if f.func_name == "decorated_command":
                self.functions[fname] = f

        # Create the frontend stream and add the message handler
        self.be_stream = self.stream(zmq.DEALER, self.be_addr, bind=False)
        self.be_stream.on_recv(self.handle_be)

        # Say hello
        self.be_send("", serialize_ready(self.name, "pubsocket"))

    def be_send(self, clientid, data):
        log.debug("be_send {}".format((clientid, data)))
        self.be_stream.send_multipart([clientid, "", data])

    def do_func(self, clientid, f, args):
        try:
            ret = f(**args)
        except Exception as e:
            self.be_send(clientid, serialize_error(e))
        else:
            self.be_send(clientid, serialize_return(ret))

    def handle_be(self, msg):
        log.debug("handle_be {}".format(msg))
        clientid, _, data = msg
        # check message type
        d = deserialize(data)
        split = deserialize(data)["name"].split(".", 1)
        if len(split) == 1:
            fname = split[0]
        else:
            device, fname = split
            if device != self.name:
                e = NameError("Wrong device name {}".format(device))
                self.be_send(clientid, serialize_error(e))
                return
        if fname in self.functions:
            cothread.Spawn(
                self.do_func, clientid, self.functions[fname], d["args"])
        else:
            e = NameError("Invalid function {}".format(fname))
            self.be_send(clientid, serialize_error(e))
