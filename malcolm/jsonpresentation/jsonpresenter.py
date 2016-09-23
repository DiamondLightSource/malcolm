import json
from collections import OrderedDict
import re

import numpy

from malcolm.core.presentation import Presenter
from malcolm.core.vtype import VType, VEnum


class JsonPresenter(Presenter):

    def __init__(self):
        super(JsonPresenter, self).__init__("JsonPresenter")
        self.camel_re = re.compile("[a-z]([a-z0-9]*)([A-Z]+[a-z0-9]*)*$")

    def normalize(self, d):
        for key, value in d.items():
            # Check camelcase in keys
            match = self.camel_re.match(key)
            if not match:
                self.log_debug("Key {} isn't camelCase".format(key))
            # pop None values
            if value is None:
                d.pop(key)
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
        elif isinstance(o, numpy.ndarray):
            assert len(o.shape) == 1, \
                "Expected 1d array, got {}".format(o.shape)
            return o.tolist()
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
        if "name" in d and "version" in d and d["name"].startswith("V"):
            typ = VType.subclasses()[d["name"]]
            if typ == VEnum:
                d = typ(d["labels"])
            else:
                d = typ
        return d

    def deserialize(self, s):
        o = json.loads(s, object_pairs_hook=self.deserialize_hook)
        return o
