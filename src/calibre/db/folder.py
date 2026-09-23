#!/usr/bin/env python
# License: GPLv3

import re


def initialize_library_paths(db):
    """Add the fork's optional field without consuming an upstream schema version.

    Opening a library never moves books. Migrate the earlier custom column in
    the same transaction, then let normal custom-column cleanup remove it.
    """
    with db.conn:
        db.execute('''
            CREATE TABLE IF NOT EXISTS library_paths (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE,
                link TEXT NOT NULL DEFAULT '');
            CREATE TABLE IF NOT EXISTS books_library_paths_link (
                id INTEGER PRIMARY KEY, book INTEGER NOT NULL UNIQUE,
                library_path INTEGER NOT NULL);
            CREATE INDEX IF NOT EXISTS library_paths_name_idx ON library_paths(name);
            CREATE INDEX IF NOT EXISTS books_library_paths_link_path_idx
                ON books_library_paths_link(library_path);
            CREATE TRIGGER IF NOT EXISTS library_paths_book_delete
                AFTER DELETE ON books BEGIN
                DELETE FROM books_library_paths_link WHERE book=OLD.id;
            END;
        ''')
        rows = list(db.execute("SELECT id FROM custom_columns WHERE label='library_path' "
                               "AND datatype='text' AND is_multiple=0 AND normalized=1 AND mark_for_delete=0"))
        for (num,) in rows:
            values = [(bid, normalize_folder(val)) for bid, val in db.execute(
                f'SELECT l.book,c.value FROM books_custom_column_{num}_link l '
                f'JOIN custom_column_{num} c ON c.id=l.value')]
            for bid, val in values:
                if not val:
                    continue
                found = list(db.execute('SELECT id FROM library_paths WHERE name=?', (val,)))
                if found:
                    item = found[0][0]
                else:
                    db.execute('INSERT INTO library_paths(name) VALUES(?)', (val,))
                    item = db.conn.last_insert_rowid()
                db.execute('INSERT OR IGNORE INTO books_library_paths_link(book,library_path) VALUES(?,?)', (bid, item))
            db.execute('UPDATE custom_columns SET mark_for_delete=1 WHERE id=?', (num,))
            # Existing OPF backups must be rewritten in the compact format.
            db.execute('INSERT OR IGNORE INTO metadata_dirtied(book) SELECT id FROM books')

        if rows:
            def migrate_pref(value):
                if isinstance(value, str):
                    return value.replace('#library_path', 'library_path')
                if isinstance(value, dict):
                    return {migrate_pref(k): migrate_pref(v) for k, v in value.items()}
                if isinstance(value, (list, tuple)):
                    return [migrate_pref(v) for v in value]
                return value
            for key in tuple(db.prefs):
                old = db.prefs[key]
                new = migrate_pref(old)
                if old != new:
                    db.prefs[key] = new


def normalize_folder(value):
    """A portable relative directory prefix, never a path outside the library."""
    if value is None:
        return ''
    if not isinstance(value, str):
        raise ValueError('Folder must be a single text value')
    value = value.strip().replace('\\', '/')
    if not value:
        return ''
    parts = value.split('/')
    for part in parts:
        if (not part or part in {'.', '..'} or part != part.strip() or part.endswith('.')
                or any(ord(c) < 32 or c in '<>:"|?*' for c in part)
                or re.match(r'(?i)^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)', part)
                or part.startswith('.') or re.search(r' \(\d+\)$', part)
                or len(part.encode('utf-8')) > 255):
            raise ValueError(f'Invalid Folder path component: {part!r}')
    return '/'.join(parts)
