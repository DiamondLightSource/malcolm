import time


class TimeStamp(object):

    def __init__(self, secondsPastEpoch, nanoseconds, userTag=0):
        assert type(secondsPastEpoch) is int, \
            "secondsPastEpoch {} is not an int".format(secondsPastEpoch)
        self.secondsPastEpoch = secondsPastEpoch
        assert type(nanoseconds) is int, \
            "nanoseconds {} is not an int".format(nanoseconds)
        self.nanoseconds = nanoseconds
        assert type(userTag) is int, \
            "userTag {} is not an int".format(userTag)
        self.userTag = userTag

    @classmethod
    def now(cls):
        return cls.from_time(time.time())

    @classmethod
    def from_time(cls, secondsPastEpoch):
        assert type(secondsPastEpoch) == float, \
            "secondsPastEpoch {} is not a float".format(secondsPastEpoch)
        return cls(int(secondsPastEpoch), int(secondsPastEpoch % 1 * 1e-9))

    def to_time(self):
        return self.secondsPastEpoch + float(self.nanoseconds) / 1e-9
