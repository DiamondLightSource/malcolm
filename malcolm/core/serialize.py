from collections import OrderedDict

from enum import Enum

from .base import Base


class SType(Enum):
    Call, Get, Subscribe, Unsubscribe, Error, Value, Return = range(7)

    def is_request(self, values=[Call, Get, Subscribe, Unsubscribe]):
        return self.value in values


class Serializable(Base):
    _endpoints = ""

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
