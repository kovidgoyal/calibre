#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING

from calibre.utils.resources import get_path as P

if TYPE_CHECKING:
    from calibre.db.backend import Connection


class SchemaUpgrade:
    def __init__(self, conn: Connection, triggers_sql: str) -> None:
        self.conn: Connection | None = conn
        conn.execute('BEGIN EXCLUSIVE TRANSACTION')
        try:
            if self.user_version == 0:
                notes_sqlite = P('notes_sqlite.sql', data=True, allow_user_override=False).decode('utf-8')
                conn.execute(notes_sqlite)
            while True:
                uv = self.user_version
                meth = getattr(self, f'upgrade_version_{uv}', None)
                if meth is None:
                    break
                print(f'Upgrading Notes database to version {uv + 1}...')
                meth()
                self.user_version = uv + 1
            conn.execute(triggers_sql)
        except Exception, BaseException:
            conn.execute('ROLLBACK')
            raise
        else:
            conn.execute('COMMIT')
        self.conn = None

    @property
    def user_version(self) -> int:
        assert self.conn is not None
        return self.conn.get('PRAGMA notes_db.user_version', all=False) or 0  # ty: ignore[invalid-return-type]

    @user_version.setter
    def user_version(self, val: int) -> None:
        assert self.conn is not None
        self.conn.execute(f'PRAGMA notes_db.user_version={val}')
