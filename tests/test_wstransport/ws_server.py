from wsgiref.simple_server import make_server
from ws4py.websocket import EchoWebSocket
from ws4py.server.wsgirefserver import WSGIServer, WebSocketWSGIRequestHandler
from ws4py.server.wsgiutils import WebSocketWSGIApplication


class MyEcho(EchoWebSocket):
    def opened(self):
        print "opened"

    def received_message(self, message):
        print message
        EchoWebSocket.received_message(self, message)


server = make_server('localhost', 9000, server_class=WSGIServer,
                     handler_class=WebSocketWSGIRequestHandler,
                     app=WebSocketWSGIApplication(handler_cls=MyEcho))
server.initialize_websockets_manager()
server.serve_forever()

