#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import os
from .schema_upgrade import SchemaUpgrade


# TODO: db dump+restore
# TODO: calibre export/import
# TODO: check library and vacuuming of fts db


class FTS:

    def __init__(self, get_connection):
        self.get_connection = get_connection
        conn = self.get_connection()
        main_db_path = os.path.abspath(conn.db_filename('main'))
        self.dbpath = os.path.join(os.path.dirname(main_db_path), 'full-text-search.db')
        conn.execute(f'ATTACH DATABASE "{self.dbpath}" AS fts_db')
        SchemaUpgrade(conn)
