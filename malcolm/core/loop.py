import abc
from collections import OrderedDict

from enum import Enum

from .base import Base, weak_method


class LState(Enum):
    NotStarted, Running, Stopping, Stopped = range(4)


class ILoop(Base):
    # Will be written in by HasLoops
    loop_remove_from_parent = None

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
        if self.loop_remove_from_parent:
            self.loop_remove_from_parent(self)

    def __del__(self):
        self.log_debug("Garbage collecting loop")
        if self.loop_state() == LState.Running:
            try:
                self.loop_stop()
            except ReferenceError:
                self.log_debug("Garbage collecting caught ref error in stop")
        if self.loop_state() == LState.Stopping:
            try:
                self.loop_wait()
            except ReferenceError:
                self.log_debug("Garbage collecting caught ref error in wait")
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
            loop.loop_remove_from_parent = weak_method(self.remove_loop)
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

    def event_loop(self):
        while True:
            try:
                event, args, kwargs = self.get_next_event(timeout=self.timeout)
            except StopIteration:
                self.log_debug("Event loop stopped by StopIteration")
                break
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
            except ReferenceError:
                self.log_debug("Event loop stopped by ReferenceError")
                break
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


class TimerLoop(ILoop):

    def __init__(self, name, callback, timeout):
        super(EventLoop, self).__init__(name)
        self.timeout = timeout
        self.finished = self.cothread.Pulse()
        self.callback = callback

    def loop_run(self):
        """Start the event loop running"""
        super(TimerLoop, self).loop_run()
        self.timer = self.cothread.Timer(self.timeout,
                                         self.callback,
                                         retrigger=True)

    def loop_stop(self):
        """Signal the event loop to stop running and wait for it to finish"""
        super(TimerLoop, self).loop_stop()
        self.timer.cancel()
        self.loop_confirm_stopped()

    def loop_confirm_stopped(self):
        super(TimerLoop, self).loop_confirm_stopped()
        self.finished.Signal()

    def loop_wait(self):
        """Wait for a loop to finish"""
        if self.loop_state() != LState.Stopped:
            self.finished.Wait()
