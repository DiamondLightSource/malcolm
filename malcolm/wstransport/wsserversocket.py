import cothread
cothread.coselect.select_hook()
cothread.cosocket.socket_hook()

@cothread.Spawn
def ticker():
    i = 0
    while True:
        print i
        i += 1
        cothread.Sleep(1)

import weakref
from collections import OrderedDict
import socket
import errno
import sys
import os

        
from malcolm.core.transport import ServerSocket, SType
from malcolm.jsonpresentation.jsonpresenter import JsonPresenter

presenter = JsonPresenter()


from wsgiref.simple_server import WSGIServer as _WSGIServer

from .fileserver import FileServer


class WSGIServer(_WSGIServer):

    def shutdown_request(self, request):
        """
        The base class would close our socket
        if we didn't override it.
        """
        pass

    def server_close(self):
        """
        Properly initiate closing handshakes on
        all websockets when the WSGI server terminates.
        """
        print "closing sockets"
        _WSGIServer.server_close(self)


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
        return self.inq.Wait(timeout)

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
        self.inq = cothread.EventQueue()
        return
        from wsgiref.simple_server import make_server
        from ws4py.websocket import WebSocket

        class WsConnection(WebSocket):

            def received_message(self, msg, inq=self.inq):
                msg = str(msg)
                print "Got", msg
                inq.Signal([self, msg])

        host, port = address.split("://")[1].split(":")
        path = os.path.join(os.path.dirname(__file__), "static")
        application = FileServer(path, WsConnection)
        server = make_server(host, int(port), application,
                             server_class=WSGIServer)
        #cothread.Spawn(server.serve_forever)
        self.server = server

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
