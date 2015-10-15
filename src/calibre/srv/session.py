#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
from copy import deepcopy
from uuid import uuid4
from threading import Lock

from calibre.utils.lru_cache import lru_cache

defaults = {
    'sort': 'date:desc',
    'library_id': None,
    'view_mode': 'cover_grid',
}

class Session(object):

    def __init__(self):
        self._data = deepcopy(defaults)

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, val):
        self._data[key] = val


class SessionProxy(object):

    ''' Prevent the creation of a long-lived session object for every new
    request without a session cookie. Instead, this object lives only as long
    an individual request, and unless some setting is changed from the default
    simply returns values from the global defaults object. '''

    def __init__(self, sessions, key):
        self.sessions = sessions
        self.key = key
        self.actual_session = None

    def __getitem__(self, key):
        if self.actual_session is None:
            return defaults[key]
        return self.actual_session[key]

    def __setitem__(self, key, val):
        with self.sessions.lock:
            if self.actual_session is None:
                self.actual_session = self.sessions.cache[self.key] = Session()
        self.actual_session[key] = val

class Sessions(object):

    def __init__(self):
        self.cache = lru_cache(size=2000)
        self.lock = Lock()

    def get_or_create(self, key=None, username=None):
        key = key or str(uuid4()).replace('-', '')
        try:
            with self.lock:
                return self.cache[key]
        except KeyError:
            return SessionProxy(self, key)
