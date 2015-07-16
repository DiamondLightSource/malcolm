from enum import Enum


class AlarmSeverity(Enum):
    noAlarm, minorAlarm, majorAlarm, invalidAlarm, undefinedAlarm = range(5)


class AlarmStatus(Enum):
    noStatus, deviceStatus, driverStatus, recordStatus, dbStatus, confStatus, \
        undefinedStatus, clientStatus = range(8)


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
        return cls(AlarmSeverity.noAlarm, AlarmStatus.noStatus, "")
