from collections import OrderedDict

from enum import Enum

from .stateMachine import StateMachine
from .device import Device, not_process_creatable


class PvEvent(Enum):
    # These are the messages we will respond to
    Attribute, Config, Abort = range(3)


class PvSeqSet(dict):

    def __init__(self, desc, **d):
        self.desc = desc
        self.update(d)
        self.set_extra()

    def set_extra(self, always=None, pre=None, post=None, abort=None):
        if always is None:
            self.always = []
        else:
            self.always = always
        self.pre = pre
        self.post = post
        self.abort = abort


@not_process_creatable
class PvSeq(Device):

    def __init__(self, name, device, *seq_sets):
        # superclass init
        super(PvSeq, self).__init__(name)

        # Make enum
        states = ["Idle"]
        for i in range(len(seq_sets)):
            states.append('SeqSet{}'.format(i + 1))
        self.PvState = Enum('PvState', states + ["Ready"])

        # Make a statemachine
        sm = StateMachine(name + ".stateMachine", self.PvState.Idle)
        self.add_stateMachine(sm)

        # listen to attributes
        self.device_attributes = device.attributes
        device.add_listener(self.on_attribute_change, "attributes")

        # some shortcuts for the state table
        do, t, s, e = self.shortcuts(self.PvState, PvEvent)

        # Store pvs that need to be set on exit from this state
        # dict state_name -> PVSequenceSet
        self.seq_sets = OrderedDict()

        # For current state, what are we waiting for to progress to next state
        # dict state_name -> (dict attr_name -> bool)
        self.match_attrs = {}

        # Add configure transition to first event
        state = self.PvState.SeqSet1
        t(self.rest_states(), PvEvent.Config, do.config_set, state)

        # Now add attribute transitions to subsequent states
        for i, ss in enumerate(seq_sets):
            self.seq_sets[state] = ss
            next_state = list(self.PvState)[state.value]
            t(state, PvEvent.Attribute, do.config_set, state, next_state)
            state = next_state

        # Add check when Ready for config mismatches
        t(s.Ready, e.Attribute, do.check, s.Ready, s.Idle)

        # Add abort for non-rest states
        non_rest = [x for x in list(s) if x not in self.rest_states()]
        t(non_rest, e.Abort, do.abort, s.Idle)

    def rest_states(self):
        return [self.PvState.Idle, self.PvState.Ready]

    def is_ready(self):
        return self.state == self.PvState.Ready

    def configure(self, config_params):
        assert self.state in self.rest_states(), \
            "Can't configure in {} state".format(self.state())
        self.stateMachine.post(PvEvent.Config, config_params=config_params)

    def abort(self):
        assert self.state not in self.rest_states(), \
            "Can't abort in {} state".format(self.state())
        self.stateMachine.post(PvEvent.Abort)

    def on_attribute_change(self, attributes, changes):
        prefixes = set(x.split(".")[0] for x in changes)
        assert len(prefixes) == 1, \
            "Only expected one attribute to change at once, got {}" \
            .format(prefixes)
        attr = prefixes.pop()
        value = self.device_attributes[attr].value
        self.stateMachine.post(PvEvent.Attribute, attr, value)

    def do_abort(self):
        seq_set = self.seq_sets[self.state]
        if seq_set.abort:
            seq_set.abort()
        return self.PvState.Idle, "Aborted"

    def do_check(self, attr=None, value=None):
        "Check if current config matches required"
        mismatches = []
        for attr, expected in sorted(self.config_params.items()):
            actual = self.device_attributes[attr].value
            if actual != expected:
                mismatches.append("{}: {!r} != {!r}".format(
                    attr, actual, expected))
        if len(mismatches) == 0:
            # No change
            return None, None
        else:
            return self.PvState.Idle, ", ".join(mismatches)

    def do_config_set(self, attr=None, value=None, config_params=None):
        done = False
        # if we got a configure, then store params and we're ready to move on
        if config_params:
            self.config_params = config_params
            done = True
        # otherwise, if there is nothing to set, just move on
        elif attr is None and len(self.match_attrs[self.state]) == 0:
            done = True
        # otherwise, if an attribute changed that we're waiting for, check
        # if all our monitored attributes have changed
        elif attr in self.match_attrs[self.state]:
            match_attrs = self.match_attrs[self.state]
            # check its demand matches actual
            if self.config_params[attr] == self.device_attributes[attr].value:
                match_attrs[attr] = True
            done = all(match_attrs.values())
        # work out which is the next state
        next_state = list(self.PvState)[self.state.value]
        # if next state is Ready, just go there
        if done and next_state == self.PvState.Ready:
            return next_state, "Configuring finished"
        elif done:
            # make a list of attributes we are changing for the next state to
            # check
            match_attrs = {}
            self.match_attrs[next_state] = match_attrs
            seq_set = self.seq_sets[next_state]
            for attr in seq_set:
                if attr in self.config_params:
                    value = self.config_params[attr]
                else:
                    value = seq_set[attr]
                if value in seq_set.always or \
                        value != self.device_attributes[attr].value:
                    match_attrs[attr] = False
                    self.config_params[attr] = value
                    self.device_attributes[attr].update(value)
            # Call our post function if we have one
            if seq_set.post:
                seq_set.post(self.config_params)
            # If there is nothing to set, prompt the next state
            if len(match_attrs) == 0:
                self.stateMachine.post(PvEvent.Attribute)
            return next_state, seq_set.desc
        else:
            # No change
            return None, None
