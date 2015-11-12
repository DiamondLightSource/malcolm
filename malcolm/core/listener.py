from collections import OrderedDict

from .base import Base


class HasListeners(Base):

    def add_listener(self, callback, prefix=""):
        """Add a listener callback function to be called when something
        changes.
        It should have call signature:
          def callback(changes)
        Where changes is a dict of prefix->new value
        """
        # Lazily make listeners dict
        if not hasattr(self, "_listeners"):
            self._listeners = OrderedDict()
        listeners = self._listeners.setdefault(prefix, [])
        assert callback not in listeners, \
            "Callback function {} already in callback list".format(
                callback)
        listeners.append(callback)

    def remove_listener(self, callback, prefix=""):
        """Remove listener callback function"""
        assert prefix in self._listeners, \
            "No listeners for prefix {}".format(prefix)
        listeners = self._listeners[prefix]
        assert callback in listeners, \
            "Callback function {} not in {}".format(callback, listeners)
        listeners.remove(callback)

    def get_endpoint(self, ename):
        endpoint = self
        if ename:
            for e in ename.split("."):
                if hasattr(endpoint, "to_dict"):
                    endpoint = endpoint.to_dict()
                assert e in endpoint, "{} not in {}".format(e, endpoint.keys())
                endpoint = endpoint[e]
        return endpoint

    def notify_listeners(self, changes, prefix=""):
        if not hasattr(self, "_listeners") or len(self._listeners) == 0:
            return
        # Add on prefix to changes
        changes = {prefix + k: v for k, v in changes.items()}
        not_uptime = [x for x in changes if not
                      x.startswith("attributes.uptime")]
        if not_uptime:
            self.log_debug("Notifying listeners of {}".format(changes))
        for prefix, listeners in self._listeners.items():
            filt_changes = {}
            for cname, cvalue in changes.items():
                if cname.startswith(prefix):
                    filt_changes[cname[len(prefix):].lstrip(".")] = cvalue
            if filt_changes:
                # If we have a dict with a single entry "", we are monitoring
                # a single item, not a structure, so make it "."
                if filt_changes.keys() == [""]:
                    filt_changes["."] = filt_changes.pop("")
                value = self.get_endpoint(prefix)
                for callback in listeners:
                    cname = getattr(callback, "__name__", "callback")
                    # self.log_error("Calling {}({}, {})"
                    #                .format(cname, value, filt_changes))
                    try:
                        callback(value, filt_changes)
                    except:
                        self.log_exception(
                            "{}({}) raised".format(cname, filt_changes))
