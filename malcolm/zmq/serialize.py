import json

TYPES = ["call", "get", "error", "return", "ready"]

def serialize_call(device, method, **args):
    d = dict(type="call", device=device, method=method)
    if args:
        d["args"] = args
    return json.dumps(d)


def serialize_get(device, param=None):
    d = dict(type="get", device=device)
    if param:
        d["param"] = param
    return json.dumps(d)


def serialize_error(e):
    d = dict(type="error", name=type(e).__name__, message=e.message)
    return json.dumps(d)


def serialize_return(ret):
    d = dict(type="return")
    if ret is not None:
        d["val"] = ret
    return json.dumps(d)


def serialize_ready(device, pubsocket):
    d = dict(type="ready", device=device, pubsocket=pubsocket)
    return json.dumps(d)


def deserialize(s):
    d = json.loads(s)
    assert d["type"] in TYPES, \
        "Expected type in {}, got {}".format(TYPES, s)
    return d
