def command(only_in, args_from=None, **attributes):
    """Provide a wrapper function that checks types"""
    decorated_args = locals().copy()

    def decorator(function):

        def decorated_command(self, *args, **kwargs):
            # TODO: validate args and kwargs from attributes
            return function(self, *args, **kwargs)

        decorated_command.decorated_args = decorated_args
        return decorated_command
    return decorator
