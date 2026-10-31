#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

import json
import os
import tempfile
from hashlib import md5
from typing import TYPE_CHECKING

from calibre.srv.tests.base import LibraryBaseTest

if TYPE_CHECKING:
    from http.client import HTTPConnection


def key_for(password: str) -> str:
    return md5(password.encode('utf-8')).hexdigest()


class KOSyncTest(LibraryBaseTest):
    def request(
        self, conn: HTTPConnection, path: str, method: str = 'GET', user: str | None = None, key: str | None = None, data: dict | None = None
    ) -> tuple[int, dict]:
        # Send requests the way KOReader does
        headers = {'Accept': 'application/vnd.koreader.v1+json'}
        if user is not None:
            headers['x-auth-user'] = user
        if key is not None:
            headers['x-auth-key'] = key
        if data is not None:
            headers['Content-Type'] = 'application/json'
            data = json.dumps(data).encode('utf-8')
        conn.request(method, '/kosync' + path, headers=headers, body=data)
        r = conn.getresponse()
        return r.status, json.loads(r.read())

    def test_kosync(self) -> None:
        with self.create_server(auth=True, auth_mode='basic') as server:
            um = server.handler.ctx.user_manager
            um.add_user('alice', 'secret')
            um.add_user('bob', 'other')
            conn = server.connect()
            alice = {'user': 'alice', 'key': key_for('secret')}
            bob = {'user': 'bob', 'key': key_for('other')}

            self.ae(self.request(conn, '/healthcheck'), (200, {'state': 'OK'}))
            status, data = self.request(conn, '/users/create', 'POST', data={'username': 'eve', 'password': key_for('x')})
            self.ae((status, data['code']), (402, 2005))
            self.assertFalse(um.has_user('eve'))

            self.ae(self.request(conn, '/users/auth', **alice), (200, {'authorized': 'OK'}))
            self.ae(self.request(conn, '/users/auth', user='alice', key=key_for('secret').upper())[0], 200)
            for creds in ({'user': 'alice', 'key': key_for('wrong')}, {'user': 'nobody', 'key': key_for('secret')}, {'user': 'alice'}, {}):
                with self.subTest(creds=creds):
                    self.ae(self.request(conn, '/users/auth', **creds), (401, {'code': 2001, 'message': 'Unauthorized'}))
                    self.ae(self.request(conn, '/syncs/progress/doc1', **creds)[0], 401)
                    self.ae(self.request(conn, '/syncs/progress', 'PUT', data={'document': 'doc1'}, **creds)[0], 401)

            self.ae(self.request(conn, '/syncs/progress/0123abcdef', **alice), (200, {}))
            progress = {
                'document': '0123abcdef',
                'progress': '/body/DocFragment[12]/body/p[3]/text().0',
                'percentage': 0.42,
                'device': 'Kobo',
                'device_id': 'D1',
            }
            status, data = self.request(conn, '/syncs/progress', 'PUT', data=dict(progress, metadata={'title': 'A book'}), **alice)
            self.ae(status, 200)
            self.ae(data['document'], '0123abcdef')
            timestamp = data['timestamp']
            self.assertIsInstance(timestamp, int)
            self.ae(self.request(conn, '/syncs/progress/0123abcdef', **alice), (200, dict(progress, timestamp=timestamp)))
            # Progress is per user
            self.ae(self.request(conn, '/syncs/progress/0123abcdef', **bob), (200, {}))
            # Page numbers for PDFs are returned as strings and device_id is optional
            status, data = self.request(
                conn, '/syncs/progress', 'PUT', data={'document': 'pdf_1', 'progress': 17, 'percentage': '0.5', 'device': 'Kindle'}, **bob
            )
            self.ae(status, 200)
            self.ae(
                self.request(conn, '/syncs/progress/pdf_1', **bob)[1],
                {'document': 'pdf_1', 'progress': '17', 'percentage': 0.5, 'device': 'Kindle', 'timestamp': data['timestamp']},
            )

            for body, code in (
                ({'progress': 'x', 'percentage': 0.1, 'device': 'd'}, 2004),
                ({'document': '', 'progress': 'x', 'percentage': 0.1, 'device': 'd'}, 2004),
                ({'document': 'a:b', 'progress': 'x', 'percentage': 0.1, 'device': 'd'}, 2004),
                ({'document': 'a-b', 'progress': 'x', 'percentage': 0.1, 'device': 'd'}, 2007),
                ({'document': 'doc', 'percentage': 0.1, 'device': 'd'}, 2003),
                ({'document': 'doc', 'progress': 'x', 'percentage': 'half', 'device': 'd'}, 2003),
                ({'document': 'doc', 'progress': 'x', 'percentage': 0.1}, 2003),
                ({'document': 'doc', 'progress': 'x', 'percentage': 'nan', 'device': 'd'}, 2003),
                ({'document': 'doc', 'progress': 'x', 'percentage': float('nan'), 'device': 'd'}, 2003),
                ({'document': 'doc', 'progress': 'x', 'percentage': 'inf', 'device': 'd'}, 2003),
                ({'document': 'doc', 'progress': 'x', 'percentage': 10**400, 'device': 'd'}, 2003),
                ({'document': 'doc', 'progress': 'x', 'percentage': 1.5, 'device': 'd'}, 2003),
                ({'document': 'doc', 'progress': 'x', 'percentage': -0.1, 'device': 'd'}, 2003),
                ({'document': 'doc', 'progress': {'a': 1}, 'percentage': 0.1, 'device': 'd'}, 2003),
                ({'document': 'doc', 'progress': True, 'percentage': 0.1, 'device': 'd'}, 2003),
                ({'document': 'doc', 'progress': 'x' * 5000, 'percentage': 0.1, 'device': 'd'}, 2003),
                ({'document': 'doc', 'progress': 'x', 'percentage': 0.1, 'device': ['d']}, 2003),
                ({'document': 'doc', 'progress': 'x', 'percentage': 0.1, 'device': 'd', 'device_id': 1}, 2003),
                ({'document': 'd' * 5000, 'progress': 'x', 'percentage': 0.1, 'device': 'd'}, 2003),
                (['doc'], 2003),
            ):
                with self.subTest(body=body):
                    status, data = self.request(conn, '/syncs/progress', 'PUT', data=body, **alice)
                    self.ae((status, data['code']), (403, code))
            # Non-ASCII keys are rejected, not a server error
            self.ae(self.request(conn, '/users/auth', user='alice', key='\xe9')[0], 401)
            self.ae(self.request(conn, '/users/auth', user='alice', key='\xe9'.encode('utf-8'))[0], 401)

            # Readonly users cannot store progress
            um.set_readonly('bob', True)
            status, data = self.request(conn, '/syncs/progress', 'PUT', data={'document': 'pdf_1', 'progress': 1, 'percentage': 0.1, 'device': 'd'}, **bob)
            self.ae((status, data['code']), (403, 2001))
            self.ae(self.request(conn, '/syncs/progress/pdf_1', **bob)[1]['progress'], '17')

            # Removing a user removes their progress
            um.remove_user('alice')
            um.add_user('alice', 'secret')
            self.ae(self.request(conn, '/syncs/progress/0123abcdef', **alice), (200, {}))

    def test_kosync_bans(self) -> None:
        from calibre.srv.tests.ajax import make_request

        with self.create_server(auth=True, auth_mode='basic', ban_for=1, ban_after=2) as server:
            server.handler.ctx.user_manager.add_user('alice', 'secret')
            conn = server.connect()
            for i in range(2):
                self.ae(self.request(conn, '/users/auth', user='alice', key=key_for(f'guess{i}'))[0], 401)
            # Banned, even with the correct key
            status, data = self.request(conn, '/users/auth', user='alice', key=key_for('secret'))
            self.ae((status, data['code']), (403, 2001))
            self.ae(self.request(conn, '/syncs/progress/doc', user='alice', key=key_for('secret'))[0], 403)
            # Normal logins are not banned by failed sync logins
            r, _ = make_request(conn, '/library-info', username='alice', password='secret')
            self.ae(r.status, 200)

        with self.create_server(auth=True, auth_mode='basic', ban_for=1, ban_after=2) as server:
            server.handler.ctx.user_manager.add_user('alice', 'secret')
            conn = server.connect()
            for i in range(2):
                r, _ = make_request(conn, '/library-info', username='alice', password=f'guess{i}')
                self.ae(r.status, 401)
            # Bans from normal logins apply to sync logins
            status, data = self.request(conn, '/users/auth', user='alice', key=key_for('secret'))
            self.ae((status, data['code']), (403, 2001))

        from types import SimpleNamespace

        from calibre.srv.kosync import ban_key

        # The remote address is None when the peer address of the socket is unavailable
        self.assertTrue(ban_key(SimpleNamespace(remote_addr=None)).startswith('kosync:'))

    def test_kosync_without_auth(self) -> None:
        with self.create_server() as server:
            conn = server.connect()
            creds = {'user': 'anyone', 'key': key_for('anything')}
            self.ae(self.request(conn, '/users/auth', **creds), (200, {'authorized': 'OK'}))
            self.ae(self.request(conn, '/users/auth')[0], 401)
            # Anonymous users can only make changes from trusted IP addresses
            progress = {'document': 'doc', 'progress': 'p', 'percentage': 0.1, 'device': 'd'}
            status, data = self.request(conn, '/syncs/progress', 'PUT', data=progress, **creds)
            self.ae((status, data['code']), (403, 2001))
            self.ae(self.request(conn, '/syncs/progress/doc', **creds), (200, {}))
        with self.create_server(local_write=True) as server:
            um = server.handler.ctx.user_manager
            um.add_user('anyone', 'secret')
            conn = server.connect()
            self.ae(self.request(conn, '/syncs/progress', 'PUT', data=progress, **creds)[0], 200)
            self.ae(self.request(conn, '/syncs/progress/doc', **creds)[1]['progress'], 'p')
            # Positions synced without authentication are separate from those of users
            self.ae(um.kosync_progress('anyone', 'doc', anonymous=True)['progress'], 'p')
            self.assertIsNone(um.kosync_progress('anyone', 'doc'))

    def test_kosync_storage(self) -> None:
        import apsw

        from calibre.srv.users import UserManager

        with tempfile.TemporaryDirectory() as tdir:
            path = os.path.join(tdir, 'users.sqlite')
            um = UserManager(path)
            um.add_user('alice', 'secret')
            um.add_user('bob', 'secret')

            def positions(username: str, anonymous: bool = False) -> dict[str, object]:
                return {d: p['progress'] for d in ('d0', 'd1', 'd2', 'd3') if (p := um.kosync_progress(username, d, anonymous=anonymous))}

            # Users and anonymous positions are separate even for the same name
            self.assertTrue(um.set_kosync_progress('alice', 'd0', 'user', 0.5, 'dev', None, 1))
            self.assertTrue(um.set_kosync_progress('alice', 'd0', 'anon', 0.5, 'dev', None, 1, anonymous=True))
            self.ae(positions('alice'), {'d0': 'user'})
            self.ae(positions('alice', anonymous=True), {'d0': 'anon'})
            # Positions cannot be stored for users that do not exist
            self.assertFalse(um.set_kosync_progress('nobody', 'd0', 'p', 0.5, 'dev', None, 1))
            self.assertTrue(um.set_kosync_progress('nobody', 'd0', 'p', 0.5, 'dev', None, 1, anonymous=True))

            # Only the most recently synced documents are kept, per user
            um.kosync_max_documents = 2
            self.assertTrue(um.set_kosync_progress('alice', 'd1', 'user', 0.5, 'dev', None, 2))
            self.assertTrue(um.set_kosync_progress('bob', 'd1', 'user', 0.5, 'dev', None, 2))
            # Updating a document makes it the most recent, even with the same timestamp
            self.assertTrue(um.set_kosync_progress('alice', 'd0', 'user2', 0.5, 'dev', None, 2))
            self.assertTrue(um.set_kosync_progress('alice', 'd2', 'user', 0.5, 'dev', None, 2))
            self.ae(positions('alice'), {'d0': 'user2', 'd2': 'user'})
            self.ae(positions('bob'), {'d1': 'user'})
            # and in total for anonymous positions
            self.assertTrue(um.set_kosync_progress('other', 'd3', 'p', 0.5, 'dev', None, 3, anonymous=True))
            self.ae(positions('alice', anonymous=True), {})
            self.ae(positions('nobody', anonymous=True), {'d0': 'p'})
            self.ae(positions('other', anonymous=True), {'d3': 'p'})

            # Positions are removed with their user, so a new user cannot get them, even if the id is reused
            um.remove_user('bob')
            um.add_user('bob', 'secret')
            self.ae(positions('bob'), {})
            # Also when deleted by versions of calibre that do not enable foreign keys
            um.conn.close()
            conn = apsw.Connection(path)
            conn.cursor().execute("DELETE FROM users WHERE name='alice'")
            self.ae(next(conn.cursor().execute('SELECT count(*) FROM kosync_progress'))[0], 0)
            self.ae(next(conn.cursor().execute('SELECT count(*) FROM kosync_anonymous_progress'))[0], 2)
            conn.close()

    def test_kosync_schema_upgrade(self) -> None:
        import apsw

        from calibre.srv.users import UserManager

        with tempfile.TemporaryDirectory() as tdir:
            path = os.path.join(tdir, 'users.sqlite')
            # Create a user database as written by older versions of calibre
            conn = apsw.Connection(path)
            conn.cursor().execute('''
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, pw TEXT NOT NULL,
                    timestamp TEXT DEFAULT CURRENT_TIMESTAMP, session_data TEXT NOT NULL DEFAULT "{}",
                    restriction TEXT NOT NULL DEFAULT "{}", readonly TEXT NOT NULL DEFAULT "n",
                    misc_data TEXT NOT NULL DEFAULT "{}", UNIQUE(name));
                INSERT INTO users (name, pw) VALUES ('old', 'pw');
                PRAGMA user_version=1;
            ''')
            conn.close()
            um = UserManager(path)
            self.ae(um.get('old'), 'pw')
            um.set_kosync_progress('old', 'doc', 'p', 0.5, 'dev', None, 1)
            self.ae(um.kosync_progress('old', 'doc'), {'document': 'doc', 'progress': 'p', 'percentage': 0.5, 'device': 'dev', 'timestamp': 1})
            self.ae(next(um.conn.cursor().execute('PRAGMA user_version'))[0], 2)
            self.ae(next(um.conn.cursor().execute('PRAGMA foreign_keys'))[0], 1)
            um.conn.close()
