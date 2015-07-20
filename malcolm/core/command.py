def command(only_in, args_from=None, **attributes):
    """Provide a wrapper function that checks types"""
    decorated_args = locals().copy()
    try:
        states = list(only_in)
    except TypeError:
        states = [only_in]

    def decorator(function):

        def decorated_command(self, *args, **kwargs):
            assert self.state in states, \
                "Command not allowed in {} state".format(self.state)
            # TODO: validate args and kwargs from attributes
            return function(self, *args, **kwargs)

        decorated_command.decorated_args = decorated_args
        return decorated_command
    return decorator
