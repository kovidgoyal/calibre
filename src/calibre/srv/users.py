#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (unicode_literals, division, absolute_import,
                        print_function)
import os, json

import apsw

from calibre.constants import config_dir
from calibre.utils.config import to_json, from_json

class UserManager(object):

    @property
    def conn(self):
        if self._conn is None:
            self._conn = apsw.Connection(self.path)
            c = self._conn.cursor()
            uv = next(c.execute('PRAGMA foreign_keys = ON; PRAGMA user_version'))[0]
            if uv == 0:
                c.execute('''
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    salt TEXT NOT NULL,
    hashed_pw TEXT NOT NULL,
    hash_type TEXT NOT NULL,
    creation_date INTEGER NOT NULL,
    UNIQUE(name)
);

CREATE TABLE session_data (
    id INTEGER PRIMARY KEY,
    user INTEGER NOT NULL,
    data TEXT NOT NULL,
    UNIQUE(user),
    FOREIGN KEY user REFERENCES users.id
);

PRAGMA user_version=1;
''')
            c.close()

    def __init__(self):
        self.path = os.path.join(config_dir, 'server-users.sqlite')
        self._conn = None

    def get_session_data(self, username):
        for data, in self.conn.cursor().execute(
                'SELECT data FROM session_data INNER JOIN users ON (session_data.user = users.id) WHERE users.name=?', (username,)):
            try:
                return json.loads(data, object_hook=from_json)
            except Exception:
                pass
        return {}

    def set_session_data(self, username, data):
        conn = self.conn
        c = conn.cursor()
        for user_id, in c.execute('SELECT id FROM users WHERE name=?', (username,)):
            data = json.dumps(data, ensure_ascii=False, default=to_json)
            c.execute('UPDATE session_data SET data=? WHERE user=?', (data, user_id))
            if not conn.changes():
                c.execute('INSERT INTO session_data (data,user) VALUES (?,?)', (data, user_id))
