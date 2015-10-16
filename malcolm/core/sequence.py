import abc
from collections import OrderedDict

from enum import Enum

from .base import Base
from .device import Device, not_process_creatable
from .stateMachine import StateMachine


class SeqEvent(Enum):
    # These are the messages we will respond to
    Start, Changes, Abort = range(3)


class SeqItem(Base):

    def __init__(self, desc, **seq_params):
        # name is desc
        super(SeqItem, self).__init__(desc)
        # store any default parameters
        self.seq_params = seq_params

    @abc.abstractmethod
    def start(self, ctx, params):
        """Called once when sequence item is entered, return True if item is
        done"""

    @abc.abstractmethod
    def done(self, ctx, changes):
        """Should return True if all the expected actions are done"""

    @abc.abstractmethod
    def mismatches(self, ctx):
        """Should return any mismatches from start values"""

    @abc.abstractmethod
    def abort(self, ctx):
        """Called to abort sequence"""


class AttributeSeqItem(SeqItem):

    def set_extra(self, always=None, post=None, abort=None):
        if always:
            self.always = always
        if post:
            self.post = post
        if abort:
            self.abort = abort

    def start(self, attributes, params):
        self.match_attrs = {}
        self.check_params = params
        for attr, value in self.seq_params.items():
            # If asked to set attribute that has been supplied here, use
            # that value
            if attr in self.check_params:
                value = self.check_params[attr]
            # Otherwise update our check params with
            else:
                self.check_params[attr] = value
            # Check if we should always set this attribute
            always = hasattr(self, "always") and value in self.always
            # If always or if value doesn't match
            if always or value != attributes[attr].value:
                self.match_attrs[attr] = False
                attributes[attr].update(value)
        # Call our post function if we have one
        if hasattr(self, "post"):
            self.post(self.check_params)
        # Return if we're done
        is_done = len(self.match_attrs) == 0
        return is_done

    def done(self, attributes, changes):
        prefixes = set(x.split(".")[0] for x in changes)
        assert len(prefixes) == 1, \
            "Only expected one attribute to change at once, got {}" \
            .format(prefixes)
        attr = prefixes.pop()
        if attr in self.match_attrs and \
                self.check_params[attr] == attributes[attr].value:
            self.match_attrs[attr] = True
        is_done = all(self.match_attrs.values())
        return is_done

    def mismatches(self, attributes):
        mismatches = []
        for attr, expected in sorted(self.check_params.items()):
            actual = attributes[attr].value
            if actual != expected:
                mismatches.append("{}: {!r} != {!r}".format(
                    attr, actual, expected))
        if mismatches:
            return ", ".join(mismatches)

    def abort(self, attributes):
        if hasattr(self, "abort"):
            self.abort(attributes)


@not_process_creatable
class Sequence(Device):

    def __init__(self, name, ctx, *seq_items):
        # superclass init
        super(Sequence, self).__init__(name)

        # check we have at least one seq item
        assert len(seq_items) > 0, \
            "Expected >1 SeqItems"

        # check that they're all of the right type
        for item in seq_items:
            assert isinstance(item, SeqItem), \
                "Expected SeqItem, got {}".format(item)

        # store context
        self.ctx = ctx

        # Make enum
        states = ["Idle"]
        for i in range(len(seq_items)):
            states.append('SeqItem{}'.format(i + 1))
        self.SeqState = Enum('SeqState', states + ["Ready"])

        # Make a statemachine
        sm = StateMachine(name + ".stateMachine", self.SeqState.Idle)
        self.add_stateMachine(sm)

        # some shortcuts for the state table
        do, t, s, e = self.shortcuts(self.SeqState, SeqEvent)

        # Store pvs that need to be set on exit from this state
        # dict state_name -> PVSequenceSet
        self.seq_items = OrderedDict()

        # Add configure transition to first event
        state = self.SeqState.SeqItem1
        t(self.rest_states(), e.Start, do.start, state)

        # Now add attribute transitions to subsequent states
        for i, ss in enumerate(seq_items):
            self.seq_items[state] = ss
            next_state = list(self.SeqState)[state.value]
            t(state, e.Changes, do.check, state, next_state)
            state = next_state

        # Add check when Ready for config mismatches
        t(s.Ready, e.Changes, do.mismatches, s.Ready, s.Idle)

        # Add abort for non-rest states
        non_rest = [x for x in list(s) if x not in self.rest_states()]
        t(non_rest, e.Abort, do.abort, s.Idle)

    def rest_states(self):
        return [self.SeqState.Idle, self.SeqState.Ready]

    def start(self, params):
        assert self.state in self.rest_states(), \
            "Can't start in {} state".format(self.state)
        self.stateMachine.post(SeqEvent.Start, params=params)

    def abort(self):
        assert self.state not in self.rest_states(), \
            "Can't abort in {} state".format(self.state)
        self.stateMachine.post(SeqEvent.Abort)

    def do_start(self, params):
        # store user params
        self.params = params
        # start first seq item
        next_state = self.SeqState.SeqItem1
        seq_item = self.seq_items[next_state]
        self._start_item(seq_item)
        return next_state, seq_item.name

    def _start_item(self, seq_item):
        is_done = seq_item.start(self.ctx, self.params)
        if is_done:
            self.stateMachine.post(SeqEvent.Changes, is_done=True)

    def on_change(self, value, changes):
        if self.state == self.SeqState.Idle:
            return
        else:
            self.stateMachine.post(SeqEvent.Changes, changes)

    def do_check(self, changes=None, is_done=False):
        if not is_done:
            is_done = self.seq_items[self.state].done(self.ctx, changes)
        if is_done:
            # Done with this item, move on to the next
            next_state = list(self.SeqState)[self.state.value]
            if next_state == self.SeqState.Ready:
                # Done
                return next_state, "Ready"
            else:
                # Start the next item
                seq_item = self.seq_items[next_state]
                self._start_item(seq_item)
                return next_state, seq_item.name
        else:
            # No change
            return None, None

    def do_mismatches(self, changes):
        mismatches = []
        for seq_item in self.seq_items.values():
            mismatch = seq_item.mismatches(self.ctx)
            if mismatch:
                mismatches.append(mismatch)
        if len(mismatches) == 0:
            # No change
            return None, None
        else:
            return self.SeqState.Idle, ", ".join(mismatches)

    def do_abort(self):
        self.seq_items[self.state].abort()
        return self.SeqState.Idle, "Aborted"
