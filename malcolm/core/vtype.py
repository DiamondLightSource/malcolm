import abc
import inspect

import numpy
from collections import OrderedDict


class VType(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def validate(self, value):
        """Validate the given value, raising an error if it can't be stored
        in this type without losing information. Return the argument in
        the correct type"""

    def __eq__(self, other):
        return type(self) == type(other)

    @classmethod
    def subclasses(cls):
        """Return list of subclasses"""
        subclasses = OrderedDict()
        for s in cls.__subclasses__():
            for g in s.subclasses().values() + [s]:
                if g.__name__ not in subclasses and not inspect.isabstract(g):
                    subclasses[g.__name__] = g
        return subclasses

    def to_dict(self):
        d = OrderedDict(name=type(self).__name__)
        d.update(version="2")
        return d


class VNumber(VType):

    @abc.abstractproperty
    def numpy_type(self):
        """Return the numpy type for this subclass"""

    def validate(self, value):
        """Check we match the numpy type"""
        # Cast to the numpy datatype
        cast = self.numpy_type()(value)
        # Rely on numpy's equals to tell us if we've lost info
        assert cast == value, \
            "Lost information converting {} to {}".format(value, cast)
        return cast


class VDouble(VNumber):

    def numpy_type(self):
        return numpy.float64


class VFloat(VNumber):

    def numpy_type(self):
        return numpy.float32


class VLong(VNumber):

    def numpy_type(self):
        return numpy.int64


class VInt(VNumber):

    def numpy_type(self):
        return numpy.int32


class VShort(VNumber):

    def numpy_type(self):
        return numpy.int16


class VByte(VNumber):

    def numpy_type(self):
        return numpy.int8


class VBool(VNumber):

    def numpy_type(self):
        return numpy.bool_


class VString(VType):

    def validate(self, value):
        """Check we match the type"""
        cast = str(value)
        return cast


class VEnum(VType):

    def __init__(self, labels):
        self.labels = tuple(labels)

    def validate(self, value):
        assert value in self.labels, \
            "{} should be one of {}".format(value, self.labels)
        return value

    def to_dict(self):
        d = super(VEnum, self).to_dict()
        d.update(labels=self.labels)
        return d

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        else:
            return set(self.labels) == set(other.labels)


class VStringArray(VType):

    def validate(self, value):
        """Check we match the type"""
        assert hasattr(value, "__iter__"), \
            "Expected iterable, got {}".format(value)
        cast = [str(x) for x in value]
        return cast
