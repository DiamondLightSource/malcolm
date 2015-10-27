from ws4py.client.threadedclient import WebSocketClient


class DummyClient(WebSocketClient):
    def opened(self):
        print "opened"
        self.send("boo")

    def closed(self, code, reason=None):
        print "Closed down", code, reason

    def received_message(self, m):
        print "got", m

if __name__ == '__main__':
    try:
        ws = DummyClient('ws://127.0.0.1:9000', protocols=['http-only', 'chat'])
        ws.connect()
        ws.run_forever()
    except KeyboardInterrupt:
        ws.close()