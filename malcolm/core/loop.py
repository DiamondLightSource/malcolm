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
        self._stopping = cothread.Pulse()
        #Call unbound function with a weak reference to self so that
        # garbage collector will call __del__ when we finish
        event_loop = weak_method(self.event_loop)     
        if self.loop_event is not None:
            loop_event = weak_method(self.loop_event)
        else:
            loop_event = None
        self.event_loop_proc = cothread.Spawn(event_loop, loop_event)#, stack_size=10000000)

    def event_loop(self, loop_event):
        while True:
            # Try the loop event
            try:
                # Are we stopped?
                if self.loop_state() != LState.Running:
                    self.log_debug("Breaking as loop state not Running")
                    break
                if loop_event is not None:
                    loop_event()
                else:
                    self._stopping.Wait()
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
        self._stopping.Signal()

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

    def loop_exit(self):
        if self.loop_state() == LState.Running:
            self.loop_stop()
        if self.loop_state() == LState.Stopping:
            self.loop_wait()
        
    def __del__(self):
        self.log_debug("Garbage collecting loop")
        if LState is None:
            # When run under nosetests, LState is sometimes garbage collected
            # before us, so just return here
            return        
        try:
            self.loop_exit()
        except ReferenceError:
            self.log_debug("Garbage collecting caught ref error")
        except:
            self.log_exception("Unexpected error during loop_exit")
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
            if loop.loop_state == LState.Running:
                loop.loop_stop()

    def loop_wait(self, timeout=None):
        """Wait for a loop to finish"""
        # Do in reverse so sockets (first) can send anything the other loops
        # produce
        loops = reversed(getattr(self, "_loops", []))
        for loop in loops:
            if loop.loop_state == LState.Stopping:
                loop.loop_wait(timeout=timeout)
                # It might remove itself, if it doesn't then remove it
                if loop in self._loops:
                    self.remove_loop(loop)
        # GC the loops
        loops = None
        # Call the super class to wait for ourselves
        super(HasLoops, self).loop_wait()


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
        try:
            ret = self.inq.Wait(timeout)
        except self.cothread.cothread.Timedout:
            raise StopIteration
        else:
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
        # TODO: this should be called?
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
        self.timer.cancel()
        super(TimerLoop, self).loop_stop()

