from collections import OrderedDict

from malcolm.core.flowgraph import FlowGraph
from .zebra2comms import Zebra2Comms
from .zebra2block import Zebra2Block
from .zebra2visibility import Zebra2Visibility
from malcolm.core.loop import TimerLoop
from malcolm.core.alarm import Alarm, AlarmSeverity, AlarmStatus
from malcolm.core import Attribute, VString, wrap_method
from malcolm.core.vtype import VBool


class Zebra2(FlowGraph):
    class_attributes = dict(
        hostname=Attribute(VString, "Hostname of zebra2 box"),
        port=Attribute(VString, "Config port of zebra2 server")
    )

    def __init__(self, name, hostname, port):
        super(Zebra2, self).__init__(name)
        self.comms = Zebra2Comms(hostname, port)
        # Read the blocks from the server
        self.num_blocks = self.comms.get_num_blocks()
        # Dict mapping str block_name -> Block instance
        self._blocks = OrderedDict()
        # (block, str field) -> [(listen_block, str mux_field)]
        self._muxes = {}
        # changes left over from last time
        self.changes = {}
        # blockname -> field_data for block
        self.field_data = {}
        # Now create N block objects based on this info
        for block, num in self.num_blocks.items():
            field_data = self.comms.get_field_data(block)
            if num == 1:
                self.make_block(block, "", field_data)
            else:
                for i in range(num):
                    self.make_block(block, i + 1, field_data)
        self.visibility = "{}:VISIBILITY".format(self.name)
        self._visibility = self.process.create_device(
            Zebra2Visibility, self.visibility, blocks=self._blocks)
        # Publish these blocks
        self.blocks = [b.name for b in self._blocks.values()]
        # Now poll them at 10Hz
        self.timer = TimerLoop("{}.Poller".format(name), self.do_poll, 0.1)
        self.add_loop(self.timer)

    def make_block(self, block, i, field_data):
        blockname = "{}:{}{}".format(self.name, block, i)
        self._blocks["{}{}".format(block, i)] = self.process.create_device(
            Zebra2Block, blockname, block=block, i=i, comms=self.comms,
            field_data=field_data, parent=self)

    def do_poll(self):
        self.changes.update(self.comms.get_changes())
        for fullfield, val in self.changes.items():
            block, field = fullfield.split(".", 1)
            if block not in self._blocks:
                print "Block {} not known".format(block)
                continue
            block = self._blocks[block]
            ret = self.update_attribute(block, field.replace(".", ":"), val)
            if ret is not None:
                self.changes[fullfield] = ret
            else:
                self.changes.pop(fullfield)

    def update_attribute(self, block, field, val):
        ret = None
        assert field in block.attributes, \
            "Block {} has no attribute {}".format(block.name, field)
        attr = block.attributes[field]
        if val == Exception:
            # set error
            alarm = Alarm(AlarmSeverity.majorAlarm, AlarmStatus.Calc,
                          "Not in range")
            attr.update(alarm=alarm)
        else:
            if isinstance(attr.typ, VBool):
                val = bool(int(val))
                if field in block.field_data and \
                        block.field_data[field][0] == "bit_out" and \
                        val == attr.value:
                    # make bit_out things toggle while changing
                    ret = val
                    val = not val
            attr.update(val)
            for listen_block, mux_field in self._muxes.get((block, field), []):
                val_attr = listen_block.attributes[mux_field + ":VAL"]
                val_attr.update(val)
        # if we changed the value of a pos_mux or bit_mux, update its value
        if field in block.field_data and \
                block.field_data[field][0] in ("bit_mux", "pos_mux"):
            # this is the attribute that needs to update
            for mux_list in self._muxes.values():
                try:
                    mux_list.remove((block, field))
                except ValueError:
                    pass
            # add it to the list of things that need to update
            mon_block_name, mon_field = val.split(".", 1)
            mon_block = self._blocks[mon_block_name]
            self._muxes.setdefault((mon_block, mon_field), []).append(
                (block, field))
            # update it to the right value
            val_attr = block.attributes[field + ":VAL"]
            val_attr.update(mon_block.attributes[mon_field].value)
            # make sure it's visible
            if mon_field != "ZERO" and block.VISIBLE != "Show":
                block._set_visible("Show")
        return ret
