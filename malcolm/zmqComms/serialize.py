import json

TYPES = ["call", "get", "error", "return", "ready"]


class CustomSerializer(json.JSONEncoder):

    def default(self, o):
        if hasattr(o, "to_dict"):
            return o.to_dict()
        else:
            return super(CustomSerializer, self).default(o)

serializer = CustomSerializer()


def serialize_call(device, method, **args):
    d = dict(type="call", device=device, method=method)
    if args:
        d["args"] = args
    return serializer.encode(d)


def serialize_get(device, param=None):
    d = dict(type="get", device=device)
    if param:
        d["param"] = param
    return serializer.encode(d)


def serialize_error(e):
    d = dict(type="error", name=type(e).__name__, message=e.message)
    return serializer.encode(d)


def serialize_return(ret):
    d = dict(type="return")
    if ret is not None:
        d["val"] = ret
    return serializer.encode(d)


def serialize_ready(device, pubsocket):
    d = dict(type="ready", device=device, pubsocket=pubsocket)
    return serializer.encode(d)


def deserialize(s):
    d = json.loads(s)
    assert d["type"] in TYPES, \
        "Expected type in {}, got {}".format(TYPES, s)
    return d
