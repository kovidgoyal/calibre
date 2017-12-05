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


def parse_restriction(raw):
    r = load_json(raw)
    if not isinstance(r, dict):
        r = {}
    lr = r.get('library_restrictions', {})
    if not isinstance(lr, dict):
        lr = {}
    r['allowed_library_names'] = frozenset(map(lambda x: x.lower(), r.get('allowed_library_names', ())))
    r['blocked_library_names'] = frozenset(map(lambda x: x.lower(), r.get('blocked_library_names', ())))
    r['library_restrictions'] = {k.lower(): v or '' for k, v in lr.iteritems()}
    return r


def serialize_restriction(r):
    ans = {}
    for x in 'allowed_library_names blocked_library_names'.split():
        v = r.get(x)
        if v:
            ans[x] = list(v)
    ans['library_restrictions'] = {l.lower(): v or '' for l, v in r.get('library_restrictions', {}).iteritems()}
    return json.dumps(ans)


def validate_username(username):
    if re.sub(r'[-a-zA-Z_0-9 ]', '', username):
        return _('For maximum compatibility you should use only the letters A-Z,'
                    ' the numbers 0-9, spaces, underscores and hyphens in the username')


def validate_password(pw):
    if not pw:
        return _('Empty passwords are not allowed')
    try:
        pw = pw.encode('ascii', 'strict')
    except ValueError:
        return _('The password must contain only ASCII (English) characters and symbols')


def create_user_data(pw, readonly=False, restriction=None):
    return {
        'pw':pw, 'restriction':parse_restriction(restriction or '{}'), 'readonly': readonly
    }


class UserManager(object):

    lock = RLock()

    @property
    def conn(self):
        with self.lock:
            if self._conn is None:
                try:
                    self._conn = apsw.Connection(self.path)
                except apsw.CantOpenError:
                    pdir = os.path.dirname(self.path)
                    if os.path.isdir(pdir):
                        raise
                    os.makedirs(pdir)
                    self._conn = apsw.Connection(self.path)
                with self._conn:
                    c = self._conn.cursor()
                    uv = next(c.execute('PRAGMA user_version'))[0]
                    if uv == 0:
                        # We have to store the unhashed password, since the digest
                        # auth scheme requires it. (Technically, one can store
                        # a MD5 hash of the username+realm+password, but it has to be
                        # without salt so it is trivially brute-forceable, anyway)
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
        self._readonly = {}

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
        return validate_username(username)

    def validate_password(self, pw):
        return validate_password(pw)

    def add_user(self, username, pw, restriction=None, readonly=False):
        with self.lock:
            msg = self.validate_username(username) or self.validate_password(pw)
            if msg is not None:
                raise ValueError(msg)
            restriction = restriction or {}
            self.conn.cursor().execute(
                'INSERT INTO users (name, pw, restriction, readonly) VALUES (?, ?, ?, ?)',
                (username, pw, serialize_restriction(restriction), ('y' if readonly else 'n')))

    def remove_user(self, username):
        with self.lock:
            self.conn.cursor().execute('DELETE FROM users WHERE name=?', (username,))
            return self.conn.changes() > 0

    @property
    def all_user_names(self):
        with self.lock:
            return {x for x, in self.conn.cursor().execute(
                'SELECT name FROM users')}

    @property
    def user_data(self):
        with self.lock:
            ans = {}
            for name, pw, restriction, readonly in self.conn.cursor().execute('SELECT name,pw,restriction,readonly FROM users'):
                ans[name] = create_user_data(pw, readonly.lower() == 'y', restriction)
        return ans

    @user_data.setter
    def user_data(self, users):
        with self.lock, self.conn:
            c = self.conn.cursor()
            remove = self.all_user_names - set(users)
            if remove:
                c.executemany('DELETE FROM users WHERE name=?', [(n,) for n in remove])
            for name, data in users.iteritems():
                res = serialize_restriction(data['restriction'])
                r = 'y' if data['readonly'] else 'n'
                c.execute('UPDATE users SET pw=?, restriction=?, readonly=? WHERE name=?',
                        (data['pw'], res, r, name))
                if self.conn.changes() > 0:
                    continue
                c.execute('INSERT INTO USERS (name, pw, restriction, readonly) VALUES (?, ?, ?, ?)',
                          (name, data['pw'], res, r))
            self.refresh()

    def refresh(self):
        self._restrictions.clear()
        self._readonly.clear()

    def is_readonly(self, username):
        with self.lock:
            try:
                return self._readonly[username]
            except KeyError:
                self._readonly[username] = False
            for readonly, in self.conn.cursor().execute(
                    'SELECT readonly FROM users WHERE name=?', (username,)):
                self._readonly[username] = readonly == 'y'
                return self._readonly[username]
        return False

    def set_readonly(self, username, value):
        with self.lock:
            self.conn.cursor().execute(
                'UPDATE users SET readonly=? WHERE name=?', ('y' if value else 'n', username))
            self._readonly.pop(username, None)

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
                    self._restrictions[username] = r = parse_restriction(restriction)
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
                'UPDATE users SET restriction=? WHERE name=?', (serialize_restriction(restrictions), username))

    def library_restriction(self, username, library_path):
        r = self.restrictions(username)
        if r is None:
            return ''
        library_name = os.path.basename(library_path).lower()
        return r['library_restrictions'].get(library_name) or ''
