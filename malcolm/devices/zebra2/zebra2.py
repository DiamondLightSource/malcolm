from collections import OrderedDict

from malcolm.core.flowgraph import FlowGraph
from .zebra2comms import Zebra2Comms
from .zebra2block import Zebra2Block
from malcolm.core.loop import TimerLoop
from malcolm.core.alarm import Alarm, AlarmSeverity, AlarmStatus


class Zebra2(FlowGraph):

    def __init__(self, name, hostname, port):
        super(Zebra2, self).__init__(name)
        self.comms = Zebra2Comms(hostname, port)
        # Read the blocks from the server
        self.num_blocks = self.comms.get_num_blocks()
        self._blocks = OrderedDict()
        # Now create N block objects based on this info
        for block, num in self.num_blocks.items():
            for i in range(num):
                self.make_block(block, i)
        # Publish these blocks
        self.blocks = [b.name for b in self._blocks.values()]
        # Now poll them at 10Hz
        self.timer = TimerLoop("{}.Poller".format(name), self.do_poll, 0.1)
        self.add_loop(self.timer)

    def make_block(self, block, i):
        field_data = self.comms.get_field_data(block)
        # TODO: make this i+1 when the server supports it
        blockname = "{}:{}{}".format(self.name, block, i)
        self._blocks["{}{}".format(block, i)] = Zebra2Block(
            blockname, self.comms, field_data)

    def do_poll(self):
        changes = self.comms.get_changes()
        for field, val in changes.items():
            block, field = field.split(".", 1)
            assert block in self._blocks, \
                "Block {} not known".format(block)
            block = self._blocks[block]
            if "." in field:
                print "Not supported yet... {}".format(field)
            else:
                print block, field, val
                self.update_attribute(block, field, val)

    def update_attribute(self, block, field, val):
        assert field in block.attributes, \
            "Block {} has no attribute {}".format(block.name, field)
        attr = block.attributes[field]
        if val == Exception:
            # set error
            alarm = Alarm(AlarmSeverity.majorAlarm, AlarmStatus.Calc,
                          "Not in range")
            attr.update(alarm=alarm)
        else:
            attr.update(val)
