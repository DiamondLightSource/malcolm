from enum import Enum

from .serialize import Serializable


class AlarmSeverity(Enum):
    noAlarm, minorAlarm, majorAlarm, invalidAlarm, undefinedAlarm = range(5)


class AlarmStatus(Enum):
    noStatus, deviceStatus, driverStatus, recordStatus, dbStatus, confStatus, \
        undefinedStatus, clientStatus = range(8)


class Alarm(Serializable):
    _endpoints = "severity,status,message".split(",")

    def __init__(self, severity, status, message):
        super(Alarm, self).__init__("Alarm")
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

    def __eq__(self, other):
        if isinstance(other, Alarm):
            equal = self.severity == other.severity
            equal &= self.status == other.status
            equal &= self.message == other.message
            return equal
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)
