#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import os, json
from threading import Lock

import apsw

from calibre.constants import config_dir
from calibre.utils.config import to_json, from_json


class UserManager(object):

    lock = Lock()

    @property
    def conn(self):
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
                        restriction TEXT NOT NULL DEFAULT "",
                        misc_data TEXT NOT NULL DEFAULT "{}",
                        UNIQUE(name)
                    );

                    PRAGMA user_version=1;
                    ''')
                c.close()

    def __init__(self, path=None):
        self.path = os.path.join(config_dir, 'server-users.sqlite') if path is None else path
        self._conn = None

    def get_session_data(self, username):
        with self.lock:
            for data, in self.conn.cursor().execute(
                    'SELECT data FROM users WHERE name=?', (username,)):
                try:
                    return json.loads(data, object_hook=from_json)
                except Exception:
                    break
            return {}

    def set_session_data(self, username, data):
        with self.lock:
            conn = self.conn
            c = conn.cursor()
            data = json.dumps(data, ensure_ascii=False, default=to_json)
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            c.execute('UPDATE users SET data=? WHERE name=?', (data, username))

    def get(self, username):
        ' Get password for user, or None if user does not exist '
        with self.lock:
            for pw, in self.conn.cursor().execute(
                    'SELECT pw FROM users WHERE name=?', (username,)):
                return pw
