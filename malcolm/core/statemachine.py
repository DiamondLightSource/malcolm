import functools
import time
import weakref

from .loop import HasLoops, EventLoop
from .listener import HasListeners
from .base import weak_method
from .subscription import ServerSubscription


class HasStateMachine(HasLoops, HasListeners):
    _stateMachine_prefix = "stateMachine."
    _endpoints = "stateMachine".split(",")

    def add_stateMachine(self, stateMachine):
        self.stateMachine = stateMachine
        self.add_loop(stateMachine)
        stateMachine.notify_listeners = functools.partial(
            weak_method(self.notify_listeners),
            prefix=self._stateMachine_prefix)

    def wait_until(self, states, timeout=None):
        """Listen to the state machine status updates until we transition to
        one of the given states"""
        # Get a list of states we should wait until
        try:
            states = list(states)
        except TypeError:
            states = [states]
        # Construct object that will wait for us
        sub = ServerSubscription(self, self._stateMachine_prefix + "state")
        for state in states:
            sub.add_event_handler(state, sub.loop_stop)
        # Add the waiter to our list of loops, and listen for state
        self.add_loop(sub)
        # Wait for the state to match
        sub.loop_wait(timeout=timeout)


class StateMachine(EventLoop):
    """Create a state machine object that will listen for events on its
    input queue, and call the respective transition function

    :param name: A human readable name for this state machine
    """
    _endpoints = "message,state,states,timeStamp".split(",")

    def __init__(self, name, initial_state, error_state=None, timeout=None):
        super(StateMachine, self).__init__(name, timeout)
        # store initial, error and current states
        self.initial_state = initial_state
        self.states = [initial_state]
        if error_state is None:
            error_state = initial_state
        elif error_state not in self.states:
            self.states.append(error_state)
        self.error_state = error_state
        self.state = initial_state
        self.message = ""
        self.timeStamp = None

    def get_next_event(self, timeout=None):
        """Return the next event to be processed. Co-operatively block and
        allow interruption from stop()
        Returns (event, args, kwargs)"""
        event, args, kwargs = self.inq.Wait(timeout=timeout)
        return ((self.state, event), args, kwargs)

    def update(self, state=None, message=None, timeStamp=None):
        changes = {}
        if state is not None and state != self.state:
            assert state in self.states, \
                "State {} should be one of {}".format(state, self.states)
            changes.update(state=state)
            self.state = state
        if message is not None and message != self.message:
            message = str(message)
            changes.update(message=message)
            self.message = message
        timeStamp = timeStamp or time.time()
        if timeStamp != self.timeStamp:
            changes.update(timeStamp=timeStamp)
            self.timeStamp = timeStamp
        # Notify anyone listening
        if hasattr(self, "notify_listeners"):
            self.notify_listeners(changes)

    def make_transition_func(self, transition_func, to_states):
        """Run the transition function"""
        # Transition function can return:
        # - (State, "message") for state change with message
        self = weakref.proxy(self)
        transition_func = weak_method(transition_func)

        def generated_transition_func(*args, **kwargs):
            self.log_debug(
                "Running transition_function {} {} {}"
                .format(transition_func, args, kwargs))
            ret = transition_func(*args, **kwargs)
            self.log_debug("Return is {}".format(ret))
            assert type(ret) in (tuple, list) and len(ret) == 2, \
                "Needed tuple or list of length 2 from {}, got {}" \
                .format(transition_func.__name__, ret)
            state, message = ret
            assert message is None or type(message) == str, \
                "Message should be string or None, got {}".format(message)
            if state is None:
                if message is None:
                    # No change
                    return
                state = self.state
            assert state in to_states, "State {} is not one of {}".format(
                state, to_states)
            self.update(state, message)

        return generated_transition_func

    def do_error(self, error):
        """Handle an error"""
        return (self.error_state, str(error))

    def error_handler(self, error, *args, **kwargs):
        """Called if an event handler raises an error"""
        super(StateMachine, self).error_handler(error, *args, **kwargs)
        try:
            state, message = self.do_error(error)
        except Exception as error:
            # User supplied do_error function failed
            state, message = StateMachine.do_error(self, error)
        self.update(state, message)

    def transition(self, from_state, event, transition_func, *to_states):
        """Add a transition to the table

        :param from_state: The state enum (or list of enums) to transition from
        :param event: The event enum that triggers a transition
        :param transition_func: The function that will be called on trigger. It
            will return a new state enum, or None if there is only one to_state
        :param to_states: The state enum or list of enums that may be
            returned by the transition_func
        """
        # Turn the to_states into a list of states
        to_state_list = []
        for to_state in to_states:
            try:
                to_state_list += list(to_state)
            except TypeError:
                to_state_list.append(to_state)
        # Add them to the list of all states
        for state in to_state_list:
            if state not in self.states:
                self.states.append(state)
        # Turn the from_states into a list of states
        try:
            from_state_list = list(from_state)
        except TypeError:
            from_state_list = [from_state]
        for from_state in from_state_list:
            if (from_state, event) in self.handlers:
                self.log_warning("overwriting state transitions for from_state"
                                 " {}, event {}".format(from_state, event))
            # check transition func exists or single state
            if transition_func is None:
                assert len(to_state_list) == 1, \
                    "Can't have multiple to_states with no transition func"

                # make a transition function that does nothing
                def simple_state_change(*args, **kwargs):
                    weak_method(self.update)(to_state_list[0], "State change")

                handler = simple_state_change
            else:
                handler = self.make_transition_func(transition_func,
                                                    to_state_list)
                functools.update_wrapper(handler, transition_func)
            self.add_event_handler((from_state, event), handler)
