from .attribute import Attribute
from .alarm import AlarmSeverity, AlarmStatus, Alarm
from .base import weak_method
from .loop import ILoop
from malcolm.core.vtype import VBool


class PvAttribute(Attribute, ILoop):

    def __init__(self, pv, typ, descriptor, rbv=None, rbv_suff=None,
                 put_callback=True, long_string=False):
        super(PvAttribute, self).__init__(typ, descriptor)
        if rbv is not None or rbv_suff is not None:
            assert rbv is None or rbv_suff is None, \
                "Can't specify both rbv and rbv_suff"
            if rbv is None:
                rbv = pv + rbv_suff
        self.pv = pv
        self.rbv = rbv
        self.long_string = long_string
        self.put_callback = put_callback

    def loop_run(self):
        super(PvAttribute, self).loop_run()
        self.put_callbacks = 0
        self.monitor_updates = 0
        self.monitor_fired = self.cothread.Pulse()
        self.make_pvs()

    def make_pvs(self):
        # TODO: use vtype to infer datatype
        from cothread.pv import PV
        from cothread.catools import FORMAT_TIME, DBR_CHAR_STR
        if self.long_string:
            datatype = DBR_CHAR_STR
        else:
            datatype = None
        if self.rbv is not None:
            self.pv = PV(self.pv, datatype=datatype)
            self.rbv = PV(self.rbv, on_update=weak_method(self.on_update),
                          format=FORMAT_TIME, datatype=datatype)
        else:
            self.pv = PV(self.pv, on_update=weak_method(self.on_update),
                         format=FORMAT_TIME, datatype=datatype)
            self.rbv = self.pv

    def on_update(self, pv, pv_timestamp=True, caget=False):
        "Called when camonitor fires"
        if self.put_callbacks == 1:
            self.monitor_updates += 1
        else:
            if caget:
                value = pv.caget()
            else:
                value = pv.get()
            self.log_debug("Camonitor update {}".format(repr(value)))
            if hasattr(value, "severity") and hasattr(value, "status"):
                severity = list(AlarmSeverity)[value.severity]
                status = list(AlarmStatus)[value.status]
                alarm = Alarm(severity, status, message="")
            else:
                alarm = None
            if pv_timestamp and hasattr(value, "timestamp"):
                timestamp = value.timestamp
            else:
                timestamp = None
            super(PvAttribute, self).update(value, alarm, timestamp)
            self.monitor_fired.Signal()

    def on_put_callback(self, _=None):
        "Called when a caput callback fires"
        self.log_debug("{}: Got put callback".format(self.pv.name))
        assert self.put_callbacks == 1, \
            "Got a caput callback while {} active".format(self.put_callbacks)
        self.put_callbacks = 0
        # If there was a monitor update while we updated, use this
        if self.monitor_updates > 0:
            self.monitor_updates = 0
            self.on_update(self.rbv, pv_timestamp=False)
        # Otherwise spawn a caget
        else:
            self.log_debug("Do caget")
            self.cothread.Spawn(self.on_update, self.rbv, caget=True,
                                pv_timestamp=False)

    def update(self, value, alarm=None, timeStamp=None):
        assert alarm is None, "Can't set alarm on a PvAttribute"
        assert timeStamp is None, "Can't set timeStamp on a PvAttribute"
        self.log_debug("caput({}, {})".format(self.pv.name, repr(value)))
        # Convert value for some VTypes
        if isinstance(self.typ, VBool):
            value = bool(value)
        if self.put_callback:
            assert self.put_callbacks == 0, \
                "Cannot run put callback when another is active"
            self.put_callbacks = 1
            self.pv.caput(value, callback=self.on_put_callback, timeout=None)
        else:
            self.pv.caput(value, callback=None, timeout=None)
