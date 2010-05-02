#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

class SchemaUpgrade(object):

    def __init__(self):
        # Upgrade database
        while True:
            uv = self.user_version
            meth = getattr(self, 'upgrade_version_%d'%uv, None)
            if meth is None:
                break
            else:
                print 'Upgrading database to version %d...'%(uv+1)
                meth()
                self.user_version = uv+1


    def upgrade_version_1(self):
        '''
        Normalize indices.
        '''
        self.conn.executescript('''\
        DROP INDEX authors_idx;
        CREATE INDEX authors_idx ON books (author_sort COLLATE NOCASE, sort COLLATE NOCASE);
        DROP INDEX series_idx;
        CREATE INDEX series_idx ON series (name COLLATE NOCASE);
        CREATE INDEX series_sort_idx ON books (series_index, id);
        ''')

    def upgrade_version_2(self):
        ''' Fix Foreign key constraints for deleting from link tables. '''
        script = '''\
        DROP TRIGGER IF EXISTS fkc_delete_books_%(ltable)s_link;
        CREATE TRIGGER fkc_delete_on_%(table)s
        BEFORE DELETE ON %(table)s
        BEGIN
            SELECT CASE
                WHEN (SELECT COUNT(id) FROM books_%(ltable)s_link WHERE %(ltable_col)s=OLD.id) > 0
                THEN RAISE(ABORT, 'Foreign key violation: %(table)s is still referenced')
            END;
        END;
        DELETE FROM %(table)s WHERE (SELECT COUNT(id) FROM books_%(ltable)s_link WHERE %(ltable_col)s=%(table)s.id) < 1;
        '''
        self.conn.executescript(script%dict(ltable='authors', table='authors', ltable_col='author'))
        self.conn.executescript(script%dict(ltable='publishers', table='publishers', ltable_col='publisher'))
        self.conn.executescript(script%dict(ltable='tags', table='tags', ltable_col='tag'))
        self.conn.executescript(script%dict(ltable='series', table='series', ltable_col='series'))

    def upgrade_version_3(self):
        ' Add path to result cache '
        self.conn.executescript('''
        DROP VIEW meta;
        CREATE VIEW meta AS
        SELECT id, title,
               (SELECT concat(name) FROM authors WHERE authors.id IN (SELECT author from books_authors_link WHERE book=books.id)) authors,
               (SELECT name FROM publishers WHERE publishers.id IN (SELECT publisher from books_publishers_link WHERE book=books.id)) publisher,
               (SELECT rating FROM ratings WHERE ratings.id IN (SELECT rating from books_ratings_link WHERE book=books.id)) rating,
               timestamp,
               (SELECT MAX(uncompressed_size) FROM data WHERE book=books.id) size,
               (SELECT concat(name) FROM tags WHERE tags.id IN (SELECT tag from books_tags_link WHERE book=books.id)) tags,
               (SELECT text FROM comments WHERE book=books.id) comments,
               (SELECT name FROM series WHERE series.id IN (SELECT series FROM books_series_link WHERE book=books.id)) series,
               series_index,
               sort,
               author_sort,
               (SELECT concat(format) FROM data WHERE data.book=books.id) formats,
               isbn,
               path
        FROM books;
        ''')

    def upgrade_version_4(self):
        'Rationalize books table'
        self.conn.executescript('''
        BEGIN TRANSACTION;
        CREATE TEMPORARY TABLE
        books_backup(id,title,sort,timestamp,series_index,author_sort,isbn,path);
        INSERT INTO books_backup SELECT id,title,sort,timestamp,series_index,author_sort,isbn,path FROM books;
        DROP TABLE books;
        CREATE TABLE books ( id      INTEGER PRIMARY KEY AUTOINCREMENT,
                             title     TEXT NOT NULL DEFAULT 'Unknown' COLLATE NOCASE,
                             sort      TEXT COLLATE NOCASE,
                             timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                             pubdate   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                             series_index REAL NOT NULL DEFAULT 1.0,
                             author_sort TEXT COLLATE NOCASE,
                             isbn TEXT DEFAULT "" COLLATE NOCASE,
                             lccn TEXT DEFAULT "" COLLATE NOCASE,
                             path TEXT NOT NULL DEFAULT "",
                             flags INTEGER NOT NULL DEFAULT 1
                        );
        INSERT INTO
            books (id,title,sort,timestamp,pubdate,series_index,author_sort,isbn,path)
            SELECT id,title,sort,timestamp,timestamp,series_index,author_sort,isbn,path FROM books_backup;
        DROP TABLE books_backup;

        DROP VIEW meta;
        CREATE VIEW meta AS
        SELECT id, title,
               (SELECT concat(name) FROM authors WHERE authors.id IN (SELECT author from books_authors_link WHERE book=books.id)) authors,
               (SELECT name FROM publishers WHERE publishers.id IN (SELECT publisher from books_publishers_link WHERE book=books.id)) publisher,
               (SELECT rating FROM ratings WHERE ratings.id IN (SELECT rating from books_ratings_link WHERE book=books.id)) rating,
               timestamp,
               (SELECT MAX(uncompressed_size) FROM data WHERE book=books.id) size,
               (SELECT concat(name) FROM tags WHERE tags.id IN (SELECT tag from books_tags_link WHERE book=books.id)) tags,
               (SELECT text FROM comments WHERE book=books.id) comments,
               (SELECT name FROM series WHERE series.id IN (SELECT series FROM books_series_link WHERE book=books.id)) series,
               series_index,
               sort,
               author_sort,
               (SELECT concat(format) FROM data WHERE data.book=books.id) formats,
               isbn,
               path,
               lccn,
               pubdate,
               flags
        FROM books;
        ''')

    def upgrade_version_5(self):
        'Update indexes/triggers for new books table'
        self.conn.executescript('''
        BEGIN TRANSACTION;
        CREATE INDEX authors_idx ON books (author_sort COLLATE NOCASE);
        CREATE INDEX books_idx ON books (sort COLLATE NOCASE);
        CREATE TRIGGER books_delete_trg
            AFTER DELETE ON books
            BEGIN
                DELETE FROM books_authors_link WHERE book=OLD.id;
                DELETE FROM books_publishers_link WHERE book=OLD.id;
                DELETE FROM books_ratings_link WHERE book=OLD.id;
                DELETE FROM books_series_link WHERE book=OLD.id;
                DELETE FROM books_tags_link WHERE book=OLD.id;
                DELETE FROM data WHERE book=OLD.id;
                DELETE FROM comments WHERE book=OLD.id;
                DELETE FROM conversion_options WHERE book=OLD.id;
        END;
        CREATE TRIGGER books_insert_trg
            AFTER INSERT ON books
            BEGIN
            UPDATE books SET sort=title_sort(NEW.title) WHERE id=NEW.id;
        END;
        CREATE TRIGGER books_update_trg
            AFTER UPDATE ON books
            BEGIN
            UPDATE books SET sort=title_sort(NEW.title) WHERE id=NEW.id;
        END;

        UPDATE books SET sort=title_sort(title) WHERE sort IS NULL;

        END TRANSACTION;
        '''
        )


    def upgrade_version_6(self):
        'Show authors in order'
        self.conn.executescript('''
        BEGIN TRANSACTION;
        DROP VIEW meta;
        CREATE VIEW meta AS
        SELECT id, title,
               (SELECT sortconcat(bal.id, name) FROM books_authors_link AS bal JOIN authors ON(author = authors.id) WHERE book = books.id) authors,
               (SELECT name FROM publishers WHERE publishers.id IN (SELECT publisher from books_publishers_link WHERE book=books.id)) publisher,
               (SELECT rating FROM ratings WHERE ratings.id IN (SELECT rating from books_ratings_link WHERE book=books.id)) rating,
               timestamp,
               (SELECT MAX(uncompressed_size) FROM data WHERE book=books.id) size,
               (SELECT concat(name) FROM tags WHERE tags.id IN (SELECT tag from books_tags_link WHERE book=books.id)) tags,
               (SELECT text FROM comments WHERE book=books.id) comments,
               (SELECT name FROM series WHERE series.id IN (SELECT series FROM books_series_link WHERE book=books.id)) series,
               series_index,
               sort,
               author_sort,
               (SELECT concat(format) FROM data WHERE data.book=books.id) formats,
               isbn,
               path,
               lccn,
               pubdate,
               flags
        FROM books;
        END TRANSACTION;
        ''')

    def upgrade_version_7(self):
        'Add uuid column'
        self.conn.executescript('''
        BEGIN TRANSACTION;
        ALTER TABLE books ADD COLUMN uuid TEXT;
        DROP TRIGGER IF EXISTS books_insert_trg;
        DROP TRIGGER IF EXISTS books_update_trg;
        UPDATE books SET uuid=uuid4();

        CREATE TRIGGER books_insert_trg AFTER INSERT ON books
        BEGIN
            UPDATE books SET sort=title_sort(NEW.title),uuid=uuid4() WHERE id=NEW.id;
        END;

        CREATE TRIGGER books_update_trg AFTER UPDATE ON books
        BEGIN
            UPDATE books SET sort=title_sort(NEW.title) WHERE id=NEW.id;
        END;

        DROP VIEW meta;
        CREATE VIEW meta AS
        SELECT id, title,
               (SELECT sortconcat(bal.id, name) FROM books_authors_link AS bal JOIN authors ON(author = authors.id) WHERE book = books.id) authors,
               (SELECT name FROM publishers WHERE publishers.id IN (SELECT publisher from books_publishers_link WHERE book=books.id)) publisher,
               (SELECT rating FROM ratings WHERE ratings.id IN (SELECT rating from books_ratings_link WHERE book=books.id)) rating,
               timestamp,
               (SELECT MAX(uncompressed_size) FROM data WHERE book=books.id) size,
               (SELECT concat(name) FROM tags WHERE tags.id IN (SELECT tag from books_tags_link WHERE book=books.id)) tags,
               (SELECT text FROM comments WHERE book=books.id) comments,
               (SELECT name FROM series WHERE series.id IN (SELECT series FROM books_series_link WHERE book=books.id)) series,
               series_index,
               sort,
               author_sort,
               (SELECT concat(format) FROM data WHERE data.book=books.id) formats,
               isbn,
               path,
               lccn,
               pubdate,
               flags,
               uuid
        FROM books;

        END TRANSACTION;
        ''')

    def upgrade_version_8(self):
        'Add Tag Browser views'
        def create_tag_browser_view(table_name, column_name):
            self.conn.executescript('''
                DROP VIEW IF EXISTS tag_browser_{tn};
                CREATE VIEW tag_browser_{tn} AS SELECT
                    id,
                    name,
                    (SELECT COUNT(id) FROM books_{tn}_link WHERE {cn}={tn}.id) count
                FROM {tn};
                '''.format(tn=table_name, cn=column_name))

        for tn in ('authors', 'tags', 'publishers', 'series'):
            cn = tn[:-1]
            if tn == 'series':
                cn = tn
            create_tag_browser_view(tn, cn)

    def upgrade_version_9(self):
        'Add custom columns'
        self.conn.executescript('''
                CREATE TABLE custom_columns (
                    id       INTEGER PRIMARY KEY AUTOINCREMENT,
                    label    TEXT NOT NULL,
                    name     TEXT NOT NULL,
                    datatype TEXT NOT NULL,
                    mark_for_delete   BOOL DEFAULT 0 NOT NULL,
                    editable BOOL DEFAULT 1 NOT NULL,
                    display  TEXT DEFAULT "{}" NOT NULL,
                    is_multiple BOOL DEFAULT 0 NOT NULL,
                    normalized BOOL NOT NULL,
                    UNIQUE(label)
                );
                CREATE INDEX custom_columns_idx ON custom_columns (label);
                CREATE INDEX IF NOT EXISTS formats_idx ON data (format);
        ''')

    def upgrade_version_10(self):
        'Add restricted Tag Browser views'
        def create_tag_browser_view(table_name, column_name, view_column_name):
            script = ('''
                DROP VIEW IF EXISTS tag_browser_filtered_{tn};
                CREATE VIEW tag_browser_filtered_{tn} AS SELECT
                    id,
                    {vcn},
                    (SELECT COUNT(books_{tn}_link.id) FROM books_{tn}_link WHERE
                        {cn}={tn}.id AND books_list_filter(book)) count
                FROM {tn};
                '''.format(tn=table_name, cn=column_name, vcn=view_column_name))
            self.conn.executescript(script)

        for tn, cn in self.tag_browser_categories.items():
            if tn != 'news':
                create_tag_browser_view(tn, cn[0], cn[1])


