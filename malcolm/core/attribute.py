from collections import OrderedDict
import time
import functools

from .alarm import Alarm
from .listener import HasListeners
from .base import weak_method, Base


class HasAttributes(HasListeners):
    """Mixin that allows Attribute objects to be stored in a class"""
    _attributes_prefix = "attributes."

    def add_attributes(self, **attributes):
        for name, attribute in sorted(attributes.items()):
            self.add_attribute(name, attribute)

    def add_attribute(self, name, attribute):
        # Lazily make attributes dict
        if not hasattr(self, "attributes"):
            self.attributes = OrderedDict()
            if hasattr(self, "class_attributes"):
                self.add_attributes(**self.class_attributes)
        assert name not in self.attributes, \
            "Name {} already exists as attribute".format(name)
        self.attributes[name] = attribute
        attribute._name = name
        attribute.notify_listeners = functools.partial(
            weak_method(self.notify_listeners),
            prefix=self._attributes_prefix + name + ".")
        return attribute

    def __getattr__(self, attr):
        """If we haven't defined a class attribute, then get its value from
        the self.attributes object"""
        if hasattr(self, "attributes") and attr in self.attributes:
            return self.attributes[attr].value
        else:
            raise AttributeError(
                "Object '{}' has no attribute '{}'"
                .format(object.__getattribute__(self, "_name"),  attr))

    def __setattr__(self, attr, value):
        """If we have an attribute, then set it, otherwise set it as a local
        variable"""
        try:
            self.attributes[attr].update(value)
        except (AttributeError, KeyError) as _:
            return object.__setattr__(self, attr, value)


class Attribute(Base):
    """Class representing an attribute"""
    _endpoints = "value,type,tags,descriptor,alarm,timeStamp".split(",")

    def __init__(self, typ, descriptor, value=None, alarm=None,
                 timeStamp=None, name=None, tags=None):
        super(Attribute, self).__init__(name)
        # TODO: add validation here
        self._typ = typ
        self._descriptor = descriptor
        if tags:
            self._tags = tuple(tags)
        else:
            self._tags = ()
        self._value = value
        self._alarm = alarm
        self._timeStamp = timeStamp

    @property
    def typ(self):
        return self._typ

    @property
    def descriptor(self):
        return self._descriptor

    @property
    def tags(self):
        return self._tags

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self.update(value)

    @property
    def alarm(self):
        return self._alarm

    @property
    def timeStamp(self):
        return self._timeStamp

    def __repr__(self):
        return "<Attribute: {}>".format(repr(self.value))

    def update(self, value, alarm=None, timeStamp=None):
        changes = {}
        # Assert type
        if value != self.value:
            if type(self.typ) == list:
                assert not isinstance(value, basestring), \
                    "Wanted list, got {}".format(repr(value))
                out_value = []
                for v in value:
                    if type(v) == unicode:
                        v = str(v)
                    assert type(v) in self.typ, \
                        "{} has type {}, wanted {}".format(v, type(v), self.typ)
                    out_value.append(v)
                value = out_value
            else:
                assert type(value) == self.typ, \
                    "{} has type {}, wanted {}".format(value, type(value), self.typ)
            changes.update(value=value)
            self._value = value
        # Check alarm
        assert alarm is None or isinstance(alarm, Alarm), \
            "Expected alarm = Alarm or None, got {}".format(alarm)
        alarm = alarm or Alarm.ok()
        if alarm != self.alarm:
            changes.update(alarm=alarm)
            self._alarm = alarm
        # Check timestamp
        assert timeStamp is None or type(timeStamp) == float, \
            "Expected timeStamp = float or None, got {}".format(timeStamp)
        timeStamp = timeStamp or time.time()
        if timeStamp != self.timeStamp:
            changes.update(timeStamp=timeStamp)
            self._timeStamp = timeStamp
        # Notify anyone listening
        if hasattr(self, "notify_listeners"):
            self.notify_listeners(changes)

    def to_dict(self):
        if type(self.typ) == list:
            typ = [t.__name__ for t in self.typ]
        else:
            typ = self.typ.__name__
        return super(Attribute, self).to_dict(type=typ)
