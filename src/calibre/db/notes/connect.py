#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import os

from calibre.constants import iswindows

from ..constants import NOTES_DIR_NAME
from .schema_upgrade import SchemaUpgrade


class Notes:

    def __init__(self, backend):
        conn = backend.get_connection()
        libdir = os.path.dirname(os.path.abspath(conn.db_filename('main')))
        notes_dir = os.path.join(libdir, NOTES_DIR_NAME)
        if not os.path.exists(notes_dir):
            os.makedirs(notes_dir, exist_ok=True)
            if iswindows:
                import calibre_extensions.winutil as winutil
                winutil.set_file_attributes(notes_dir, winutil.FILE_ATTRIBUTE_HIDDEN | winutil.FILE_ATTRIBUTE_NOT_CONTENT_INDEXED)
        dbpath = os.path.join(notes_dir, 'notes.db')
        conn.execute("ATTACH DATABASE ? AS notes_db", (dbpath,))
        self.allowed_fields = set()
        triggers = []
        for table in backend.tables.values():
            m = table.metadata
            if not table.supports_notes or m.get('datatype') == 'rating':
                continue
            self.allowed_fields.add(table.name)
            triggers.append(
                f'CREATE TEMP TRIGGER IF NOT EXISTS notes_db_{table.name.replace("#", "_")}_deleted_trigger AFTER DELETE ON main.{m["table"]} BEGIN\n'
                f"  DELETE FROM notes WHERE colname = '{table.name}' AND item = OLD.id;\n"
                'END;'
            )
        SchemaUpgrade(conn, '\n'.join(triggers))
        conn.notes_dbpath = dbpath
