#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

import json
import os
import re
from functools import lru_cache
from threading import RLock
from typing import TYPE_CHECKING, cast

import apsw

from calibre import as_unicode
from calibre.constants import config_dir
from calibre.utils.config import from_json, to_json
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping
    from typing import TypedDict

    class Restriction(TypedDict, total=False):
        allowed_library_names: frozenset[str] | list[str]
        blocked_library_names: frozenset[str] | list[str]
        # Maps lowercased library names to search restrictions
        library_restrictions: dict[str, str]

    class UserData(TypedDict):
        pw: str
        restriction: Restriction
        readonly: bool
        allow_change_password_via_http: bool


def as_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, default=to_json)


def load_json(raw: str | bytes) -> object:
    try:
        return json.loads(raw, object_hook=from_json)
    except Exception:
        return {}


@lru_cache(maxsize=1024)
def parse_restriction(raw: str) -> Restriction:
    r = load_json(raw)
    if not isinstance(r, dict):
        r = {}
    lr = r.get('library_restrictions', {})
    if not isinstance(lr, dict):
        lr = {}
    r['allowed_library_names'] = frozenset(x.lower() for x in r.get('allowed_library_names', ()))
    r['blocked_library_names'] = frozenset(x.lower() for x in r.get('blocked_library_names', ()))
    r['library_restrictions'] = {k.lower(): v or '' for k, v in lr.items()}
    return cast('Restriction', r)


def serialize_restriction(r: Restriction) -> str:
    ans: dict[str, object] = {}
    for x in 'allowed_library_names blocked_library_names'.split():
        v = r.get(x)
        if v:
            ans[x] = list(v)
    ans['library_restrictions'] = {l.lower(): v or '' for l, v in r.get('library_restrictions', {}).items()}
    return json.dumps(ans)


def validate_username(username: str) -> str | None:
    if re.sub(r'[-a-zA-Z_0-9 ]', '', username):
        return _('For maximum compatibility you should use only the letters A-Z, the numbers 0-9, spaces, underscores and hyphens in the username')


def validate_password(pw: str) -> str | None:
    if not pw:
        return _('Empty passwords are not allowed')
    try:
        pw = pw.encode('ascii', 'strict')  # ty: ignore[invalid-assignment]
    except ValueError:
        return _('The password must contain only ASCII (English) characters and symbols')


def create_user_data(pw: str, readonly: bool = False, restriction: str | None = None, misc_data: str = '{}') -> UserData:
    misc_data = json.loads(misc_data)
    return {
        'pw': pw,
        'restriction': parse_restriction(restriction or '{}').copy(),
        'readonly': readonly,
        'allow_change_password_via_http': bool(misc_data.get('allow_change_password_via_http', True)),
    }


def connect(path: str, exc_class: type[BaseException] = ValueError) -> apsw.Connection:
    try:
        return apsw.Connection(path)
    except apsw.CantOpenError as e:
        pdir = os.path.dirname(path)
        if os.path.isdir(pdir):
            raise exc_class(f'Failed to open userdb database at {path} with error: {as_unicode(e)}')
        try:
            os.makedirs(pdir)
        except OSError as e:
            raise exc_class(f'Failed to make directory for userdb database at {pdir} with error: {as_unicode(e)}')
        try:
            return apsw.Connection(path)
        except apsw.CantOpenError as e:
            raise exc_class(f'Failed to open userdb database at {path} with error: {as_unicode(e)}')


class UserManager:
    lock = RLock()
    # The maximum number of documents for which KOReader reading positions are kept per user
    kosync_max_documents = 10000

    @property
    def conn(self) -> apsw.Connection:
        with self.lock:
            if self._conn is None:
                self._conn = connect(self.path)
                # Has no effect inside a transaction, so must be set here
                self._conn.cursor().execute('PRAGMA foreign_keys=ON')
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
                        uv = 1
                    if uv == 1:
                        # Reading positions synced by KOReader devices, see
                        # kosync.py. Positions of users are keyed by their id
                        # so that they cannot be confused with positions
                        # stored when authentication is disabled, which are
                        # keyed by whatever username KOReader sends and so are
                        # stored separately. The trigger removes the positions
                        # of deleted users even when foreign keys are not
                        # enabled, as by older versions of calibre.
                        c.execute('''
                        CREATE TABLE kosync_progress (
                            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                            document TEXT NOT NULL,
                            progress TEXT NOT NULL,
                            percentage REAL NOT NULL,
                            device TEXT NOT NULL,
                            device_id TEXT,
                            timestamp INTEGER NOT NULL,
                            PRIMARY KEY (user_id, document)
                        );

                        CREATE TRIGGER kosync_progress_delete_user AFTER DELETE ON users
                        BEGIN
                            DELETE FROM kosync_progress WHERE user_id=OLD.id;
                        END;

                        CREATE TABLE kosync_anonymous_progress (
                            user TEXT NOT NULL,
                            document TEXT NOT NULL,
                            progress TEXT NOT NULL,
                            percentage REAL NOT NULL,
                            device TEXT NOT NULL,
                            device_id TEXT,
                            timestamp INTEGER NOT NULL,
                            PRIMARY KEY (user, document)
                        );

                        PRAGMA user_version=2;
                        ''')
                    c.close()
        return self._conn

    def __init__(self, path: str | None = None) -> None:
        self.path = os.path.join(config_dir, 'server-users.sqlite') if path is None else path
        self._conn: apsw.Connection | None = None

    def get_session_data(self, username: str | None) -> dict:
        with self.lock:
            for (data,) in self.conn.cursor().execute('SELECT session_data FROM users WHERE name=?', (username,)):
                return cast('dict', load_json(data))
        return {}

    def set_session_data(self, username: str | None, data: object) -> None:
        with self.lock:
            conn = self.conn
            c = conn.cursor()
            data = as_json(data)
            if isinstance(data, bytes):
                data = data.decode('utf-8')
            c.execute('UPDATE users SET session_data=? WHERE name=?', (data, username))

    def get(self, username: str | None) -> str | None:
        "Get password for user, or None if user does not exist"
        with self.lock:
            for (pw,) in self.conn.cursor().execute('SELECT pw FROM users WHERE name=?', (username,)):
                return pw

    def has_user(self, username: str | None) -> bool:
        return self.get(username) is not None

    def validate_username(self, username: str) -> str | None:
        if self.has_user(username):
            return _('The username %s already exists') % username
        return validate_username(username)

    def validate_password(self, pw: str) -> str | None:
        return validate_password(pw)

    def add_user(
        self, username: str, pw: str, restriction: Restriction | None = None, readonly: bool = False, allow_change_password_via_http: bool = True
    ) -> None:
        with self.lock:
            msg = self.validate_username(username) or self.validate_password(pw)
            if msg is not None:
                raise ValueError(msg)
            restriction = restriction or {}
            misc_data = {'allow_change_password_via_http': allow_change_password_via_http}
            self.conn.cursor().execute(
                'INSERT INTO users (name, pw, restriction, readonly, misc_data) VALUES (?, ?, ?, ?, ?)',
                (username, pw, serialize_restriction(restriction), ('y' if readonly else 'n'), json.dumps(misc_data)),
            )

    def remove_user(self, username: str) -> bool:
        with self.lock:
            self.conn.cursor().execute('DELETE FROM users WHERE name=?', (username,))
            return self.conn.changes() > 0

    @property
    def all_user_names(self) -> set[str]:
        with self.lock:
            return {x for (x,) in self.conn.cursor().execute('SELECT name FROM users')}

    @property
    def user_data(self) -> dict[str, UserData]:
        with self.lock:
            ans: dict[str, UserData] = {}
            for name, pw, restriction, readonly, misc_data in self.conn.cursor().execute('SELECT name,pw,restriction,readonly,misc_data FROM users'):
                ans[name] = create_user_data(pw, readonly.lower() == 'y', restriction, misc_data)
        return ans

    @user_data.setter
    def user_data(self, users: Mapping[str, UserData]) -> None:
        with self.lock, self.conn:
            c = self.conn.cursor()
            remove = self.all_user_names - set(users)
            if remove:
                c.executemany('DELETE FROM users WHERE name=?', [(n,) for n in remove])
            for name, data in users.items():
                res = serialize_restriction(data['restriction'])
                misc_data = json.dumps({'allow_change_password_via_http': bool(data.get('allow_change_password_via_http', True))})
                r = 'y' if data['readonly'] else 'n'
                c.execute(
                    'INSERT INTO USERS (name, pw, restriction, readonly, misc_data) VALUES (?, ?, ?, ?, ?) '
                    'ON CONFLICT DO UPDATE SET pw=?, restriction=?, readonly=?, misc_data=?',
                    (name, data['pw'], res, r, misc_data, data['pw'], res, r, misc_data),
                )
            self.refresh()

    def refresh(self) -> None:
        pass  # legacy compat

    def is_readonly(self, username: str | None) -> bool:
        with self.lock:
            for (readonly,) in self.conn.cursor().execute('SELECT readonly FROM users WHERE name=?', (username,)):
                return readonly == 'y'
            return False

    def set_readonly(self, username: str, value: bool) -> None:
        with self.lock:
            self.conn.cursor().execute('UPDATE users SET readonly=? WHERE name=?', ('y' if value else 'n', username))

    def change_password(self, username: str, pw: str) -> None:
        with self.lock:
            msg = self.validate_password(pw)
            if msg is not None:
                raise ValueError(msg)
            self.conn.cursor().execute('UPDATE users SET pw=? WHERE name=?', (pw, username))

    def restrictions(self, username: str | None) -> Restriction | None:
        with self.lock:
            for (restriction,) in self.conn.cursor().execute('SELECT restriction FROM users WHERE name=?', (username,)):
                return parse_restriction(restriction).copy()

    def allowed_library_names(self, username: str | None, all_library_names: Iterable[str]) -> set[str]:
        "Get allowed library names for specified user from set of all library names"
        r = self.restrictions(username)
        if r is None:
            return set()
        inc = r['allowed_library_names']
        exc = r['blocked_library_names']

        def check(n: str) -> bool:
            n = n.lower()
            return (not inc or n in inc) and n not in exc

        return {n for n in all_library_names if check(n)}

    def update_user_restrictions(self, username: str, restrictions: Restriction) -> None:
        if not isinstance(restrictions, dict):
            raise TypeError('restrictions must be a dict')
        with self.lock:
            self.conn.cursor().execute('UPDATE users SET restriction=? WHERE name=?', (serialize_restriction(restrictions), username))

    def library_restriction(self, username: str | None, library_path: str) -> str:
        r = self.restrictions(username)
        if r is None:
            return ''
        library_name = os.path.basename(library_path).lower()
        return r['library_restrictions'].get(library_name) or ''

    def misc_data(self, username: str) -> dict[str, object]:
        with self.lock:
            for (misc_data,) in self.conn.cursor().execute('SELECT misc_data FROM users WHERE name=?', (username,)):
                return json.loads(misc_data)
        return {}

    def is_allowed_to_change_password_via_http(self, username: str) -> bool:
        return bool(self.misc_data(username).get('allow_change_password_via_http', True))

    def set_allowed_to_change_password_via_http(self, username: str, allow: bool = True) -> None:
        with self.lock:
            md = self.misc_data(username)
            md['allow_change_password_via_http'] = allow
            self.conn.cursor().execute('UPDATE users SET misc_data=? WHERE name=?', (json.dumps(md), username))

    def kosync_progress(self, username: str, document: str, anonymous: bool = False) -> dict | None:
        """
        Return the reading position synced by KOReader for the specified document or None. Positions
        stored with anonymous=True, when authentication is disabled, are separate from those of users.
        """
        if anonymous:
            sql = 'SELECT progress,percentage,device,device_id,timestamp FROM kosync_anonymous_progress WHERE user=? AND document=?'
        else:
            sql = (
                'SELECT p.progress,p.percentage,p.device,p.device_id,p.timestamp FROM kosync_progress p'
                ' JOIN users u ON p.user_id=u.id WHERE u.name=? AND p.document=?'
            )
        with self.lock:
            for progress, percentage, device, device_id, timestamp in self.conn.cursor().execute(sql, (username, document)):
                ans = {'document': document, 'progress': progress, 'percentage': percentage, 'device': device, 'timestamp': timestamp}
                if device_id is not None:
                    ans['device_id'] = device_id
                return ans
        return None

    def set_kosync_progress(
        self,
        username: str,
        document: str,
        progress: str,
        percentage: float,
        device: str,
        device_id: str | None,
        timestamp: int,
        anonymous: bool = False,
    ) -> bool:
        """
        Store the reading position synced by KOReader for the specified document. Returns False if
        the user does not exist. Only the kosync_max_documents most recently synced documents are
        kept per user and in total for anonymous=True.
        """
        values = (document, progress, percentage, device, device_id, timestamp)
        with self.lock, self.conn:
            c = self.conn.cursor()
            if anonymous:
                table, where, key = 'kosync_anonymous_progress', '', ()
                c.execute(
                    'INSERT OR REPLACE INTO kosync_anonymous_progress (user, document, progress, percentage, device, device_id, timestamp)'
                    ' VALUES (?, ?, ?, ?, ?, ?, ?)',
                    (username,) + values,
                )
            else:
                for (user_id,) in c.execute('SELECT id FROM users WHERE name=?', (username,)):
                    break
                else:
                    return False
                table, where, key = 'kosync_progress', ' WHERE user_id=?', (user_id,)
                c.execute(
                    'INSERT OR REPLACE INTO kosync_progress (user_id, document, progress, percentage, device, device_id, timestamp)'
                    ' VALUES (?, ?, ?, ?, ?, ?, ?)',
                    key + values,
                )
            (count,) = next(c.execute(f'SELECT count(*) FROM {table}{where}', key))
            if count > self.kosync_max_documents:
                # Discard the least recently synced documents, replaced rows get a new rowid
                c.execute(
                    f'DELETE FROM {table} WHERE rowid IN (SELECT rowid FROM {table}{where} ORDER BY timestamp, rowid LIMIT ?)',
                    key + (count - self.kosync_max_documents,),
                )
        return True
