import json
from collections import OrderedDict
import re

import numpy

from malcolm.core.presentation import Presenter


class JsonPresenter(Presenter):

    def __init__(self):
        super(JsonPresenter, self).__init__("JsonPresenter")
        self.camel_re = re.compile("[a-z]([a-z0-9]*)([A-Z]+[a-z0-9]*)*$")

    def normalize(self, d):
        # Check camelcase in keys
        for key in d.keys():
            match = self.camel_re.match(key)
            if not match:
                self.log_warning("Key {} isn't camelCase".format(key))
            #    print match.group()
        if "timeStamp" in d:
            timeStamp = d["timeStamp"]
            ts = OrderedDict(secondsPastEpoch=int(timeStamp))
            ts.update(nanoseconds=int(timeStamp % 1 / 1e-9))
            ts.update(userTag=0)
            d["timeStamp"] = ts
        for d2 in d.values():
            if hasattr(d2, "values"):
                self.normalize(d2)
        return d

    def serialize_hook(self, o):
        if hasattr(o, "to_dict"):
            d = o.to_dict()
            if hasattr(d, "values"):
                d = self.normalize(d)
            return d
        elif isinstance(o, numpy.number):
            return o.tolist()
        elif isinstance(o, numpy.bool_):
            return bool(o)
        else:
            raise AssertionError("Can't encode {}".format(repr(o)))

    def serialize(self, o):
        s = json.dumps(
            self.normalize(o), default=self.serialize_hook)
        return s

    def deserialize_hook(self, pairs):
        d = OrderedDict(pairs)
        if "timeStamp" in d:
            d["timeStamp"] = d["timeStamp"]["secondsPastEpoch"] + \
                float(d["timeStamp"]["nanoseconds"]) * 1e-9
        return d

    def deserialize(self, s):
        o = json.loads(s, object_pairs_hook=self.deserialize_hook)
        return o
