import abc
import collections

from .base import Base
from collections import OrderedDict


class SeqItem(Base):

    @abc.abstractmethod
    def start(self, value_transitions):
        """Called once when sequence item is entered, return True if item is
        done"""

    def done(self, value, changes):
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

    def always_set(self, always):
        assert isinstance(always, (tuple, list)), \
            "Expected tuple or list, got {}".format(always)
        self.always = always
        return self

    def start(self, value_transitions):
        self.match_attrs = {}
        for attr, value in self.seq_params.items():
            # If value is None, nothing to do
            if value is None:
                continue
            # Check if we should always set this attribute
            always = hasattr(self, "always") and attr in self.always
            # If always or if value doesn't match
            if always or not self.attributes[attr].value_equal(value):
                self.match_attrs[attr] = False
                try:
                    self.attributes[attr].update(value)
                except:
                    self.log_exception("Failed to set {} to {}"
                                       .format(attr, value))
                    raise

        # Return if we're done
        is_done = len(self.match_attrs) == 0
        return is_done

    def done(self, value, changes):
        prefixes = set(x.split(".")[0] for x in changes)
        assert len(prefixes) == 1, \
            "Only expected one attribute to change at once, got {}" \
            .format(prefixes)
        attr = prefixes.pop()
        if attr in self.match_attrs and \
                self.attributes[attr].value_equal(self.seq_params[attr]):
            self.log_debug("{} now matches".format(attr))
            self.match_attrs[attr] = True
        is_done = all(self.match_attrs.values())
        if not is_done:
            self.log_debug("Still waiting for {}".format(
                [n for n, v in self.match_attrs.items() if not v]))
        return is_done

    def mismatches(self):
        mismatches = []
        for attr, expected in sorted(self.seq_params.items()):
            actual = self.attributes[attr].value
            if not self.attributes[attr].value_equal(expected):
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

    def start(self, value_transitions):
        self.func(**self.params)
        return True


class SeqTransitionItem(SeqItem):

    def __init__(self, desc, obs, desired, rest=None):
        # name is desc
        super(SeqTransitionItem, self).__init__(desc)
        # These could be mock objects, so better only allow lists or tuples
        if isinstance(obs, (tuple, list)):
            self.obs = list(obs)
        else:
            self.obs = [obs]
        # These are states so can do this
        try:
            self.desired = list(desired)
        except:
            self.desired = [desired]
        if rest is None:
            self.rest = self.desired
        else:
            self.rest = rest
            for desired in self.desired:
                assert desired in rest, \
                    "{} should be in {}".format(desired, rest)

    def start(self, value_transitions):
        # Check whether we have transitioned to this state since seq began
        self.obs_todo = self.obs[:]
        self.transitions = value_transitions
        return self.done(None, None)

    def done(self, value, changes):
        for ob in self.obs_todo[:]:
            # Check if we are now done
            transitions = self.transitions.get(ob, None)
            while transitions:
                changes = transitions.popleft()
                if "state" in changes:
                    actual = changes["state"]
                elif "value" in changes:
                    actual = changes["value"]
                else:
                    continue
                if actual in self.rest:
                    assert actual in self.desired, \
                        "{}: Expected {}, got {}" \
                        .format(ob.name, self.desired, actual)
                    self.obs_todo.remove(ob)
                    break
        if self.obs_todo:
            names = [ob.name for ob in self.obs_todo]
            self.log_debug("Still waiting for {}".format(names))
            return False
        else:
            self.log_debug("All done")
            return True

    def mismatches(self):
        mismatches = []
        for ob in self.obs:
            if hasattr(ob, "state"):
                actual = ob.state
            else:
                actual = ob.value
            if actual not in self.desired:
                mismatches.append("{}: {} not in {}".format(
                    ob.name, actual, self.desired))
        if mismatches:
            return ", ".join(mismatches)


class Sequence(Base):

    def __init__(self, name, *seq_items):
        # superclass init
        super(Sequence, self).__init__(name)

        # check we have at least one seq item
        assert len(seq_items) > 0, "Expected >1 SeqItems"
        for item in seq_items:
            assert isinstance(item, SeqItem), \
                "Expected SeqItem, got {}".format(item)
        self.seq_items = seq_items
        self.running = False

    def start(self):
        assert not self.running, "Sequence already running"
        self.running = True
        self.current_item = 0
        self.value_transitions = {}
        self._start_item(self.current_item)
        return self.item_done, self.seq_items[self.current_item].name

    def _start_item(self, current_item):
        self.item_done = self.seq_items[
            current_item].start(self.value_transitions)

    def process(self, value, changes):
        assert self.running, "Sequence not running"
        if value is not None and not isinstance(value, OrderedDict):
            if value not in self.value_transitions:
                self.value_transitions[value] = collections.deque()
            self.value_transitions[value].append(changes)
        if not self.item_done:
            # check if item is done
            self.item_done = self.seq_items[
                self.current_item].done(value, changes)
        if self.item_done:
            # Move onto next item
            if self.current_item == len(self.seq_items) - 1:
                self.running = False
            else:
                self.current_item += 1
                self._start_item(self.current_item)
        msg = self.seq_items[self.current_item].name
        return self.running, self.item_done, msg

    def mismatches(self):
        mismatches = []
        for seq_item in self.seq_items:
            mismatch = seq_item.mismatches()
            if mismatch:
                mismatches.append(mismatch)
        if len(mismatches) != 0:
            return ", ".join(mismatches)

    def abort(self):
        assert self.running, "Sequence not running"
        self.seq_items[self.current_item].abort()
        self.running = False
