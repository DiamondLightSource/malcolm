from abc import ABCMeta
import logging


class Base(object):
    __metaclass__ = ABCMeta

    def __init__(self, name):
        self._name = name
        self._log = logging.getLogger(self._name)
        self.log_debug = self._log.debug
        self.log_warning = self._log.warning
        self.log_info = self._log.warning
        self.log_error = self._log.error
        self.log_exception = self._log.exception

    @property
    def name(self):
        return self._name
