#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import os, json, re
from threading import RLock

import apsw

from calibre.constants import config_dir
from calibre.utils.config import to_json, from_json


def as_json(data):
    return json.dumps(data, ensure_ascii=False, default=to_json)


def load_json(raw):
    try:
        return json.loads(raw, object_hook=from_json)
    except Exception:
        return {}


class UserManager(object):

    lock = RLock()

    @property
    def conn(self):
        with self.lock:
            if self._conn is None:
                self._conn = apsw.Connection(self.path)
                with self._conn:
                    c = self._conn.cursor()
                    uv = next(c.execute('PRAGMA user_version'))[0]
                    if uv == 0:
                        # We have to store the unhashed password, since the digest
                        # auth scheme requires it.
                        # timestamp stores the ISO 8601 creation timestamp in UTC.
                        c.execute('''
                        CREATE TABLE users (
                            id INTEGER PRIMARY KEY,
                            name TEXT NOT NULL,
                            pw TEXT NOT NULL,
                            timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                            session_data TEXT NOT NULL DEFAULT "{}",
                            restriction TEXT NOT NULL DEFAULT "{}",
                            readonly TEXT NOT NULL DEFAULT "n",
                            misc_data TEXT NOT NULL DEFAULT "{}",
                            UNIQUE(name)
                        );

                        PRAGMA user_version=1;
                        ''')
                    c.close()
        return self._conn

    def __init__(self, path=None):
        self.path = os.path.join(config_dir, 'server-users.sqlite') if path is None else path
        self._conn = None
        self._restrictions = {}

    def get_session_data(self, username):
        with self.lock:
            for data, in self.conn.cursor().execute(
                    'SELECT session_data FROM users WHERE name=?', (username,)):
                return load_json(data)
        return {}

    def set_session_data(self, username, data):
        with self.lock:
            conn = self.conn
            c = conn.cursor()
            data = as_json(data)
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            c.execute('UPDATE users SET session_data=? WHERE name=?', (data, username))

    def get(self, username):
        ' Get password for user, or None if user does not exist '
        with self.lock:
            for pw, in self.conn.cursor().execute(
                    'SELECT pw FROM users WHERE name=?', (username,)):
                return pw

    def has_user(self, username):
        return self.get(username) is not None

    def validate_username(self, username):
        if self.has_user(username):
            return _('The username %s already exists') % username
        if re.sub(r'[a-zA-Z0-9 ]', '', username):
            return _('For maximum compatibility you should use only the letters A-Z, the numbers 0-9 and spaces in the username')

    def validate_password(self, pw):
        try:
            pw = pw.encode('ascii', 'strict')
        except ValueError:
            return _('The password must contain only ASCII (English) characters and symbols')

    def add_user(self, username, pw, restriction=None, readonly=False):
        with self.lock:
            msg = self.validate_username(username) or self.validate_password(pw)
            if msg is not None:
                raise ValueError(msg)
            restriction = restriction or {}
            if not isinstance(restriction, dict):
                raise TypeError('restriction must be a dict')
            self.conn.cursor().execute(
                'INSERT INTO users (name, pw, restriction, readonly) VALUES (?, ?, ?, ?)',
                (username, pw, json.dumps(restriction), ('y' if readonly else 'n')))

    def remove_user(self, username):
        with self.lock:
            self.conn.cursor().execute('DELETE FROM users WHERE name=?', (username,))
            return self.conn.changes() > 0

    @property
    def all_user_names(self):
        with self.lock:
            return {x for x, in self.conn.cursor().execute(
                'SELECT name FROM users')}

    def change_password(self, username, pw):
        with self.lock:
            msg = self.validate_password(pw)
            if msg is not None:
                raise ValueError(msg)
            self.conn.cursor().execute(
                'UPDATE users SET pw=? WHERE name=?', (pw, username))

    def restrictions(self, username):
        with self.lock:
            r = self._restrictions.get(username)
            if r is None:
                for restriction, in self.conn.cursor().execute(
                        'SELECT restriction FROM users WHERE name=?', (username,)):
                    self._restrictions[username] = r = json.loads(restriction)
                    r['allowed_library_names'] = frozenset(r.get('allowed_library_names', ()))
                    r['blocked_library_names'] = frozenset(r.get('blocked_library_names', ()))
                    break
            return r

    def allowed_library_names(self, username, all_library_names):
        ' Get allowed library names for specified user from set of all library names '
        r = self.restrictions(username)
        if r is None:
            return set()
        inc = r['allowed_library_names']
        exc = r['blocked_library_names']

        def check(n):
            n = n.lower()
            return (not inc or n in inc) and n not in exc
        return {n for n in all_library_names if check(n)}

    def update_user_restrictions(self, username, restrictions):
        if not isinstance(restrictions, dict):
            raise TypeError('restrictions must be a dict')
        with self.lock:
            self._restrictions.pop(username, None)
            self.conn.cursor().execute(
                'UPDATE users SET restriction=? WHERE name=?', (json.dumps(restrictions), username))
