from collections import OrderedDict

import cothread
from cothread.cosocket import socket


class Zebra2Comms(object):

    def __init__(self, hostname, port):
        self.sock = socket()
        self.sock.connect((hostname, port))
        self.respq = cothread.EventQueue()
        self.outq = cothread.EventQueue()
        cothread.Spawn(self.recv_task)

    def send_recv(self, msg):
        q = cothread.EventQueue()
        self.respq.Signal(q)
        self.sock.send(msg)
        resp = q.Wait(1.0)
        if isinstance(resp, Exception):
            raise resp
        else:
            return resp

    def get_lines(self):
        buf = ""
        while True:
            lines = buf.split("\n")
            for line in lines[:-1]:
                #print "Yield", repr(line)
                yield line
            buf = lines[-1]
            # Get something new from the socket
            rx = self.sock.recv(4096)
            assert rx, "Didn't get response in time"
            buf += rx

    def recv_task(self):
        self._resp = []
        self._is_multiline = None
        for line in self.get_lines():
            #print "Line", line
            if self._is_multiline is None:
                self._is_multiline = line.startswith("!") or line == "."
            if line.startswith("ERR"):
                self._respond(ValueError(line))
            elif self._is_multiline:
                if line == ".":
                    self._respond(self._resp)
                else:
                    assert line[0] == "!", \
                        "Multiline response {} doesn't start with !" \
                        .format(repr(line))
                    self._resp.append(line[1:])
            else:
                self._respond(line)

    def _respond(self, resp):
        q = self.respq.Wait(0.1)
        q.Signal(resp)
        #print "Signal", resp
        self._resp = []
        self._is_multiline = None

    def get_num_blocks(self):
        num_blocks = OrderedDict()
        for line in self.send_recv("*BLOCKS?\n"):
            block, num = line.split()
            num_blocks[block] = int(num)
        return num_blocks

    def get_field_data(self, block):
        results = {}
        for line in self.send_recv("{}.*?\n".format(block)):
            data = line.split()
            assert len(data) in (3, 4), \
                "Expected field_data to have len 3 or 4, got {}"\
                .format(len(data))
            if len(data) == 3:
                data.append("")
            name, index, cls, typ = data
            results[int(index)] = (name, cls, typ)
        field_data = OrderedDict()
        for _, (name, cls, typ) in sorted(results.items()):
            field_data[name] = (cls, typ)
        return field_data

    def get_enum_labels(self, block, field):
        enum_labels = []
        for line in self.send_recv("{}.{}.LABELS?\n".format(block, field)):
            enum_labels.append(line)
        return enum_labels

    def get_changes(self):
        changes = OrderedDict()
        for line in self.send_recv("*CHANGES?\n"):
            if line.endswith("(error)"):
                field = line.split(" ", 1)[0]
                val = Exception
            elif "<" in line:
                # table
                pass
            else:
                field, val = line.split("=", 1)
            changes[field] = val
        return changes

    def set_field(self, block, field, value):
        resp = self.send_recv("{}.{}={}\n".format(block, field, value))
        assert resp == "OK", \
            "Expected OK, got {}".format(resp)

    def get_bits(self):
        bits = []
        for i in range(4):
            bits += self.send_recv("*BITS{}?\n".format(i))
        return bits

    def get_positions(self):
        return self.send_recv("*POSITIONS?\n")
