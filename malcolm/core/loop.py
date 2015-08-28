import abc
import weakref
from collections import OrderedDict

from enum import Enum

from .base import Base


class LState(Enum):
    NotStarted, Running, Stopping, Stopped = range(4)


def weak_method(method):
    # If a method
    if hasattr(method, "__func__"):
        self = weakref.proxy(method.__self__)
        func = method.__func__

        def f(*args, **kwargs):
            func(self, *args, **kwargs)

        return f
    else:
        # already just a function
        return method


class ILoop(Base):

    @abc.abstractmethod
    def loop_run(self):
        """Start the event loop running"""
        self.log_debug("Running loop")
        import cothread
        self.cothread = cothread
        self._loop_state = LState.Running

    @abc.abstractmethod
    def loop_stop(self):
        """Signal the event loop to stop running and wait for it to finish"""
        self._loop_state = LState.Stopping
        self.log_debug("Stopping loop")

    @abc.abstractmethod
    def loop_wait(self):
        """Wait for a loop to finish"""

    def loop_state(self):
        """Return a LState"""
        try:
            return self._loop_state
        except:
            return LState.NotStarted

    def spawn(self, method, *args, **kwargs):
        # Call unbound function with a weak reference to self so that
        # garbage collector will call __del__ when we finish
        meth = weak_method(method)
        return self.cothread.Spawn(meth, raise_on_wait=True, *args,
                                   **kwargs)

    def loop_confirm_stopped(self):
        """Wait for a loop to finish"""
        self._loop_state = LState.Stopped

    def __del__(self):
        self.log_debug("Garbage collecting loop")
        if self.loop_state() == LState.Running:
            self.loop_stop()
        if self.loop_state() == LState.Stopping:
            try:
                self.loop_wait()
            except ReferenceError:
                pass
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
            loop.loop_run()

    def remove_loop(self, loop):
        assert loop.loop_state() == LState.Stopped, \
            "Must stop a loop before remove"
        self._loops.remove(loop)

    def loop_run(self):
        """Start the event loop running"""
        super(HasLoops, self).loop_run()
        for loop in getattr(self, "_loops", []):
            loop.loop_run()

    def loop_wait(self):
        """Wait for a loop to finish"""
        for loop in getattr(self, "_loops", []):
            loop.loop_wait()
            self.remove_loop(loop)
        self.loop_confirm_stopped()

    def loop_stop(self):
        """Signal the event loop to stop running and wait for it to finish"""
        super(HasLoops, self).loop_stop()
        for loop in getattr(self, "_loops", []):
            loop.loop_stop()


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
        """Return the next event to be processed as a callable. Co-operatively block and
        allow interruption from stop()
        Returns (event, args, kwargs)"""
        return self.inq.Wait(timeout)

    def add_event_handler(self, event, function):
        assert callable(function), \
            "function {0} is not callable".format(function)
        # Store the unbound function, we will call it with a weakref to self
        # later so we can be garbage collected
        self.handlers[event] = weak_method(function)

    def event_loop(self):
        while self.loop_state() == LState.Running:
            try:
                event, args, kwargs = self.get_next_event(timeout=self.timeout)
            except:
                self.log_exception("Exception raised getting next event")
                continue
            self.log_debug("Got event {} {} {}".format(event, args, kwargs))
            if event in self.handlers:
                function = self.handlers[event]
            elif None in self.handlers:
                function = self.handlers[None]
            else:
                self.log_info(
                    "No handler functions for event {}".format(event))
                continue
            self.log_debug("Running function {}".format(function.__name__))
            try:
                function(*args, **kwargs)
            except Exception, error:
                self.error_handler(error, *args, **kwargs)
        self.loop_confirm_stopped()

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
        self.event_loop_proc = self.spawn(self.event_loop)

    def loop_stop(self):
        """Signal the the underlying event loop should close"""
        super(EventLoop, self).loop_stop()
        self.inq.close()

    def loop_wait(self):
        """Wait for the event loop to finish"""
        self.event_loop_proc.Wait(timeout=self.timeout)
