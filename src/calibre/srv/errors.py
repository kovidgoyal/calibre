#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from polyglot import http_client


class JobQueueFull(Exception):
    pass


class RouteError(ValueError):
    pass


class HTTPSimpleResponse(Exception):

    def __init__(self, http_code, http_message='', close_connection=False, location=None, authenticate=None, log=None):
        Exception.__init__(self, http_message)
        self.http_code = http_code
        self.close_connection = close_connection
        self.location = location
        self.authenticate = authenticate
        self.log = log


class HTTPRedirect(HTTPSimpleResponse):

    def __init__(self, location, http_code=http_client.MOVED_PERMANENTLY, http_message='', close_connection=False):
        HTTPSimpleResponse.__init__(self, http_code, http_message, close_connection, location)


class HTTPNotFound(HTTPSimpleResponse):

    def __init__(self, http_message='', close_connection=False):
        HTTPSimpleResponse.__init__(self, http_client.NOT_FOUND, http_message, close_connection)


class HTTPAuthRequired(HTTPSimpleResponse):

    def __init__(self, payload, log=None):
        HTTPSimpleResponse.__init__(self, http_client.UNAUTHORIZED, authenticate=payload, log=log)


class HTTPBadRequest(HTTPSimpleResponse):

    def __init__(self, message, close_connection=False):
        HTTPSimpleResponse.__init__(self, http_client.BAD_REQUEST, message, close_connection)


class HTTPForbidden(HTTPSimpleResponse):

    def __init__(self, http_message='', close_connection=True, log=None):
        HTTPSimpleResponse.__init__(self, http_client.FORBIDDEN, http_message, close_connection, log=log)


class HTTPInternalServerError(HTTPSimpleResponse):

    def __init__(self, http_message='', close_connection=True, log=None):
        HTTPSimpleResponse.__init__(self, http_client.INTERNAL_SERVER_ERROR, http_message, close_connection, log=log)


class BookNotFound(HTTPNotFound):

    def __init__(self, book_id, db):
        HTTPNotFound.__init__(self, 'No book with id: {} in library: {}'.format(book_id, db.server_library_id))
