import abc
from collections import OrderedDict

from enum import Enum

from .base import Base, weak_method


class LState(Enum):
    NotStarted, Running, Stopping, Stopped = range(4)


class ILoop(Base):
    # If this is a function then spawn event loop
    loop_event = None

    # Will be written in by HasLoops
    def loop_remove_from_parent(self, loop):
        pass

    def loop_run(self):
        """Start the event loop running"""
        self.log_debug("Running loop")
        import cothread
        self.cothread = cothread
        self._loop_state = LState.Running
        if self.loop_event:
            # Call unbound function with a weak reference to self so that
            # garbage collector will call __del__ when we finish
            event_loop = weak_method(self.event_loop)
            loop_event = weak_method(self.loop_event)
            self.event_loop_proc = cothread.Spawn(event_loop, loop_event)
            # stack_size=1000000)
        else:
            self.event_loop_proc = cothread.Pulse()

    def event_loop(self, loop_event):
        while True:
            # Try the loop event
            try:
                # Are we stopped?
                if self.loop_state() != LState.Running:
                    self.log_debug("Breaking as loop state not Running")
                    break
                loop_event()
            except (ReferenceError, StopIteration) as e:
                try:
                    self.log_debug("Breaking from {}".format(type(e)))
                except ReferenceError:
                    pass
                break
            except Exception, e:
                self.log_exception("Exception raised processing event")
        try:
            self.loop_confirm_stopped()
        except ReferenceError as e:
            return

    @abc.abstractmethod
    def loop_stop(self):
        """Signal the event loop to stop running"""
        self._loop_state = LState.Stopping
        self.log_debug("Stopping loop")

    def loop_wait(self, timeout=None):
        """Wait for a loop to finish"""
        self.log_debug("Waiting for loop to finish")
        if self.loop_state() != LState.Stopped:
            self.event_loop_proc.Wait(timeout=timeout)
        self.log_debug("Loop finished")

    def loop_state(self):
        """Return a LState"""
        try:
            return self._loop_state
        except:
            return LState.NotStarted

    def loop_confirm_stopped(self):
        """Wait for a loop to finish"""
        self.log_debug("Confirming loop stopped")
        self._loop_state = LState.Stopped
        try:
            self.loop_remove_from_parent(self)
        except ReferenceError:
            self.log_debug("Parent has already been garbage collected")
        if hasattr(self.event_loop_proc, "Signal"):
            self.event_loop_proc.Signal()

    def __del__(self):
        self.log_debug("Garbage collecting loop")
        if LState is None:
            # When run under nosetests, LState is sometimes garbage collected
            # before us, so just return here
            return
        if self.loop_state() == LState.Running:
            try:
                self.loop_stop()
            except ReferenceError:
                self.log_debug("Garbage collecting caught ref error in stop")
            except:
                self.log_exception("Unexpected error during loop_stop")
        if self.loop_state() == LState.Stopping:
            try:
                self.loop_wait()
            except ReferenceError:
                self.log_debug("Garbage collecting caught ref error in wait")
            except:
                self.log_exception("Unexpected error during loop_wait")
        self.log_debug("Loop garbage collected")


class HasLoops(ILoop):

    def add_loop(self, loop):
        # Lazily make loops dict
        assert isinstance(loop, ILoop), \
            "Expected EventLoop, got {}".format(loop)
        if not hasattr(self, "_loops"):
            self._loops = []
        self._loops.append(loop)
        # If after run, then run loop
        if self.loop_state() == LState.Running:
            loop.loop_remove_from_parent = weak_method(self.remove_loop)
            loop.loop_run()

    def remove_loop(self, loop):
        assert loop.loop_state() == LState.Stopped, \
            "Must stop a loop before remove"
        assert loop in self._loops, \
            "{} is not in {}".format(loop.name, [x.name for x in self._loops])
        self._loops.remove(loop)

    def loop_run(self):
        """Start the event loop running"""
        super(HasLoops, self).loop_run()
        for loop in getattr(self, "_loops", []):
            loop.loop_remove_from_parent = weak_method(self.remove_loop)
            loop.loop_run()

    def loop_stop(self):
        """Signal the event loop to stop running and wait for it to finish"""
        super(HasLoops, self).loop_stop()
        loops = reversed(getattr(self, "_loops", []))
        for loop in loops:
            loop.loop_stop()

    def loop_wait(self, timeout=None):
        """Wait for a loop to finish"""
        # Do in reverse so sockets (first) can send anything the other loops
        # produce
        self.log_debug("Waiting for loop to finish")
        loops = reversed(getattr(self, "_loops", []))
        for loop in loops:
            loop.loop_wait(timeout=timeout)
            # It might remove itself, if it doesn't then remove it
            if loop in self._loops:
                self.remove_loop(loop)
        loops = None
        self.loop_confirm_stopped()


class EventLoop(ILoop):

    def __init__(self, name, timeout=None):
        super(EventLoop, self).__init__(name)
        self.timeout = timeout
        self.handlers = OrderedDict()

    def post(self, event, *args, **kwargs):
        """Post a event to the input queue that the state machine can deal
        with

        :param event: a event enum
        """
        self.inq.Signal((event, args, kwargs))

    def get_next_event(self, timeout=None):
        """Return the next event to be processed. Co-operatively block and
        allow interruption from stop()
        Returns (event, args, kwargs)"""
        ret = self.inq.Wait(timeout)
        return ret

    def add_event_handler(self, event, function):
        assert callable(function), \
            "function {0} is not callable".format(function)
        # Store the unbound function, we will call it with a weakref to self
        # later so we can be garbage collected
        self.handlers[event] = weak_method(function)

    def loop_event(self):
        event, args, kwargs = weak_method(
            self.get_next_event)(timeout=self.timeout)
        # self.log_debug("Got event {} {} {}".format(event, args, kwargs))
        if event in self.handlers:
            function = self.handlers[event]
        elif None in self.handlers:
            function = self.handlers[None]
        else:
            self.log_info(
                "No handler functions for event {}".format(event))
            return
        # fname = getattr(function, "__name__", str(function))
        # self.log_debug("Running function {}".format(fname))
        try:
            function(*args, **kwargs)
        except ReferenceError:
            raise
        except Exception, error:
            self.error_handler(error, *args, **kwargs)

    def error_handler(self, error, *args, **kwargs):
        """Called if an event handler raises an error"""
        extras = []
        if args:
            extras.append("args={}".format(args))
        if kwargs:
            extras.append("kwargs={}".format(kwargs))
        if extras:
            msg = "Handler (called with {}) raised error: {}".format(
                ", ".join(extras), error)
        else:
            msg = "Handler raised error: {}".format(error)
        self.log_exception(msg)

    def loop_run(self):
        """Run the event loop in a new cothread"""
        super(EventLoop, self).loop_run()
        self.inq = self.cothread.EventQueue()

    def loop_stop(self):
        """Signal the the underlying event loop should close"""
        super(EventLoop, self).loop_stop()
        self.inq.close()


class TimerLoop(ILoop):

    def __init__(self, name, callback, timeout, retrigger=True):
        super(TimerLoop, self).__init__(name)
        self.timeout = timeout
        self.callback = callback
        self.retrigger = retrigger

    def on_trigger(self):
        if not self.retrigger:
            self.loop_stop()
        self.callback()

    def loop_run(self):
        """Start the event loop running"""
        super(TimerLoop, self).loop_run()
        self.timer = self.cothread.Timer(self.timeout,
                                         self.callback,
                                         retrigger=self.retrigger)

    def loop_stop(self):
        """Signal the event loop to stop running and wait for it to finish"""
        super(TimerLoop, self).loop_stop()
        self.timer.cancel()
        self.loop_confirm_stopped()
