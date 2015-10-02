from .attribute import Attribute
from .alarm import AlarmSeverity, AlarmStatus, Alarm
from .base import weak_method
from .loop import ILoop


class PVAttribute(Attribute, ILoop):

    def __init__(self, pv, typ, descriptor, rbv=None, rbv_suff=None,
                 put_callback=True):
        super(PVAttribute, self).__init__(typ, descriptor)
        if rbv is not None or rbv_suff is not None:
            assert rbv is None or rbv_suff is None, \
                "Can't specify both rbv and rbv_suff"
            if rbv is None:
                rbv = pv + rbv_suff
        self.pv = pv
        self.rbv = rbv
        self.put_callback = put_callback

    def loop_run(self):
        super(PVAttribute, self).loop_run()
        self.put_callbacks = 0
        self.monitor_updates = 0
        self.monitor_fired = self.cothread.Pulse()
        self.make_pvs()

    def make_pvs(self):
        from cothread.pv import PV
        from cothread.catools import FORMAT_TIME
        if self.rbv is not None:
            self.pv = PV(self.pv)
            self.rbv = PV(self.rbv, on_update=weak_method(self.on_update),
                          format=FORMAT_TIME)
        else:
            self.pv = PV(self.pv, on_update=weak_method(self.on_update),
                         format=FORMAT_TIME)
            self.rbv = self.pv

    def on_update(self, pv, pv_timestamp=True):
        "Called when camonitor fires"
        if self.put_callbacks > 0:
            self.monitor_updates += 1
        else:
            value = pv.get()
            self.log_debug("Camonitor update {}".format(repr(value)))
            severity = list(AlarmSeverity)[value.severity]
            status = list(AlarmStatus)[value.status]
            alarm = Alarm(severity, status, message="")
            if pv_timestamp:
                timestamp = value.timestamp
            else:
                timestamp = None
            super(PVAttribute, self).update(value, alarm, timestamp)
            self.monitor_fired.Signal()

    def on_put_callback(self, _=None):
        "Called when a caput callback fires"
        self.log_debug("Got put callback")
        assert self.put_callbacks > 0, \
            "Got a caput callback while {} active".format(self.put_callbacks)
        self.put_callbacks -= 1
        # If we are the last put callback to return
        if self.put_callbacks == 0:
            # If there was a monitor update while we updated, use this
            if self.monitor_updates > 0:
                self.monitor_updates = 0
                self.on_update(self.rbv, pv_timestamp=False)
            # Otherwise wait up to 0.5s for a monitor to come in
            else:
                try:
                    self.log_debug("Wait monitor update")
                    self.monitor_fired.Wait(0.5)
                except self.cothread.cothread.Timedout:
                    self.log_debug("Force monitor update")
                    # if no monitor, force an update
                    self.on_update(self.rbv, pv_timestamp=False)

    def update(self, value, alarm=None, timeStamp=None):
        assert alarm is None, "Can't set alarm on a PVAttribute"
        assert timeStamp is None, "Can't set timeStamp on a PVAttribute"
        self.log_debug("Caput {} {}".format(repr(value), self.pv))
        if self.put_callback:
            self.put_callbacks += 1
            self.pv.caput(value, callback=self.on_put_callback, timeout=None)
        else:
            self.pv.caput(value, callback=None, timeout=None)
