from .device import Device
from .loop import ILoop, LState
from .serialize import SType


class ValueQueue(ILoop):

    def loop_run(self):
        """Start the event loop running"""
        super(ValueQueue, self).loop_run()
        self.inq = self.cothread.EventQueue()
        self.finished = self.cothread.Pulse()

    def post(self, event, **kwargs):
        self.inq.Signal((event, kwargs))

    def loop_wait(self):
        """Wait for a loop to finish"""
        if self.loop_state() != LState.Stopped:
            self.finished.Wait()

    def loop_confirm_stopped(self):
        super(ValueQueue, self).loop_confirm_stopped()
        self.finished.Signal()

    def loop_stop(self):
        """Signal the event loop to stop running and wait for it to finish"""
        super(ValueQueue, self).loop_stop()
        self.inq.close()


class DeviceClient(Device):

    def __init__(self, name, process, timeout=None):
        super(DeviceClient, self).__init__(name, process, timeout)
        # Assume process can make us a sock for the named device
        self.sock = process.get_sock(name)

    def do_call(self, method, **kwargs):
        # Setup a ValueQueue that will handle the returns
        endpoint = ".".join(self.name, method)
        vq = ValueQueue("Call({})".format(endpoint))
        self.add_loop(vq)
        self.sock.request(
            vq.post, SType.Call, endpoint=endpoint, args=kwargs)
        event, d = vq.inq.Wait()
        assert event == SType.Return
        ret = d["value"]
        vq.loop_stop()
        vq.loop_confirm_stopped()
        self.remove_loop(vq)
        return ret

