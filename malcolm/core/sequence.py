import abc
from collections import OrderedDict
import time

from enum import Enum

from .base import Base
from .device import Device, not_process_creatable
from malcolm.core.statemachine import StateMachine


class SeqEvent(Enum):
    # These are the messages we will respond to
    Start, Changes, Abort = range(3)


class SeqItem(Base):

    @abc.abstractmethod
    def start(self, params, t):
        """Called once when sequence item is entered, return True if item is
        done"""

    def done(self, changes):
        """Should return True if all the expected actions are done"""
        return True

    def mismatches(self):
        """Should return any mismatches from start values"""
        return None

    def abort(self):
        """Called to abort sequence"""
        pass


class SeqAttributeItem(SeqItem):

    def __init__(self, desc, attributes, **seq_params):
        # name is desc
        super(SeqAttributeItem, self).__init__(desc)
        # store attributes
        self.attributes = attributes
        self.seq_params = seq_params

    def set_extra(self, always=None, post=None):
        if always:
            self.always = always
        if post:
            self.post = post

    def start(self, params, t):
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
            # If value is None, nothing to do
            if value is None:
                continue
            # Check if we should always set this attribute
            always = hasattr(self, "always") and attr in self.always
            # If always or if value doesn't match
            if always or value != self.attributes[attr].value:
                self.match_attrs[attr] = False
                self.attributes[attr].update(value)
        # Call our post function if we have one
        if hasattr(self, "post"):
            self.post(self.check_params)
        # Return if we're done
        is_done = len(self.match_attrs) == 0
        return is_done

    def done(self, changes):
        prefixes = set(x.split(".")[0] for x in changes)
        assert len(prefixes) == 1, \
            "Only expected one attribute to change at once, got {}" \
            .format(prefixes)
        attr = prefixes.pop()
        if attr in self.match_attrs and \
                self.attributes[attr].value_equal(self.check_params[attr]):
            self.match_attrs[attr] = True
        is_done = all(self.match_attrs.values())
        return is_done

    def mismatches(self):
        mismatches = []
        for attr, expected in sorted(self.check_params.items()):
            actual = self.attributes[attr].value
            if actual != expected:
                mismatches.append("{}: {!r} != {!r}".format(
                    attr, actual, expected))
        if mismatches:
            return ", ".join(mismatches)


class SeqFunctionItem(SeqItem):

    def __init__(self, desc, func, **params):
        # name is desc
        super(SeqFunctionItem, self).__init__(desc)
        # this is the function we will call on start()
        self.func = func
        # store params to pass
        self.params = params

    def start(self, params, t):
        self.func(**self.params)
        return True


class SeqStateItem(SeqItem):

    def __init__(self, desc, device, desired, rest):
        # name is desc
        super(SeqStateItem, self).__init__(desc)
        # this is the function we will call on start()
        self.device = device
        self.desired = desired
        self.rest = rest
        assert desired in rest, \
            "{} should be in {}".format(desired, rest)

    def start(self, params, t):
        # Check whether we have transitioned to this state since seq began
        if self.device.stateMachine.timeStamp < t:
            return False
        else:
            return self.done()

    def done(self, changes=None):
        if self.device.state in self.rest:
            assert self.device.state == self.desired, \
                "Expected {}, got {}".format(self.desired, self.device.state)
            return True
        else:
            return False

    def mismatches(self):
        if self.device.state != self.desired:
            actual = self.device.state.name
            expected = self.desired.name
            m = "{}: {} not in {}".format(self.device.name, actual, expected)
            return m


class SeqAttributeReadItem(SeqItem):

    def __init__(self, desc, attribute, desired):
        # name is desc
        super(SeqAttributeReadItem, self).__init__(desc)
        # this is the function we will call on start()
        self.attribute = attribute
        self.desired = desired

    def start(self, params, t):
        # Check whether we have transitioned to this state since seq began
        if self.attribute.timeStamp < t:
            return False
        else:
            return self.done()

    def done(self, changes=None):
        return self.attribute.value == self.desired

    def mismatches(self):
        if self.attribute.value != self.desired:
            m = "{}: {} != {}".format(self.attribute.name,
                                      self.attribute.value, self.desired)
            return m


@not_process_creatable
class Sequence(Device):

    def __init__(self, name, *seq_items):
        # superclass init
        super(Sequence, self).__init__(name)

        # check we have at least one seq item
        assert len(seq_items) > 0, "Expected >1 SeqItems"
        for item in seq_items:
            assert isinstance(item, SeqItem), \
                "Expected SeqItem, got {}".format(item)

        # Make enum
        states = ["Fault", "Idle"]
        for i in range(len(seq_items)):
            states.append('SeqItem{}'.format(i + 1))
        self.SeqState = Enum('SeqState', states + ["Done"])

        # Make a stateMachine
        sm = StateMachine(name + ".stateMachine", self.SeqState.Idle,
                          self.SeqState.Fault)
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

        # Add check when Done for config mismatches
        t(s.Done, e.Changes, do.mismatches, s.Done, s.Idle)

        # Add abort for non-rest states
        non_rest = [x for x in list(s) if x not in self.rest_states()]
        t(non_rest, e.Abort, do.abort, s.Idle)

    def rest_states(self):
        return [self.SeqState.Fault, self.SeqState.Idle, self.SeqState.Done]

    def start(self, params=None):
        assert self.state in self.rest_states(), \
            "Can't start in {} state".format(self.state)
        if params is None:
            params = {}
        self.stateMachine.post(SeqEvent.Start, params=params, t=time.time())

    def abort(self):
        assert self.state not in self.rest_states(), \
            "Can't abort in {} state".format(self.state)
        self.stateMachine.post(SeqEvent.Abort)

    def do_start(self, params, t):
        # store user params
        self.params = params
        self.t = t
        # start first seq item
        next_state = self.SeqState.SeqItem1
        seq_item = self.seq_items[next_state]
        self._start_item(seq_item)
        return next_state, seq_item.name

    def _start_item(self, seq_item):
        is_done = seq_item.start(self.params, self.t)
        if is_done:
            for _ in range(len(self.stateMachine.inq)):
                self.stateMachine.inq.Wait()
            self.stateMachine.post(SeqEvent.Changes, is_done=True)

    def on_change(self, value, changes):
        self.stateMachine.post(SeqEvent.Changes, changes=changes)

    def do_check(self, changes=None, is_done=False):
        if not is_done:
            is_done = self.seq_items[self.state].done(changes)
        if is_done:
            # Done with this item, move on to the next
            next_state = list(self.SeqState)[self.state.value]
            if next_state == self.SeqState.Done:
                # Done
                return next_state, "Done"
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
            mismatch = seq_item.mismatches()
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
