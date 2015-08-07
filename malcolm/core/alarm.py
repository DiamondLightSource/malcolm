from enum import Enum
from collections import OrderedDict


class AlarmSeverity(Enum):
    noAlarm, minorAlarm, majorAlarm, invalidAlarm, undefinedAlarm = range(5)

    def to_dict(self):
        return self.value


class AlarmStatus(Enum):
    noStatus, deviceStatus, driverStatus, recordStatus, dbStatus, confStatus, \
        undefinedStatus, clientStatus = range(8)

    def to_dict(self):
        return self.value


class Alarm(object):

    def __init__(self, severity, status, message):
        assert severity in AlarmSeverity, \
            "severity {} is not an AlarmSeverity".format(severity)
        self.severity = severity
        assert status in AlarmStatus, \
            "status {} is not an AlarmStatus".format(status)
        self.status = status
        assert type(message) is str, \
            "message {} is not a string".format(message)
        self.message = message

    @classmethod
    def ok(cls):
        return cls(AlarmSeverity.noAlarm, AlarmStatus.noStatus, "No alarm")

    def to_dict(self):
        d = OrderedDict(severity=self.severity)
        d.update(status=self.status)
        d.update(message=self.message)
        return d
