from alarm import Alarm
from timeStamp import TimeStamp
from collections import OrderedDict


class Attributes(object):
    """Container for a number of attributes"""

    def __init__(self, **attributes):
        self.attributes = OrderedDict()
        self.add_attributes(**attributes)

    def __setattr__(self, attr, value):
        if attr == "attributes":
            return object.__setattr__(self, attr, value)
        else:
            self.attributes[attr].set_value(value)

    def __getattr__(self, attr):
        if attr == "attributes":
            return object.__getattr__(self, attr)
        else:
            return self.attributes[attr].value

    def set_value(self, attr, value, alarm=None, timeStamp=None):
        self.attributes[attr].set_value(value, alarm, timeStamp)

    def to_dict(self):
        return self.attributes

    def add_attributes(self, **attributes):
        for name, attribute in attributes.items():
            self.attributes[name] = attribute
            attribute.name = name


class Attribute(object):
    """Class representing an attribute"""

    def __init__(self, typ, descriptor, value=None, alarm=None,
                 timeStamp=None, name=None):
        # TODO: add validation here
        self.name = name
        self.typ = typ
        self.descriptor = descriptor
        self.value = value
        self.alarm = alarm
        self.timeStamp = timeStamp
        self.tags = []

    def set_value(self, value, alarm=None, timeStamp=None):
        self.value = value
        self.alarm = alarm or Alarm.ok()
        self.timeStamp = timeStamp or TimeStamp.now()

    def to_dict(self):
        d = OrderedDict(value=self.value)
        d.update(type=self.typ.__name__)
        if self.tags:
            d.update(tags=self.tags)
        d.update(descriptor=self.descriptor)
        if self.alarm is not None:
            d.update(alarm=self.alarm)
        if self.timeStamp is not None:
            d.update(timeStamp=self.timeStamp)
        return d
