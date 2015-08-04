import json

TYPES = ["call", "get", "error", "return", "value", "ready"]


class CustomSerializer(json.JSONEncoder):

    def default(self, o):
        if hasattr(o, "to_dict"):
            return o.to_dict()
        else:
            return super(CustomSerializer, self).default(o)

serializer = CustomSerializer()


def serialize(typ, _id, **kwargs):
    assert type(_id) == int, "Need an integer ID, got {}".format(_id)
    d = dict(id=_id, type=typ, **kwargs)
    s = serializer.encode(d)
    return s


def serialize_call(_id, method, **args):
    if args:
        kwargs = dict(args=args)
    else:
        kwargs = {}
    s = serialize("call", _id, method=method, **kwargs)
    return s


def serialize_get(_id, param):
    s = serialize("get", _id, param=param)
    return s


def serialize_error(_id, e):
    s = serialize("error", _id, message=e.message)
    return s


def serialize_return(_id, val):
    if val is not None:
        kwargs = dict(val=val)
    else:
        kwargs = {}
    s = serialize("return", _id, **kwargs)
    return s


def serialize_value(_id, val):
    s = serialize("value", _id, val=val)
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
