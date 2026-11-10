#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

import tempfile
import unittest

import apsw

from calibre.devices.kobo import bool_match, is_false_value, is_true_value
from calibre.devices.kobo.bookmark import Bookmark
from calibre.devices.kobo.db import row_factory
from calibre.devices.kobo.driver import KOBOTOUCH


class KoboTouchForTest(KOBOTOUCH):
    tolino: bool = False

    def isTolinoDevice(self) -> bool:
        return self.tolino

    @property
    def ignore_collections_names(self) -> list[str]:
        return []


class TestKoboBooleans(unittest.TestCase):
    def create_db(self) -> apsw.Connection:
        conn = apsw.Connection(':memory:')
        conn.execute('''
CREATE TABLE Shelf (CreationDate TEXT, Id TEXT, InternalName TEXT, LastModified TEXT, Name TEXT, Type TEXT,
    _IsDeleted BOOL, _IsVisible BOOL, _IsSynced BOOL, _SyncTime TEXT, LastAccessed TEXT, PRIMARY KEY(Id));
CREATE TABLE ShelfContent (ShelfName TEXT, ContentId TEXT, DateModified TEXT, _IsDeleted BOOL, _IsSynced BOOL,
    PRIMARY KEY(ShelfName, ContentId));
CREATE TABLE Activity (Id TEXT, Type TEXT);
-- Newer Kobo firmware stores integer booleans while rows written by older
-- firmware or calibre contain the strings 'true' and 'false'
INSERT INTO Shelf (Id, InternalName, Name, Type, _IsDeleted, _IsVisible, _IsSynced) VALUES
    ('1', 'text', 'text', 'UserTag', 'false', 'true', 'true'),
    ('2', 'int', 'int', 'UserTag', 0, 1, 1),
    ('3', 'deleted text', 'deleted text', 'UserTag', 'true', 'true', 'true'),
    ('4', 'deleted int', 'deleted int', 'UserTag', 1, 1, 1),
    ('5', 'empty synced', 'empty synced', 'UserTag', 0, 1, 1),
    ('6', 'empty unsynced', 'empty unsynced', 'UserTag', 0, 1, 0),
    ('7', 'only deleted members', 'only deleted members', 'UserTag', 0, 1, 1);
INSERT INTO ShelfContent (ShelfName, ContentId, _IsDeleted, _IsSynced) VALUES
    ('text', 'a', 'false', 'false'),
    ('int', 'a', 0, 0),
    ('int', 'b', 1, 0),
    ('only deleted members', 'a', 1, 0),
    ('only deleted members', 'b', 'true', 'false');
INSERT INTO Activity (Id, Type) VALUES ('text', 'Shelf'), ('int', 'Shelf'), ('deleted int', 'Shelf');
''')
        conn.row_trace = row_factory
        return conn

    def create_driver(self, tolino: bool = False) -> KoboTouchForTest:
        d = KoboTouchForTest(None)
        d.tolino = tolino
        d.dbversion = 222
        d.fwversion = (6, 0, 279225)
        return d

    def test_kobo_mixed_boolean_values(self) -> None:
        for tolino in (False, True):
            d = self.create_driver(tolino)
            conn = self.create_db()
            self.assertEqual(sorted(d.get_bookshelflist(conn)), ['empty synced', 'empty unsynced', 'int', 'only deleted members', 'text'], f'tolino: {tolino}')
            d.delete_empty_bookshelves(conn)
            self.assertEqual(sorted(d.get_bookshelflist(conn)), ['int', 'text'], f'tolino: {tolino}')
            remaining = {r['Name'] for r in conn.execute('SELECT Name FROM Shelf')}
            self.assertNotIn('empty unsynced', remaining)
            self.assertIn('empty synced', remaining)
            activity = sorted(r['Id'] for r in conn.execute('SELECT Id FROM Activity'))
            self.assertEqual(activity, ['int', 'text'])

    def test_kobo_bool_match(self) -> None:
        conn = apsw.Connection(':memory:')
        conn.execute('CREATE TABLE t (x BOOL); INSERT INTO t VALUES (0), (1), (?), (?), (NULL)', ('false', 'true'))

        def count(where: str) -> int:
            return conn.execute(f'SELECT COUNT(*) FROM t WHERE {where}').fetchall()[0][0]

        self.assertEqual(count(bool_match('x', False)), 2)
        self.assertEqual(count(bool_match('x', True)), 2)
        self.assertEqual(count('NOT ' + bool_match('x', True)), 2)
        # The Python helpers must agree with the SQL condition
        for (x,) in conn.execute('SELECT x FROM t'):
            for value, func in ((True, is_true_value), (False, is_false_value)):
                in_sql = conn.execute(f'SELECT COUNT(*) FROM (SELECT ? AS x) WHERE {bool_match("x", value)}', (x,)).fetchall()[0][0] == 1
                if x is not None:
                    self.assertEqual(func(x), in_sql, f'{func.__name__}({x!r})')
        self.assertTrue(is_true_value('1'))
        self.assertTrue(is_false_value('0'))
        self.assertFalse(is_true_value('1') and is_false_value('1'))

    def test_kobo_bookmark_hidden(self) -> None:
        conn = apsw.Connection(':memory:')
        conn.execute('''
CREATE TABLE content (ContentID TEXT, BookID TEXT, BookTitle TEXT, Title TEXT, VolumeIndex INTEGER, ___NumPages INTEGER,
    MimeType TEXT, ContentType INTEGER, DateLastRead TEXT, ___PercentRead INTEGER, ReadStatus INTEGER);
CREATE TABLE Bookmark (BookmarkID TEXT, VolumeID TEXT, ContentID TEXT, Text TEXT, Annotation TEXT, ChapterProgress REAL,
    StartContainerChildIndex INTEGER, StartOffset INTEGER, Hidden BOOL);
INSERT INTO Bookmark VALUES
    ('1', 'book', 'book', 'text false', '', 0.1, 1, 1, 'false'),
    ('2', 'book', 'book', 'int false', '', 0.2, 1, 1, 0),
    ('3', 'book', 'book', 'text true', '', 0.3, 1, 1, 'true'),
    ('4', 'book', 'book', 'int true', '', 0.4, 1, 1, 1);
''')
        conn.row_trace = row_factory
        with tempfile.NamedTemporaryFile(suffix='.epub') as f:
            bm = Bookmark(conn, 'book', f.name, 1, 'epub', 'epub')
        assert bm.user_notes is not None
        self.assertEqual(sorted(str(n['text']) for n in bm.user_notes.values()), ['int false', 'text false'])


def find_tests() -> unittest.TestSuite:
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestKoboBooleans)


if __name__ == '__main__':
    from calibre.utils.run_tests import run_cli

    run_cli(find_tests())
