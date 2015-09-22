from cothread.pv import PV
from cothread.catools import FORMAT_TIME

from .attribute import Attribute
from .alarm import AlarmSeverity, AlarmStatus, Alarm
from .base import weak_method


class PVAttribute(Attribute):

    def __init__(self, pv, typ, descriptor):
        super(PVAttribute, self).__init__(typ, descriptor)
        self.pv = PV(pv, on_update=weak_method(self.on_update),
                     format=FORMAT_TIME)

    def on_update(self, value):
        severity = list(AlarmSeverity)[value.severity]
        status = list(AlarmStatus)[value.status]
        alarm = Alarm(severity, status, message="")
        super(PVAttribute, self).update(value, value.timestamp, alarm)

    def update(self, value, alarm=None, timeStamp=None):
        assert alarm is None, "Can't set alarm on a PVAttribute"
        assert timeStamp is None, "Can't set timeStamp on a PVAttribute"
        self.pv.caput(value)
