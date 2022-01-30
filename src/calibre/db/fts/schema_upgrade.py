#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


class SchemaUpgrade:

    def __init__(self, conn):
        self.conn = conn
        conn.execute('BEGIN EXCLUSIVE TRANSACTION')
        try:
            while True:
                uv = self.user_version
                meth = getattr(self, f'upgrade_version_{uv}', None)
                if meth is None:
                    break
                print(f'Upgrading FTS database to version {uv+1}...')
                meth()
                self.user_version = uv + 1
        except (Exception, BaseException):
            conn.execute('ROLLBACK')
            raise
        else:
            conn.execute('COMMIT')
        self.conn = None

    @property
    def user_version(self):
        return self.conn.get('PRAGMA fts_db.user_version', all=False) or 0

    @user_version.setter
    def user_version(self, val):
        self.conn.execute(f'PRAGMA fts_db.user_version={val}')
