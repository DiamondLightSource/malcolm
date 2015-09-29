from abc import ABCMeta
import logging
import weakref
import functools
from collections import OrderedDict


class Base(object):
    __metaclass__ = ABCMeta
    _endpoints = ""

    def __init__(self, name):
        super(Base, self).__init__()
        self.name = name

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name
        lname = "{}({})".format(type(self).__name__, self._name)
        self._log = logging.getLogger(lname)
        self.log_debug = self._log.debug
        self.log_warning = self._log.warning
        self.log_info = self._log.info
        self.log_error = self._log.error
        self.log_exception = self._log.exception

    def to_dict(self, **overrides):
        d = OrderedDict()
        for endpoint in self._endpoints:
            if endpoint in overrides:
                val = overrides[endpoint]
            else:
                val = getattr(self, endpoint)
            if val not in ([], {}, (), None):
                d[endpoint] = val
        return d


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
