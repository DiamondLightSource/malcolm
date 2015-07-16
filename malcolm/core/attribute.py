from alarm import Alarm
from timeStamp import TimeStamp

class Attributes(object):
    """Container for a number of attributes"""

    def __init__(self, attributes):
        self.attributes = {}
        for name, (typ, desc) in attributes.items():
            self.attributes[name] = Attribute(name, typ, desc)

    def __setattr__(self, attr, value):
        if attr == "attributes":
            return object.__setattr__(self, attr, value)
        else:
            self.attributes[attr].value = value

    def __getattr__(self, attr):
        if attr == "attributes":
            return object.__getattr__(self, attr)
        else:
            return self.attributes[attr].value

class Attribute(object):
    """Class representing an attribute"""

    def __init__(self, name, typ, descriptor, alarm=None,
                 timeStamp=None):
        # TODO: add validation here
        self.name = name
        self.typ = typ
        self.value = None
        self.tags = []
        self.descriptor = descriptor
        self.alarm = alarm or Alarm.ok()
        self.timeStamp = timeStamp or TimeStamp.now()



