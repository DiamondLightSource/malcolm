from collections import OrderedDict

from cothread.cosocket import socket


class Zebra2Comms(object):

    def __init__(self, hostname, port):
        self.sock = socket()
        self.sock.connect((hostname, port))
        self.buffer = ""
        self.line_iterator = self.get_line()

    def get_line(self):
        while True:
            lines = self.buffer.split("\n")
            for line in lines[:-1]:
                yield line
            self.buffer = lines[-1]
            # Get something new from the socket
            rx = self.sock.recv(4096)
            assert rx, "Didn't get response in time"
            self.buffer += rx

    def get_response(self, is_multiline=None):
        if is_multiline:
            ret = []
        for line in self.line_iterator:
            if is_multiline is None:
                is_multiline = line.startswith("!") or line == "."
                ret = []
            if line.startswith("ERR"):
                raise ValueError(line)
            elif is_multiline:
                if line == ".":
                    return ret
                else:
                    assert line[0] == "!", \
                        "Multiline response {} doesn't start with !" \
                        .format(repr(line))
                    ret.append(line[1:])
            else:
                return line

    def get_num_blocks(self):
        self.sock.send("*BLOCKS?\n")
        num_blocks = OrderedDict()
        for line in self.get_response():
            block, num = line.split()
            num_blocks[block] = int(num)
        return num_blocks

    def get_field_data(self, block):
        self.sock.send("{}.*?\n".format(block))
        results = {}
        for line in self.get_response():
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
        self.sock.send("{}.{}.LABELS?\n".format(block, field))
        enum_labels = OrderedDict()
        for line in self.get_response():
            index, string = line.split(" ", 1)
            enum_labels[int(index)] = string
        return enum_labels

    def get_changes(self):
        self.sock.send("*CHANGES?\n")
        changes = OrderedDict()
        for line in self.get_response():
            if line.endswith("(error)"):
                field = line.split(" ", 1)[0]
                val = Exception
            else:
                field, val = line.split("=", 1)
            changes[field] = val
        return changes

    def set_field(self, block, field, value):
        self.sock.send("{}.{}={}\n".format(block, field, value))
        resp = self.get_response()
        assert resp == "OK", \
            "Expected OK, got {}".format(resp)
