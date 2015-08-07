import json
from enum import Enum
from collections import OrderedDict


class SType(Enum):
    Call, Get, Error, Return, Value, Ready = range(6)


class CustomSerializer(json.JSONEncoder):

    def default(self, o):
        if hasattr(o, "to_dict"):
            return o.to_dict()
        else:
            return super(CustomSerializer, self).default(o)

serializer = CustomSerializer()


def serialize(typ, _id, kwargs):
    assert type(_id) == int, "Need an integer ID, got {}".format(_id)
    assert typ in SType, \
        "Expected type in {}, got {}".format(list(SType.__members__), typ)
    d = OrderedDict(type=typ.name)
    d.update(id=_id)
    d.update(kwargs)
    s = serializer.encode(d)
    return s


def serialize_call(_id, method, **args):
    d = OrderedDict(method=method)
    if args:
        d.update(args=args)
    s = serialize(SType.Call, _id, d)
    return s


def serialize_get(_id, param):
    d = OrderedDict(param=param)
    s = serialize(SType.Get, _id, d)
    return s


def serialize_error(_id, e):
    d = OrderedDict(message=e.message)
    s = serialize(SType.Error, _id, d)
    return s


def serialize_return(_id, val):
    d = OrderedDict()
    if val is not None:
        d.update(val=val)
    s = serialize(SType.Return, _id, d)
    return s


def serialize_value(_id, val):
    d = OrderedDict(val=val)
    s = serialize(SType.Value, _id, d)
    return s


def serialize_ready(device):
    d = OrderedDict(type=SType.Ready.name)
    d.update(device=device)
    s = serializer.encode(d)
    return s


def deserialize(s):
    d = json.loads(s, object_pairs_hook=OrderedDict)
    typ = d["type"]
    assert typ in SType.__members__, \
        "Expected type in {}, got {}".format(list(SType.__members__), typ)
    d["type"] = SType.__members__[typ]
    if d["type"] != SType.Ready:
        assert "id" in d, "No id in {}".format(d)
    return d
