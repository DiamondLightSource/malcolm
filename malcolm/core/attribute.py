from collections import OrderedDict
import time
import functools
import copy

import numpy

from .alarm import Alarm
from .listener import HasListeners
from .base import weak_method, Base
from .vtype import VType, VObject
from .loop import HasLoops, ILoop


class HasAttributes(HasLoops, HasListeners):
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
                for cn, ca in sorted(self.class_attributes.items()):
                    self.add_attribute(cn, copy.copy(ca))
        if not hasattr(self, "_instance_attributes"):
            self._instance_attributes = []
        assert name not in self.attributes, \
            "Name {} already exists as attribute".format(name)
        self.attributes[name] = attribute
        # Set attribute name, this is the only place we should do this
        attribute.name = name
        attribute.notify_listeners = functools.partial(
            weak_method(self.notify_listeners),
            prefix=self._attributes_prefix + name + ".")
        # if this is a loop and we have loops, add it
        if isinstance(attribute, ILoop):
            self.add_loop(attribute)
        # if this is an instance attribute, add it
        if isinstance(attribute, InstanceAttribute):
            self._instance_attributes.append(attribute)
            # if the instance attribute is a sentinal This then replace it
            # with type of self
            # TODO: this is actually wrong if we subclass, but never mind
            if attribute.dcls == This:
                attribute.dcls = type(self)
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
        self.update_type(typ)
        self._descriptor = descriptor
        if tags:
            self._tags = list(tags)
        else:
            self._tags = []
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
        return "<Attribute: {}={}>".format(self.name, repr(self.value))

    def update(self, value, alarm=None, timeStamp=None):
        changes = {}
        # Assert type
        if value is not None:
            value = self.typ.validate(value)
            if self.value is None:
                equal = False
            else:
                equal = self.typ.value_equal(value, self.value)
            if not equal:
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

    def update_type(self, typ):
        old_typ = getattr(self, "_typ", None)
        if isinstance(typ, VType):
            self._typ = typ
        elif typ in VType.subclasses().values():
            self._typ = typ()
        else:
            raise AssertionError("Expected subclass or instance of {}, got {}"
                                 .format(VType.subclasses().keys(), typ))
        if self._typ != old_typ:
            # Notify anyone listening
            if hasattr(self, "notify_listeners"):
                self.notify_listeners(dict(type=self._typ))

    def to_dict(self, **kwargs):
        return super(Attribute, self).to_dict(type=self.typ, **kwargs)


class This(object):
    # Sentinel class to allow us to refer to ourselves in class attributes
    pass


class InstanceAttribute(Attribute):

    def __init__(self, dcls, descriptor, value=None, alarm=None,
                 timeStamp=None, name=None, tags=None):
        super(InstanceAttribute, self).__init__(
            VObject, descriptor, value=value, alarm=alarm,
            timeStamp=timeStamp, name=name, tags=tags)
        self.dcls = dcls

    def to_dict(self):
        value = self.value
        if value is not None:
            value = value.name
        return super(InstanceAttribute, self).to_dict(value=value)
