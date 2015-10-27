import weakref
from collections import OrderedDict
import socket
import errno
import sys

from malcolm.core.transport import ServerSocket, SType
from malcolm.jsonpresentation.jsonpresenter import JsonPresenter


presenter = JsonPresenter()


class WsServerSocket(ServerSocket):

    def send(self, msg):
        """Send the message to the socket"""
        conn, msg = msg
        print "Sent", msg 
        conn.send(msg)

    def recv(self, timeout=None):
        """Co-operatively block until received"""
        if timeout is None:
            timeout = self.timeout
        while True:
            if len(self.inq):
                msg = self.inq.Wait()
                sys.stdout.write("Got message {}\n".format(msg))
                sys.stdout.flush()
                return msg
            print "wait"
            if self.poll_list(self.event_list, timeout):
                print "handle"
                self.server._handle_request_noblock()
                print "handled"
                # Let the other real thread put something on our input queue
                self.cothread.Sleep(0.25)
            else:
                # TODO: Wrong!
                raise StopIteration

    def serialize(self, typ, kwargs):
        """Serialize the arguments to a string that can be sent to the socket
        """
        kwargs.pop("ws_id", None)
        _id = kwargs.pop("id")
        assert type(_id) == int, "Need an integer ID, got {}".format(_id)
        assert typ in SType, \
            "Expected type in {}, got {}".format(list(SType.__members__), typ)
        d = OrderedDict(type=typ.name)
        d.update(id=_id)
        if kwargs is not None:
            d.update(kwargs)
        s = presenter.serialize(d)
        return s

    def deserialize(self, msg):
        """Deserialize the string to
        (typ, kwargs)"""
        ws_id, data = msg
        d = presenter.deserialize(data)
        typ = d.pop("type")
        assert typ in SType.__members__, \
            "Expected type in {}, got {}".format(list(SType.__members__), typ)
        typ = SType.__members__[typ]
        assert "id" in d, "No id in {}".format(d)
        d["ws_id"] = ws_id
        return typ, d

    def open(self, address):
        """Open the socket on the given address"""
        from cothread import coselect
        self.poll_list = coselect.poll_list
        import cothread
        self.inq = cothread.ThreadedEventQueue()
        from wsgiref.simple_server import make_server
        from ws4py.websocket import WebSocket
        from ws4py.server.wsgirefserver import WSGIServer, WebSocketWSGIRequestHandler
        from ws4py.server.wsgiutils import WebSocketWSGIApplication

        class WsConnection(WebSocket):
            def received_message(self, msg, inq=self.inq):
                msg = str(msg)
                print "Got", msg
                inq.Signal([self, msg])

        host, port = address.split("://")[1].split(":")
        app = WebSocketWSGIApplication(handler_cls=WsConnection)
        server = make_server(host, int(port), server_class=WSGIServer,
                             handler_class=WebSocketWSGIRequestHandler,
                             app=app)
        server.initialize_websockets_manager()
        self.server = server
        self.event_list = [(server.socket, coselect.POLLIN)]

    def close(self):
        """Close the socket"""
        self.server.server_close()

    def make_send_function(self, kwargs):
        """Make a send function that will call send with suitable arguments
        to be used as a response function"""
        if not hasattr(self, "_send_functions"):
            self._send_functions = weakref.WeakValueDictionary()
        ws_id = kwargs.pop("ws_id")
        _id = kwargs.pop("id")
        if (ws_id, _id) not in self._send_functions:
            self = weakref.proxy(self)

            def send(typ, value=None, **kwargs):
                kwargs = OrderedDict(id=_id)
                if typ == SType.Error:
                    kwargs.update(message=value.message)
                else:
                    if hasattr(value, "to_dict"):
                        value = value.to_dict()
                    kwargs.update(value=value)
                msg = self.serialize(typ, kwargs)
                try:
                    ws_id.send(msg)
                except socket.error as error:
                    if error.errno != errno.EHOSTUNREACH:
                        raise
                    # Unsubscribe all things with this ws id
                    sends = []
                    for (z, i) in self._send_functions.keys():
                        if z == ws_id:
                            sends.append(self._send_functions.pop((z, i)))
                    if sends:
                        self.log_debug("Unsubscribing {}"
                                       .format([s.endpoint for s in sends]))
                        for send in sends:
                            self.processq.Signal(
                                (SType.Unsubscribe, [send], {}))

            self._send_functions[(ws_id, _id)] = send
        return self._send_functions[(ws_id, _id)]

WsServerSocket.register("ws://")
WsServerSocket.register("wss://")
