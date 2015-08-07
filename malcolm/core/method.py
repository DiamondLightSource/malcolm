import functools
import inspect
from attribute import Attribute
from json import JSONEncoder


class Method():

    def __init__(self, function, valid_states=None, args_from=None):
        assert inspect.isfunction(function), \
            "Expected function, got {}".format(function)
        self.function = function
        if valid_states is None or type(valid_states) in (list, tuple):
            self.valid_states = valid_states
        else:
            try:
                self.valid_states = list(valid_states)
            except TypeError:
                self.valid_states = [valid_states]
        self.args_from = args_from
        functools.update_wrapper(self, self.function)

    def describe(self, device):
        self.device = device
        # If args_from then get the args from another named member functions
        if self.args_from:
            # Get method object from device using the supplied function name
            function = getattr(device, self.args_from.__name__).function
        else:
            function = self.function
        # Set the docstring from the _actual_ function
        self.descriptor = self.function.__doc__
        # Get the args and defaults from the args_from function
        args, varargs, keywords, defaults = inspect.getargspec(function)
        # Pop self off
        if args and args[0] == "self":
            args.pop(0)
        assert varargs is None, \
            "Not allowed to use *{} in {}".format(varargs, function)
        assert keywords is None, \
            "Not allowed to use **{} in {}".format(keywords, function)
        # Make the structure
        self.args = {}
        if defaults is None:
            defaults = []
        for i, arg in enumerate(args):
            attribute = device.attributes.attributes[arg]
            assert attribute.name == arg, \
                "Attribute name {} should be {}".format(attribute.name, arg)
            self.args[arg] = Attribute(
                attribute.name, attribute.typ, attribute.descriptor)
            defaulti = i - len(args) + len(defaults)
            if defaulti < 0:
                # required
                self.args[arg].tags.append("required")
            else:
                # default
                self.args[arg].value = defaults[defaulti]
            attribute.tags.append(self.function.__name__)

    def __call__(self, *args, **kwargs):
        if self.valid_states is not None:
            assert self.device.state in self.valid_states, \
                "Command not allowed in {} state".format(self.device.state)
        # TODO: validate args and kwargs from attributes
        return self.function(self.device, *args, **kwargs)

    @classmethod
    def describe_methods(cls, device):
        def ismethod(thing):
            return isinstance(thing, cls)
        methods = {}
        for mname, method in inspect.getmembers(device, predicate=ismethod):
            method.describe(device)
            methods[mname] = method
        return methods

    def to_dict(self):
        d = dict(descriptor=self.descriptor, args=self.args)
        if self.valid_states:
            d["valid_states"] = [s.name for s in self.valid_states]
        return d
    

def wrap_method(only_in=None, args_from=None):
    """Provide a wrapper function that checks types"""
    def decorator(function):
        return Method(function, only_in, args_from)
    return decorator
