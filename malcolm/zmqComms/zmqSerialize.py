import json
from enum import Enum


class SType(Enum):
    Call, Get, Error, Return, Value, Ready = range(6)


class CustomSerializer(json.JSONEncoder):

    def default(self, o):
        if hasattr(o, "to_dict"):
            return o.to_dict()
        else:
            return super(CustomSerializer, self).default(o)

serializer = CustomSerializer()


def serialize(typ, _id, **kwargs):
    assert type(_id) == int, "Need an integer ID, got {}".format(_id)
    assert typ in SType, \
        "Expected type in {}, got {}".format(list(SType.__members__), typ)
    d = dict(id=_id, type=typ.name, **kwargs)
    s = serializer.encode(d)
    return s


def serialize_call(_id, method, **args):
    if args:
        kwargs = dict(args=args)
    else:
        kwargs = {}
    s = serialize(SType.Call, _id, method=method, **kwargs)
    return s


def serialize_get(_id, param):
    s = serialize(SType.Get, _id, param=param)
    return s


def serialize_error(_id, e):
    s = serialize(SType.Error, _id, message=e.message)
    return s


def serialize_return(_id, val):
    if val is not None:
        kwargs = dict(val=val)
    else:
        kwargs = {}
    s = serialize(SType.Return, _id, **kwargs)
    return s


def serialize_value(_id, val):
    s = serialize(SType.Value, _id, val=val)
    return s


def serialize_ready(device):
    d = dict(type=SType.Ready.name, device=device)
    s = serializer.encode(d)
    return s


def deserialize(s):
    d = json.loads(s)
    typ = d["type"]
    assert typ in SType.__members__, \
        "Expected type in {}, got {}".format(list(SType.__members__), typ)
    d["type"] = SType.__members__[typ]
    if d["type"] != SType.Ready:
        assert "id" in d, "No id in {}".format(d)
    return d
