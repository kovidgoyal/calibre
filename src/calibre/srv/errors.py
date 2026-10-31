#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

import http.client
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from calibre.db.cache import Cache


class JobQueueFull(Exception):
    pass


class RouteError(ValueError):
    pass


class HTTPSimpleResponse(Exception):
    def __init__(
        self,
        http_code: int,
        http_message: str = '',
        close_connection: bool = False,
        location: str | None = None,
        authenticate: str | None = None,
        log: str | None = None,
    ) -> None:
        Exception.__init__(self, http_message)
        self.http_code = http_code
        self.close_connection = close_connection
        self.location = location
        self.authenticate = authenticate
        self.log = log


class HTTPRedirect(HTTPSimpleResponse):
    def __init__(self, location: str, http_code: int = http.client.MOVED_PERMANENTLY, http_message: str = '', close_connection: bool = False) -> None:
        HTTPSimpleResponse.__init__(self, http_code, http_message, close_connection, location)


class HTTPTempRedirect(HTTPSimpleResponse):
    def __init__(self, location: str, http_code: int = http.client.TEMPORARY_REDIRECT, http_message: str = '', close_connection: bool = False) -> None:
        HTTPSimpleResponse.__init__(self, http_code, http_message, close_connection, location)


class HTTPNotFound(HTTPSimpleResponse):
    def __init__(self, http_message: str = '', close_connection: bool = False) -> None:
        HTTPSimpleResponse.__init__(self, http.client.NOT_FOUND, http_message, close_connection)


class HTTPAuthRequired(HTTPSimpleResponse):
    def __init__(self, payload: str, log: str | None = None) -> None:
        HTTPSimpleResponse.__init__(self, http.client.UNAUTHORIZED, authenticate=payload, log=log)


class HTTPBadRequest(HTTPSimpleResponse):
    def __init__(self, message: str, close_connection: bool = False) -> None:
        HTTPSimpleResponse.__init__(self, http.client.BAD_REQUEST, message, close_connection)


class HTTPFailedDependency(HTTPSimpleResponse):
    def __init__(self, message: str, close_connection: bool = False) -> None:
        HTTPSimpleResponse.__init__(self, http.client.FAILED_DEPENDENCY, message, close_connection)


class HTTPPreconditionRequired(HTTPSimpleResponse):
    def __init__(self, message: str, close_connection: bool = False) -> None:
        HTTPSimpleResponse.__init__(self, http.client.PRECONDITION_REQUIRED, message, close_connection)


class HTTPUnprocessableEntity(HTTPSimpleResponse):
    def __init__(self, message: str, close_connection: bool = False) -> None:
        HTTPSimpleResponse.__init__(self, http.client.UNPROCESSABLE_ENTITY, message, close_connection)


class HTTPForbidden(HTTPSimpleResponse):
    def __init__(self, http_message: str = '', close_connection: bool = True, log: str | None = None) -> None:
        HTTPSimpleResponse.__init__(self, http.client.FORBIDDEN, http_message, close_connection, log=log)


class HTTPInternalServerError(HTTPSimpleResponse):
    def __init__(self, http_message: str = '', close_connection: bool = True, log: str | None = None) -> None:
        HTTPSimpleResponse.__init__(self, http.client.INTERNAL_SERVER_ERROR, http_message, close_connection, log=log)


class BookNotFound(HTTPNotFound):
    def __init__(self, book_id: int | str, db: Cache) -> None:
        HTTPNotFound.__init__(self, f'No book with id: {book_id} in library: {db.server_library_id}')
