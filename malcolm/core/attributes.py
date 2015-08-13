from collections import OrderedDict
from attribute import Attribute


class Attributes(OrderedDict):
    """Container for a number of attributes"""

    def __init__(self, **attributes):
        super(Attributes, self).__init__()
        self.add_attributes(**attributes)

    def __getattr__(self, attr):
        # Need this horrible line as OrderedDict expects an
        # AttributeError if self.__root doesn't exist
        if attr in ['_OrderedDict__root']:
            raise AttributeError
        return self[attr]

    def __setattr__(self, attr, value):
        if attr in self:
            self[attr] = value
        else:
            super(Attributes, self).__setattr__(attr, value)

    def update(self, attr, value, alarm=None, timeStamp=None):
        self[attr].update(value, alarm, timeStamp)

    def add_attributes(self, **attributes):
        for name, attribute in sorted(attributes.items()):
            assert isinstance(attribute, Attribute), \
                "Needed an attribute, {} is a {}".format(name, attribute)
            self[name] = attribute
            attribute.name = name
