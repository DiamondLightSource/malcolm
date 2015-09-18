import json
from collections import OrderedDict

from malcolm.core.presentation import Presenter


class JsonPresenter(Presenter):

    def __init__(self):
        super(JsonPresenter, self).__init__("JsonPresenter")

    def serialize_timestamps(self, d):
        if "timeStamp" in d:
            timeStamp = d["timeStamp"]
            ts = OrderedDict(secondsPastEpoch=int(timeStamp))
            ts.update(nanoseconds=int(timeStamp % 1 / 1e-9))
            ts.update(userTag=0)
            d["timeStamp"] = ts
        for d2 in d.values():
            if hasattr(d2, "values"):
                self.serialize_timestamps(d2)
        return d

    def serialize_hook(self, o):
        if hasattr(o, "to_dict"):
            d = o.to_dict()
            if hasattr(d, "values"):
                d = self.serialize_timestamps(d)
            return d
        else:
            return o

    def serialize(self, o):
        s = json.dumps(
            self.serialize_timestamps(o), default=self.serialize_hook)
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
