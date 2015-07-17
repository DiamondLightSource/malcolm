import json


def serialize_method(method, **args):
    d = dict(name=method, args=args)
    return json.dumps(d)


def serialize_error(e):
    d = dict(name="error", type=type(e).__name__, message=e.message)
    return json.dumps(d)


def serialize_return(ret):
    d = dict(name="return")
    if ret is not None:
        d["ret"] = ret
    return json.dumps(d)


def serialize_ready(device, pubsocket):
    d = dict(name="ready", device=device, pubsocket=pubsocket)
    return json.dumps(d)


def deserialize(s):
    return json.loads(s)
