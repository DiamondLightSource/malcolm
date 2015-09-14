from abc import ABCMeta
import logging
import weakref
import functools


class Base(object):
    __metaclass__ = ABCMeta

    def __init__(self, name):
        super(Base, self).__init__()
        self._name = name
        self._log = logging.getLogger(self._name)
        self.log_debug = self._log.debug
        self.log_warning = self._log.warning
        self.log_info = self._log.info
        self.log_error = self._log.error
        self.log_exception = self._log.exception

    @property
    def name(self):
        return self._name


def weak_method(method):
    # If a method
    if hasattr(method, "__func__"):
        self = weakref.proxy(method.__self__)
        func = method.__func__

        @functools.wraps(func)
        def f(*args, **kwargs):
            return func(self, *args, **kwargs)

        return f
    else:
        # already just a function
        return method
