from alarm import Alarm
from timeStamp import TimeStamp
from collections import OrderedDict
from malcolm.core.traitsapi import HasTraits, Str, ListStr, Instance, Undefined


class Attribute(HasTraits):
    """Class representing an attribute"""
    name = Str
    tags = ListStr
    descriptor = Str
    alarm = Instance(Alarm)
    timeStamp = Instance(TimeStamp)

    def __init__(self, typ, descriptor, value=None, alarm=None,
                 timeStamp=None, name=None):
        self.add_trait("value", typ(Undefined))
        self.value.update = self.update
        self.typ = typ
        self.descriptor = descriptor
        if name is not None:
            self.name = name
        if value is not None:
            self.value = value
        if alarm is not None:
            self.alarm = alarm
        if timeStamp is not None:
            self.timeStamp = timeStamp

    def update(self, value, alarm=None, timeStamp=None):
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


