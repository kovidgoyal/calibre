#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import httplib

class JobQueueFull(Exception):
    pass

class HTTPSimpleResponse(Exception):

    def __init__(self, http_code, http_message='', close_connection=False, location=None):
        Exception.__init__(self, http_message)
        self.http_code = http_code
        self.close_connection = close_connection
        self.location = location

class HTTPRedirect(HTTPSimpleResponse):

    def __init__(self, location, http_code=httplib.MOVED_PERMANENTLY, http_message='', close_connection=False):
        HTTPSimpleResponse.__init__(self, http_code, http_message, close_connection, location)

class HTTPNotFound(HTTPSimpleResponse):

    def __init__(self, http_message='', close_connection=False):
        HTTPSimpleResponse.__init__(self, httplib.NOT_FOUND, http_message, close_connection)
