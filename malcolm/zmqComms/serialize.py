import json

TYPES = ["call", "get", "error", "return", "value", "ready"]


class CustomSerializer(json.JSONEncoder):

    def default(self, o):
        if hasattr(o, "to_dict"):
            return o.to_dict()
        else:
            return super(CustomSerializer, self).default(o)

serializer = CustomSerializer()


def serialize(typ, id, **kwargs):
    assert type(id) == int, "Need an integer ID, got {}".format(id)
    d = dict(id=id, type=typ, **kwargs)
    s = serializer.encode(d)
    return s


def serialize_call(id, method, **args):
    if args:
        kwargs = dict(args=args)
    else:
        kwargs = {}
    s = serialize("call", id, method=method, **kwargs)
    return s


def serialize_get(id, param):
    s = serialize("get", id, param=param)
    return s


def serialize_error(id, e):
    s = serialize("error", id, name=type(e).__name__, message=e.message)
    return s


def serialize_return(id, val):
    if val is not None:
        kwargs = dict(val=val)
    else:
        kwargs = {}
    s = serialize("return", id, **kwargs)
    return s


def serialize_value(id, val):
    s = serialize("value", id, val=val)
    return s


def serialize_ready(device):
    d = dict(type="ready", device=device)
    s = serializer.encode(d)
    return s


def deserialize(s):
    d = json.loads(s)
    assert d["type"] in TYPES, \
        "Expected type in {}, got {}".format(TYPES, s)
    if d["type"] != "ready":
        assert "id" in d, "No id in {}".format(d)
    return d
