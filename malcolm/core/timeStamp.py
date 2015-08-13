import time
from collections import OrderedDict
from malcolm.core.traitsapi import HasTraits, ReadOnly


class TimeStamp(HasTraits):
    secondsPastEpoch = ReadOnly
    nanoseconds = ReadOnly
    userTag = ReadOnly

    def __init__(self, secondsPastEpoch, nanoseconds, userTag=0):
        self.secondsPastEpoch = secondsPastEpoch
        self.nanoseconds = nanoseconds
        self.userTag = userTag

    @classmethod
    def now(cls):
        return cls.from_time(time.time())

    @classmethod
    def from_time(cls, secondsPastEpoch):
        assert type(secondsPastEpoch) == float, \
            "secondsPastEpoch {} is not a float".format(secondsPastEpoch)
        return cls(int(secondsPastEpoch), int(secondsPastEpoch % 1 / 1e-9))

    def to_time(self):
        return self.secondsPastEpoch + float(self.nanoseconds) * 1e-9

    def to_dict(self):
        d = OrderedDict(secondsPastEpoch=self.secondsPastEpoch)
        d.update(nanoseconds=self.nanoseconds)
        d.update(userTag=self.userTag)
        return d
