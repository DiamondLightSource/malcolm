from collections import OrderedDict
import logging
from enum import Enum
from status import Status
log = logging.getLogger(__name__)


class StateMachine(object):
    """Create a state machine object that will listen for events on its
    input queue, and call the respective transition function

    :param name: A human readable name for this state machine
    """

    def __init__(self, name, initial_state, error_state=None):
        # self.transitions[(from_state, event)] = (transition_f, to_state_list)
        self.transitions = OrderedDict()
        # store initial, error and current states
        self.status = Status(name, initial_state)
        if error_state is None:
            error_state = initial_state
        self.error_state = error_state
        # name for logging
        self.name = name
        # this is what we set the status message variable to at the end
        # of a transition function
        self._status_message = None

    def add_listener(self, callback):
        """Add a listener callback function to be called when we change state.
        It should have call signature:
          def on_transition(state, message, timeStamp)
        """
        self.status.add_listener(callback)

    def remove_listener(self, callback):
        """Remove listener callback function"""
        self.status.remove_listener(callback)

    def post(self, event, *args, **kwargs):
        """Post a event to the input queue that the state machine can deal
        with

        :param event: a event enum
        """
        self.inq.Signal((event, args, kwargs))

    @property
    def state(self):
        return self.status.state

    def status_message(self, message):
        """Set the status message that will be sent when the transition
        function completes"""
        assert self._status_message is None, "Status message has already " \
            "been set to {}".format(self._status_message)
        self._status_message = message

    def event_loop(self):
        """Listen for inputs on input queue and implement state transitions"""
        # input queue for events
        for event, args, kwargs in self.inq:
            # get the transition_func for this state and event
            self._status_message = None
            try:
                transition_func, to_state_list = self.transitions[
                    (self.state, event)]
            except KeyError:
                log.warning("{0}: in state {1} has no transition functions "
                            "registered for event {2}".format(
                                self.name, self.state, event))
                continue
            # If no transition_func and only one to_state return it
            try:
                # new state is the return value
                new_state = transition_func(event, *args, **kwargs)
            except Exception, error:
                # error give a different return value, any allowed
                new_state = self.do_error(event, error)
            else:
                # if no state returned and there is only one possibility then
                # it is implied
                if new_state is None and len(to_state_list) == 1:
                    new_state = to_state_list[0]
                # If state is ok then do a transition
                elif new_state not in to_state_list:
                    self._status_message = \
                        "Returned state {} in response to event {} " \
                        "is not one of the registered states {}" \
                        .format(new_state, event, to_state_list)
                    log.warning(
                        "{}: {}".format(self.name, self._status_message))
                    new_state = self.error_state
            func_name = getattr(transition_func, "__name__", transition_func)
            log.info("{}: event {} caused func {} to be called "
                     "transitioning {} -> {}"
                     .format(self.name, event, func_name, self.state,
                             new_state))
            if self._status_message is None and new_state != self.state:
                self._status_message = "State change"
            self.status.update(self._status_message, new_state)

    def do_error(self, event, error):
        log.error("{}: event {} caused error {} in transition func"
                  .format(self.name, event, repr(error)))
        self._status_message = error.message
        return self.error_state

    def start_event_loop(self):
        """Run the event loop in a new cothread"""
        import cothread
        self.cothread = cothread
        self.inq = cothread.EventQueue()
        log.debug("{0}: start_event_loop called".format(self.name))
        self.event_loop_proc = cothread.Spawn(self.event_loop)

    def transition(self, from_state, event, transition_func, *to_states):
        """Add a transition to the table

        :param from_state: The state enum (or list of enums) to transition from
        :param event: The event enum that triggers a transition
        :param transition_func: The function that will be called on trigger. It
            will return a new state enum, or None if there is only one to_state
        :param to_states: The state enum or list of enums that may be
            returned by the transition_func
        """
        try:
            from_state_list = list(from_state)
        except TypeError:
            from_state_list = [from_state]
        for from_state in from_state_list:
            to_state_list = []
            for to_state in to_states:
                try:
                    to_state_list += list(to_state)
                except TypeError:
                    to_state_list.append(to_state)
            if (from_state, event) in self.transitions:
                log.warning("{0}: overwriting state transitions for "
                            "from_state {1}, event {2}"
                            .format(self.name, from_state, event))
            # check transition func exists or single state
            if transition_func is None:
                assert len(to_state_list) == 1, \
                    "Can't have multiple to_states with no transition func"

                # make a transition function that does nothing
                def do_nothing(event, *args, **kwargs):
                    return None
                transition_func = do_nothing
            else:
                assert callable(transition_func), \
                    "transition_func {0} is not callable".format(
                        transition_func)
            self.transitions[(from_state, event)] = (transition_func,
                                                     to_state_list)

    def wait_for_transition(self, states):
        """Wait until self.state matches one of states

        :param states: The state enum (or list of enums) to wait for
        """
        try:
            states = list(states)
        except TypeError:
            states = [states]
        for state in states:
            assert isinstance(state, Enum)
        done = self.cothread.Pulse()

        def on_transition(state, message, timeStamp):
            if state in states:
                done.Signal()

        self.add_listener(on_transition)
        done.Wait()
        self.remove_listener(on_transition)
        if self.state == self.error_state:
            raise AssertionError(self.status.message)
