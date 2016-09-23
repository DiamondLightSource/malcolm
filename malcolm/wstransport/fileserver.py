import os


# Number of bytes to send in each block
BLOCK_SIZE = 4096


class FileServer(object):
    """ Serves static files from a directory.
    """

    def __init__(self, path, ws_handler):
        """ path is directory where static files are stored
        """
        from wsgiref import util
        util._hoppish = {}.__contains__

        self.path = path
        from ws4py.server.wsgiutils import WebSocketWSGIApplication
        self.wsapp = WebSocketWSGIApplication(handler_cls=ws_handler)

    def __call__(self, environ, start_response):
        """ WSGI entry point
        """
        # Upgrade header means websockets...
        upgrade_header = environ.get('HTTP_UPGRADE', '').lower()
        if upgrade_header:
            from ws4py.compat import get_connection
            environ['ws4py.socket'] = get_connection(environ['wsgi.input'])
            # This will make a websocket, hopefully!
            ret = self.wsapp(environ, start_response)
            if 'ws4py.websocket' in environ:
                import cothread
                cothread.Spawn(environ.pop('ws4py.websocket').run)
            return ret

        # Find path to file to server
        path_info = environ["PATH_INFO"]

        if not path_info:
            return self._not_found(start_response)
        elif path_info == "/":
            path_info = "/index.html"

        file_path = os.path.join(self.path, path_info[1:])

        # If file does not exist, return 404
        if not os.path.exists(file_path):
            return self._not_found(start_response)

        # Guess mimetype of file based on file extension
        import mimetypes
        mimetype = mimetypes.guess_type(file_path)[0]

        # If we can't guess mimetype, return a 403 Forbidden
        if mimetype is None:
            if file_path.endswith(".woff"):
                mimetype = "application/octet-stream"
            else:
                return self._forbidden(start_response)

        # Get size of file
        size = os.path.getsize(file_path)

        # Create headers and start response
        headers = [
            ("Content-type", mimetype),
            ("Content-length", str(size)),
        ]

        start_response("200 OK", headers)

        # Send file
        return self._send_file(file_path, size)

    def _send_file(self, file_path, size):
        """ A generator function which returns the blocks in a file, one at
        a time.

        """
        with open(file_path) as f:
            block = f.read(BLOCK_SIZE)
            while block:
                yield block
                block = f.read(BLOCK_SIZE)

    def _not_found(self, start_response):
        start_response("404 NOT FOUND", [("Content-type", "text/plain")])
        return ["Not found", ]

    def _forbidden(self, start_response):
        start_response("403 FORBIDDEN", [("Content-type", "text/plain")])
        return ["Forbidden", ]
