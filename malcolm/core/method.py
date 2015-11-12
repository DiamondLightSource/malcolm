from collections import OrderedDict
import inspect
import functools
import weakref
import copy

from .base import Base
from .attribute import Attribute
from malcolm.core.attribute import InstanceAttribute


class HasMethods(Base):
    """Mixin that allows Attribute objects to be stored in a class"""
    _methods_prefix = "methods."

    def add_methods(self, **attributes):
        # combine attributes
        if hasattr(self, "attributes"):
            merged_attributes = self.attributes.copy()
            merged_attributes.update(attributes)
            attributes = merged_attributes

        def ismethod(thing):
            return isinstance(thing, Method)

        for _, method in inspect.getmembers(self, predicate=ismethod):
            self.add_method(method, **attributes)

    def add_method(self, method, **attributes):
        # Decorated function is an object, when we subclass we need to
        # copy it so we do the manualy weak binding on the right object
        # can't do it elsewhere, so do it here
        method = copy.copy(method)
        # Lazily make methods dict
        if not hasattr(self, "methods"):
            self.methods = OrderedDict()

        method.describe(self, attributes)
        self.methods[method.name] = method
        # make sure self.blah calls the copied method
        setattr(self, method.name, method)


def wrap_method(only_in=None, arguments_from=None, **attributes):
    """Provide a wrapper function that checks types"""
    def decorator(function):
        assert inspect.isfunction(function), \
            "Expected function, got {}".format(function)
        name = function.__name__
        descriptor = function.__doc__
        return Method(name, descriptor, function, only_in,
                      arguments_from, **attributes)
    return decorator


class Method(Base):
    """Class representing a callable method"""
    _endpoints = "name,descriptor,arguments,validStates".split(",")

    def __init__(self, name, descriptor, function, valid_states=None,
                 arguments_from=None, **attributes):
        # Set the name and docstring from the _actual_ function
        super(Method, self).__init__(name)
        self.descriptor = descriptor
        self.function = function
        functools.update_wrapper(self, self.function)
        if valid_states is None or type(valid_states) in (list, tuple):
            self.valid_states = valid_states
        else:
            try:
                self.valid_states = list(valid_states)
            except TypeError:
                self.valid_states = [valid_states]
        self.arguments_from = arguments_from
        self.device = None
        self.attributes = attributes

    def _get_args_defaults(self, function, check_var=True):
        # Get the arguments and defaults from the arguments_from function
        args, varargs, keywords, defaults = inspect.getargspec(function)
        # Pop self off
        if args and args[0] == "self":
            args.pop(0)
        if check_var:
            assert varargs is None, \
                "Not allowed to use *{} in {}".format(varargs, function)
            assert keywords is None, \
                "Not allowed to use **{} in {}".format(keywords, function)
        default_d = {}
        if defaults is None:
            defaults = []
        default_off = len(args) - len(defaults)
        for i, default in enumerate(defaults):
            default_d[args[i + default_off]] = default
        return args, default_d

    def describe(self, device, attributes):
        self.attributes.update(attributes)
        self.device = weakref.proxy(device)
        # If arguments_from then get the arguments from another named member
        # functions
        if self.arguments_from:
            # Get method object from device using the supplied function name
            method = getattr(device, self.arguments_from.__name__, None)
            if method and isinstance(method, Method):
                function = method.function
            else:
                function = self.arguments_from
            args, defaults = self._get_args_defaults(function)
            extra_args, extra_defaults = self._get_args_defaults(
                self.function, check_var=False)
            for arg in extra_args:
                assert arg not in args, \
                    "Duplicate argument {} in {}".format(
                        arg, self.function.__name__)
                args.append(arg)
                if arg in extra_defaults:
                    defaults[arg] = extra_defaults[arg]
        else:
            function = self.function
            args, defaults = self._get_args_defaults(function)
        # Make the structure
        self.arguments = OrderedDict()
        for arg in args:
            if arg in defaults:
                # default
                tags = []
                value = defaults[arg]
            else:
                # required
                tags = ["argument:required"]
                value = None
            attribute = self.attributes[arg]
            attr_args = dict(descriptor=attribute.descriptor,
                             name=arg, value=value, tags=tags)
            if isinstance(attribute, InstanceAttribute):
                a = InstanceAttribute(dcls=attribute.dcls, **attr_args)
                device._instance_attributes.append(a)
            else:
                a = Attribute(typ=attribute.typ, **attr_args)
            self.arguments[arg] = a
            attribute.tags.append("method:{}".format(self.function.__name__))

    def __call__(self, *args, **kwargs):
        assert self.device, \
            "Cannot run before device.add_methods() has been called"
        sm = getattr(self.device, "stateMachine", None)
        if sm and self.valid_states is not None:
            assert sm.state in self.valid_states, \
                "Method {} not allowed in {} state".format(
                    self.function.__name__, sm.state)
        # Add in args
        for aname, aval in zip(self.arguments.keys(), args):
            kwargs[aname] = aval
        # Check arg presence and values
        missing = []
        for arg, attr in self.arguments.items():
            if arg not in kwargs:
                if "argument:required" not in attr.tags:
                    kwargs[arg] = attr.value
                else:
                    missing.append(arg)
        assert len(missing) == 0, \
            "Arguments not supplied: {}, you gave me {}".format(
                missing, kwargs)
        # Now report extras
        extras = [x for x in sorted(kwargs) if x not in self.arguments]
        assert len(extras) == 0, \
            "Unknown arguments supplied: {}".format(extras)
        # Now validate
        for k, v in kwargs.items():
            kwargs[k] = self.arguments[k].typ.validate(v)
        return self.function(self.device, **kwargs)

    def to_dict(self):
        if self.valid_states:
            valid_states = [s.name for s in self.valid_states]
        else:
            valid_states = []
        return super(Method, self).to_dict(validStates=valid_states)


class ClientMethod(Method):

    def describe(self, device, attributes):
        self.device = weakref.proxy(device)
        # attributes here are arguments
        self.arguments = OrderedDict()
        for name, arg in self.in_arguments.items():
            a = Attribute(arg["type"], arg["descriptor"],
                          value=arg.get("value", None), name=name,
                          tags=arg.get("tags", []))
            self.arguments[name] = a
