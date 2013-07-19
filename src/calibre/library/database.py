__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Backend that implements storage of ebooks in an sqlite database.
'''
import sqlite3 as sqlite
import datetime, re, cPickle, sre_constants
from zlib import compress, decompress

from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata import string_to_authors
from calibre import isbytestring

class Concatenate(object):
    '''String concatenation aggregator for sqlite'''
    def __init__(self, sep=','):
        self.sep = sep
        self.ans = ''

    def step(self, value):
        if value is not None:
            self.ans += value + self.sep

    def finalize(self):
        if not self.ans:
            return None
        if self.sep:
            return self.ans[:-len(self.sep)]
        return self.ans
class Connection(sqlite.Connection):

    def get(self, *args, **kw):
        ans = self.execute(*args)
        if not kw.get('all', True):
            ans = ans.fetchone()
            if not ans:
                ans = [None]
            return ans[0]
        return ans.fetchall()

def _connect(path):
    if isinstance(path, unicode):
        path = path.encode('utf-8')
    conn =  sqlite.connect(path, factory=Connection, detect_types=sqlite.PARSE_DECLTYPES|sqlite.PARSE_COLNAMES)
    conn.row_factory = lambda cursor, row : list(row)
    conn.create_aggregate('concat', 1, Concatenate)
    title_pat = re.compile('^(A|The|An)\s+', re.IGNORECASE)
    def title_sort(title):
        match = title_pat.search(title)
        if match:
            prep = match.group(1)
            title = title.replace(prep, '') + ', ' + prep
        return title.strip()
    conn.create_function('title_sort', 1, title_sort)
    return conn

class LibraryDatabase(object):

    @staticmethod
    def books_in_old_database(path):
        '''
        Iterator over the books in the old pre 0.4.0 database.
        '''
        conn = sqlite.connect(path)
        cur = conn.execute('select * from books_meta order by id;')
        book = cur.fetchone()
        while book:
            id = book[0]
            meta = { 'title':book[1], 'authors':book[2], 'publisher':book[3],
                     'tags':book[5], 'comments':book[7], 'rating':book[8],
                     'timestamp':datetime.datetime.strptime(book[6], '%Y-%m-%d %H:%M:%S'),
                    }
            cover = {}
            query = conn.execute('select uncompressed_size, data from books_cover where id=?', (id,)).fetchone()
            if query:
                cover = {'uncompressed_size': query[0], 'data': query[1]}
            query = conn.execute('select extension, uncompressed_size, data from books_data where id=?', (id,)).fetchall()
            formats = {}
            for row in query:
                formats[row[0]] = {'uncompressed_size':row[1], 'data':row[2]}
            yield meta, cover, formats
            book = cur.fetchone()

    @staticmethod
    def sizeof_old_database(path):
        conn = sqlite.connect(path)
        ans  = conn.execute('SELECT COUNT(id) from books_meta').fetchone()[0]
        conn.close()
        return ans

    @staticmethod
    def import_old_database(path, conn, progress=None):
        count = 0
        for book, cover, formats in LibraryDatabase.books_in_old_database(path):
            authors = book['authors']
            if not authors:
                authors = 'Unknown'
            obj = conn.execute('INSERT INTO books(title, timestamp, author_sort) VALUES (?,?,?)',
                               (book['title'], book['timestamp'], authors))
            id = obj.lastrowid
            authors = string_to_authors(authors)
            for a in authors:
                author = conn.execute('SELECT id from authors WHERE name=?', (a,)).fetchone()
                if author:
                    aid = author[0]
                else:
                    aid = conn.execute('INSERT INTO authors(name) VALUES (?)', (a,)).lastrowid
                conn.execute('INSERT INTO books_authors_link(book, author) VALUES (?,?)', (id, aid))
            if book['publisher']:
                candidate = conn.execute('SELECT id from publishers WHERE name=?', (book['publisher'],)).fetchone()
                pid = candidate[0] if candidate else conn.execute('INSERT INTO publishers(name) VALUES (?)',
                                                              (book['publisher'],)).lastrowid
                conn.execute('INSERT INTO books_publishers_link(book, publisher) VALUES (?,?)', (id, pid))
            if book['rating']:
                candidate = conn.execute('SELECT id from ratings WHERE rating=?', (2*book['rating'],)).fetchone()
                rid = candidate[0] if candidate else conn.execute('INSERT INTO ratings(rating) VALUES (?)',
                                                              (2*book['rating'],)).lastrowid
                conn.execute('INSERT INTO books_ratings_link(book, rating) VALUES (?,?)', (id, rid))
            tags = book['tags']
            if tags:
                tags = tags.split(',')
            else:
                tags = []
            for a in tags:
                a = a.strip()
                if not a: continue
                tag = conn.execute('SELECT id from tags WHERE name=?', (a,)).fetchone()
                if tag:
                    tid = tag[0]
                else:
                    tid = conn.execute('INSERT INTO tags(name) VALUES (?)', (a,)).lastrowid
                conn.execute('INSERT INTO books_tags_link(book, tag) VALUES (?,?)', (id, tid))
            comments = book['comments']
            if comments:
                conn.execute('INSERT INTO comments(book, text) VALUES (?, ?)',
                             (id, comments))
            if cover:
                conn.execute('INSERT INTO covers(book, uncompressed_size, data) VALUES (?, ?, ?)',
                             (id, cover['uncompressed_size'], cover['data']))
            for format in formats.keys():
                conn.execute('INSERT INTO data(book, format, uncompressed_size, data) VALUES (?, ?, ?, ?)',
                             (id, format, formats[format]['uncompressed_size'],
                              formats[format]['data']))
            conn.commit()
            count += 1
            if progress:
                progress(count)


    @staticmethod
    def create_version1(conn):
        conn.executescript(\
        '''
        /**** books table *****/
        CREATE TABLE books ( id        INTEGER PRIMARY KEY AUTOINCREMENT,
                             title     TEXT NOT NULL DEFAULT 'Unknown' COLLATE NOCASE,
                             sort      TEXT COLLATE NOCASE,
                             timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                             uri       TEXT,
                             series_index INTEGER NOT NULL DEFAULT 1
                           );
        CREATE INDEX books_idx ON books (sort COLLATE NOCASE);
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


        /***** authors table *****/
        CREATE TABLE authors ( id   INTEGER PRIMARY KEY,
                              name TEXT NOT NULL COLLATE NOCASE,
                              sort TEXT COLLATE NOCASE,
                              UNIQUE(name)
                             );
        CREATE INDEX authors_idx ON authors (sort COLLATE NOCASE);
        CREATE TRIGGER authors_insert_trg
        AFTER INSERT ON authors
        BEGIN
          UPDATE authors SET sort=NEW.name WHERE id=NEW.id;
        END;
        CREATE TRIGGER authors_update_trg
        AFTER UPDATE ON authors
        BEGIN
          UPDATE authors SET sort=NEW.name WHERE id=NEW.id;
        END;
        CREATE TABLE books_authors_link ( id INTEGER PRIMARY KEY,
                                          book INTEGER NOT NULL,
                                          author INTEGER NOT NULL,
                                          UNIQUE(book, author)
                                        );
        CREATE INDEX books_authors_link_bidx ON books_authors_link (book);
        CREATE INDEX books_authors_link_aidx ON books_authors_link (author);

        CREATE TRIGGER fkc_insert_books_authors_link
        BEFORE INSERT ON books_authors_link
        BEGIN
          SELECT CASE
              WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
              THEN RAISE(ABORT, 'Foreign key violation: book not in books')
              WHEN (SELECT id from authors WHERE id=NEW.author) IS NULL
              THEN RAISE(ABORT, 'Foreign key violation: author not in authors')
          END;
        END;
        CREATE TRIGGER fkc_update_books_authors_link_a
        BEFORE UPDATE OF book ON books_authors_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
            END;
        END;
        CREATE TRIGGER fkc_update_books_authors_link_b
        BEFORE UPDATE OF author ON books_authors_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from authors WHERE id=NEW.author) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: author not in authors')
            END;
        END;
        CREATE TRIGGER fkc_delete_books_authors_link
        BEFORE DELETE ON authors
        BEGIN
            SELECT CASE
                WHEN (SELECT COUNT(id) FROM books_authors_link WHERE book=OLD.book) > 0
                THEN RAISE(ABORT, 'Foreign key violation: author is still referenced')
            END;
        END;

        /***** publishers table *****/
        CREATE TABLE publishers ( id   INTEGER PRIMARY KEY,
                                  name TEXT NOT NULL COLLATE NOCASE,
                                  sort TEXT COLLATE NOCASE,
                                  UNIQUE(name)
                             );
        CREATE INDEX publishers_idx ON publishers (sort COLLATE NOCASE);
        CREATE TRIGGER publishers_insert_trg
        AFTER INSERT ON publishers
        BEGIN
          UPDATE publishers SET sort=NEW.name WHERE id=NEW.id;
        END;
        CREATE TRIGGER publishers_update_trg
        AFTER UPDATE ON publishers
        BEGIN
          UPDATE publishers SET sort=NEW.name WHERE id=NEW.id;
        END;
        CREATE TABLE books_publishers_link ( id INTEGER PRIMARY KEY,
                                          book INTEGER NOT NULL,
                                          publisher INTEGER NOT NULL,
                                          UNIQUE(book)
                                        );
        CREATE INDEX books_publishers_link_bidx ON books_publishers_link (book);
        CREATE INDEX books_publishers_link_aidx ON books_publishers_link (publisher);

        CREATE TRIGGER fkc_insert_books_publishers_link
        BEFORE INSERT ON books_publishers_link
        BEGIN
          SELECT CASE
              WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
              THEN RAISE(ABORT, 'Foreign key violation: book not in books')
              WHEN (SELECT id from publishers WHERE id=NEW.publisher) IS NULL
              THEN RAISE(ABORT, 'Foreign key violation: publisher not in publishers')
          END;
        END;
        CREATE TRIGGER fkc_update_books_publishers_link_a
        BEFORE UPDATE OF book ON books_publishers_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
            END;
        END;
        CREATE TRIGGER fkc_update_books_publishers_link_b
        BEFORE UPDATE OF publisher ON books_publishers_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from publishers WHERE id=NEW.publisher) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: publisher not in publishers')
            END;
        END;
        CREATE TRIGGER fkc_delete_books_publishers_link
        BEFORE DELETE ON publishers
        BEGIN
            SELECT CASE
                WHEN (SELECT COUNT(id) FROM books_publishers_link WHERE book=OLD.book) > 0
                THEN RAISE(ABORT, 'Foreign key violation: publisher is still referenced')
            END;
        END;

        /***** tags table *****/
        CREATE TABLE tags ( id   INTEGER PRIMARY KEY,
                            name TEXT NOT NULL COLLATE NOCASE,
                            UNIQUE (name)
                             );
        CREATE INDEX tags_idx ON tags (name COLLATE NOCASE);

        CREATE TABLE books_tags_link ( id INTEGER PRIMARY KEY,
                                          book INTEGER NOT NULL,
                                          tag INTEGER NOT NULL,
                                          UNIQUE(book, tag)
                                        );
        CREATE INDEX books_tags_link_bidx ON books_tags_link (book);
        CREATE INDEX books_tags_link_aidx ON books_tags_link (tag);

        CREATE TRIGGER fkc_insert_books_tags_link
        BEFORE INSERT ON books_tags_link
        BEGIN
          SELECT CASE
              WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
              THEN RAISE(ABORT, 'Foreign key violation: book not in books')
              WHEN (SELECT id from tags WHERE id=NEW.tag) IS NULL
              THEN RAISE(ABORT, 'Foreign key violation: tag not in tags')
          END;
        END;
        CREATE TRIGGER fkc_update_books_tags_link_a
        BEFORE UPDATE OF book ON books_tags_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
            END;
        END;
        CREATE TRIGGER fkc_update_books_tags_link_b
        BEFORE UPDATE OF tag ON books_tags_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from tags WHERE id=NEW.tag) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: tag not in tags')
            END;
        END;
        CREATE TRIGGER fkc_delete_books_tags_link
        BEFORE DELETE ON tags
        BEGIN
            SELECT CASE
                WHEN (SELECT COUNT(id) FROM books_tags_link WHERE tag=OLD.book) > 0
                THEN RAISE(ABORT, 'Foreign key violation: tag is still referenced')
            END;
        END;

        /***** series table *****/
        CREATE TABLE series ( id   INTEGER PRIMARY KEY,
                              name TEXT NOT NULL COLLATE NOCASE,
                              sort TEXT COLLATE NOCASE,
                              UNIQUE (name)
                             );
        CREATE INDEX series_idx ON series (sort COLLATE NOCASE);
        CREATE TRIGGER series_insert_trg
        AFTER INSERT ON series
        BEGIN
          UPDATE series SET sort=NEW.name WHERE id=NEW.id;
        END;
        CREATE TRIGGER series_update_trg
        AFTER UPDATE ON series
        BEGIN
          UPDATE series SET sort=NEW.name WHERE id=NEW.id;
        END;
        CREATE TABLE books_series_link ( id INTEGER PRIMARY KEY,
                                          book INTEGER NOT NULL,
                                          series INTEGER NOT NULL,
                                          UNIQUE(book)
                                        );
        CREATE INDEX books_series_link_bidx ON books_series_link (book);
        CREATE INDEX books_series_link_aidx ON books_series_link (series);

        CREATE TRIGGER fkc_insert_books_series_link
        BEFORE INSERT ON books_series_link
        BEGIN
          SELECT CASE
              WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
              THEN RAISE(ABORT, 'Foreign key violation: book not in books')
              WHEN (SELECT id from series WHERE id=NEW.series) IS NULL
              THEN RAISE(ABORT, 'Foreign key violation: series not in series')
          END;
        END;
        CREATE TRIGGER fkc_update_books_series_link_a
        BEFORE UPDATE OF book ON books_series_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
            END;
        END;
        CREATE TRIGGER fkc_update_books_series_link_b
        BEFORE UPDATE OF serie ON books_series_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from series WHERE id=NEW.series) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: series not in series')
            END;
        END;
        CREATE TRIGGER fkc_delete_books_series_link
        BEFORE DELETE ON series
        BEGIN
            SELECT CASE
                WHEN (SELECT COUNT(id) FROM books_series_link WHERE book=OLD.book) > 0
                THEN RAISE(ABORT, 'Foreign key violation: series is still referenced')
            END;
        END;

        /**** ratings table ****/

        CREATE TABLE ratings ( id   INTEGER PRIMARY KEY,
                               rating INTEGER CHECK(rating > -1 AND rating < 11),
                               UNIQUE (rating)
                             );
        INSERT INTO ratings (rating) VALUES (0);
        INSERT INTO ratings (rating) VALUES (1);
        INSERT INTO ratings (rating) VALUES (2);
        INSERT INTO ratings (rating) VALUES (3);
        INSERT INTO ratings (rating) VALUES (4);
        INSERT INTO ratings (rating) VALUES (5);
        INSERT INTO ratings (rating) VALUES (6);
        INSERT INTO ratings (rating) VALUES (7);
        INSERT INTO ratings (rating) VALUES (8);
        INSERT INTO ratings (rating) VALUES (9);
        INSERT INTO ratings (rating) VALUES (10);

        CREATE TABLE books_ratings_link ( id INTEGER PRIMARY KEY,
                                          book INTEGER NOT NULL,
                                          rating INTEGER NOT NULL,
                                          UNIQUE(book, rating)
                                        );
        CREATE INDEX books_ratings_link_bidx ON books_ratings_link (book);
        CREATE INDEX books_ratings_link_aidx ON books_ratings_link (rating);

        CREATE TRIGGER fkc_insert_books_ratings_link
        BEFORE INSERT ON books_ratings_link
        BEGIN
          SELECT CASE
              WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
              THEN RAISE(ABORT, 'Foreign key violation: book not in books')
              WHEN (SELECT id from ratings WHERE id=NEW.rating) IS NULL
              THEN RAISE(ABORT, 'Foreign key violation: rating not in ratings')
          END;
        END;
        CREATE TRIGGER fkc_update_books_ratings_link_a
        BEFORE UPDATE OF book ON books_ratings_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
            END;
        END;
        CREATE TRIGGER fkc_update_books_ratings_link_b
        BEFORE UPDATE OF rating ON books_ratings_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from ratings WHERE id=NEW.rating) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: rating not in ratings')
            END;
        END;

        /**** data table ****/
        CREATE TABLE data ( id     INTEGER PRIMARY KEY,
                            book   INTEGER NON NULL,
                            format TEXT NON NULL COLLATE NOCASE,
                            uncompressed_size INTEGER NON NULL,
                            data   BLOB NON NULL,
                            UNIQUE(book, format)
                          );
        CREATE INDEX data_idx ON data (book);
        CREATE TRIGGER fkc_data_insert
        BEFORE INSERT ON data
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
            END;
        END;
        CREATE TRIGGER fkc_data_update
        BEFORE UPDATE OF book ON data
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
            END;
        END;

        /**** covers table ****/
        CREATE TABLE covers ( id INTEGER PRIMARY KEY,
                              book INTEGER NON NULL,
                              uncompressed_size INTEGER NON NULL,
                              data BLOB NON NULL,
                              UNIQUE(book)
                            );
        CREATE INDEX covers_idx ON covers (book);
        CREATE TRIGGER fkc_covers_insert
        BEFORE INSERT ON covers
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
            END;
        END;
        CREATE TRIGGER fkc_covers_update
        BEFORE UPDATE OF book ON covers
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
            END;
        END;

        /**** comments table ****/
        CREATE TABLE comments ( id INTEGER PRIMARY KEY,
                              book INTEGER NON NULL,
                              text TEXT NON NULL COLLATE NOCASE,
                              UNIQUE(book)
                            );
        CREATE INDEX comments_idx ON comments (book);
        CREATE TRIGGER fkc_comments_insert
        BEFORE INSERT ON comments
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
            END;
        END;
        CREATE TRIGGER fkc_comments_update
        BEFORE UPDATE OF book ON comments
        BEGIN
            SELECT CASE
                WHEN (SELECT id from books WHERE id=NEW.book) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: book not in books')
            END;
        END;

        /**** Handle deletion of book ****/
        CREATE TRIGGER books_delete_trg
        AFTER DELETE ON books
        BEGIN
            DELETE FROM books_authors_link WHERE book=OLD.id;
            DELETE FROM books_publishers_link WHERE book=OLD.id;
            DELETE FROM books_ratings_link WHERE book=OLD.id;
            DELETE FROM books_series_link WHERE book=OLD.id;
            DELETE FROM books_tags_link WHERE book=OLD.id;
            DELETE FROM data WHERE book=OLD.id;
            DELETE FROM covers WHERE book=OLD.id;
            DELETE FROM comments WHERE book=OLD.id;
        END;

        /**** Views ****/
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
               sort,
               (SELECT sort FROM authors WHERE authors.id IN (SELECT author from books_authors_link WHERE book=books.id)) authors_sort,
               (SELECT sort FROM publishers WHERE publishers.id IN (SELECT publisher from books_publishers_link WHERE book=books.id)) publisher_sort
        FROM books;
        '''\
        )
        conn.execute('pragma user_version=1')
        conn.commit()

    @staticmethod
    def upgrade_version1(conn):
        conn.executescript(
'''
/***** authors_sort table *****/
        ALTER TABLE books ADD COLUMN author_sort TEXT COLLATE NOCASE;
        UPDATE books SET author_sort=(SELECT name FROM authors WHERE id=(SELECT author FROM books_authors_link WHERE book=books.id)) WHERE id IN (SELECT id FROM books ORDER BY id);
        DROP INDEX authors_idx;
        DROP TRIGGER authors_insert_trg;
        DROP TRIGGER authors_update_trg;
        CREATE INDEX authors_idx ON books (author_sort COLLATE NOCASE);

        CREATE TABLE conversion_options ( id INTEGER PRIMARY KEY,
                                          format TEXT NOT NULL COLLATE NOCASE,
                                          book INTEGER,
                                          data BLOB NOT NULL,
                                          UNIQUE(format,book)
                                        );
        CREATE INDEX conversion_options_idx_a ON conversion_options (format COLLATE NOCASE);
        CREATE INDEX conversion_options_idx_b ON conversion_options (book);

        DROP TRIGGER books_delete_trg;
        CREATE TRIGGER books_delete_trg
        AFTER DELETE ON books
        BEGIN
            DELETE FROM books_authors_link WHERE book=OLD.id;
            DELETE FROM books_publishers_link WHERE book=OLD.id;
            DELETE FROM books_ratings_link WHERE book=OLD.id;
            DELETE FROM books_series_link WHERE book=OLD.id;
            DELETE FROM books_tags_link WHERE book=OLD.id;
            DELETE FROM data WHERE book=OLD.id;
            DELETE FROM covers WHERE book=OLD.id;
            DELETE FROM comments WHERE book=OLD.id;
            DELETE FROM conversion_options WHERE book=OLD.id;
        END;

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
               sort,
               author_sort
        FROM books;

        DROP INDEX publishers_idx;
        CREATE INDEX publishers_idx ON publishers (name COLLATE NOCASE);
        DROP TRIGGER publishers_insert_trg;
        DROP TRIGGER publishers_update_trg;
'''
                                )
        conn.execute('pragma user_version=2')
        conn.commit()

    @staticmethod
    def upgrade_version2(conn):
        conn.executescript(
'''
/***** Add ISBN column ******/
ALTER TABLE books ADD COLUMN isbn TEXT DEFAULT "" COLLATE NOCASE;
''')
        conn.execute('pragma user_version=3')
        conn.commit()

    @staticmethod
    def upgrade_version3(conn):
        conn.executescript(
'''
/***** Add series_index column to meta view ******/
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
           author_sort
    FROM books;
''')
        conn.execute('pragma user_version=4')
        conn.commit()

    @staticmethod
    def upgrade_version4(conn):
        conn.executescript(
'''
/***** Add formats column to meta view ******/
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
           (SELECT concat(format) FROM data WHERE data.book=books.id) formats
    FROM books;
''')
        conn.execute('pragma user_version=5')
        conn.commit()

    @staticmethod
    def upgrade_version5(conn):
        conn.executescript(\
        '''
        DROP TRIGGER fkc_delete_books_tags_link;
        CREATE TRIGGER fkc_delete_books_tags_link
        BEFORE DELETE ON tags
        BEGIN
            SELECT CASE
                WHEN (SELECT COUNT(id) FROM books_tags_link WHERE tag=OLD.id) > 0
                THEN RAISE(ABORT, 'Foreign key violation: tag is still referenced')
            END;
        END;
        ''')
        conn.execute('pragma user_version=6')
        conn.commit()

    @staticmethod
    def upgrade_version6(conn):
        conn.executescript('''CREATE TABLE feeds ( id   INTEGER PRIMARY KEY,
                              title TEXT NOT NULL,
                              script TEXT NOT NULL,
                              UNIQUE(title)
                             );''')
        conn.execute('pragma user_version=7')
        conn.commit()

    @staticmethod
    def upgrade_version7(conn):
        conn.executescript('''\
        DROP TRIGGER fkc_update_books_series_link_b;
        CREATE TRIGGER fkc_update_books_series_link_b
        BEFORE UPDATE OF series ON books_series_link
        BEGIN
            SELECT CASE
                WHEN (SELECT id from series WHERE id=NEW.series) IS NULL
                THEN RAISE(ABORT, 'Foreign key violation: series not in series')
            END;
        END;

        DROP TRIGGER fkc_delete_books_series_link;
        CREATE TRIGGER fkc_delete_books_series_link
        BEFORE DELETE ON series
        BEGIN
            SELECT CASE
                WHEN (SELECT COUNT(id) FROM books_series_link WHERE series=OLD.id) > 0
                THEN RAISE(ABORT, 'Foreign key violation: series is still referenced')
            END;
        END;
        '''
        )
        conn.execute('pragma user_version=8')
        conn.commit()

    @staticmethod
    def upgrade_version8(conn):
        conn.execute('DELETE FROM feeds')
        conn.execute('pragma user_version=9')
        conn.commit()

    @staticmethod
    def upgrade_version9(conn):
        for id, title in conn.execute('SELECT id, title FROM books').fetchall():
            conn.execute('UPDATE books SET title=? WHERE id=?', (title, id))
        conn.execute('pragma user_version=10')
        conn.commit()

    @staticmethod
    def upgrade_version10(conn):
        for id, author_sort in conn.execute('SELECT id, author_sort FROM books').fetchall():
            if not author_sort:
                aus = conn.execute('SELECT authors FROM meta WHERE id=?',(id,)).fetchone()[0]
                conn.execute('UPDATE books SET author_sort=? WHERE id=?', (aus, id))
        conn.execute('pragma user_version=11')
        conn.commit()

    @staticmethod
    def upgrade_version11(conn):
        conn.executescript(
'''
/***** Add isbn column to meta view ******/
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
           isbn
    FROM books;
''')
        conn.execute('pragma user_version=12')
        conn.commit()

    def __init__(self, dbpath, row_factory=False):
        self.dbpath = dbpath
        self.conn = _connect(dbpath)
        if row_factory:
            self.conn.row_factory = sqlite.Row
        self.cache = []
        self.data  = []
        if self.user_version == 0: # No tables have been created
            LibraryDatabase.create_version1(self.conn)
        i = 0
        while True:
            i += 1
            func = getattr(LibraryDatabase, 'upgrade_version%d'%i, None)
            if func is None:
                break
            if self.user_version == i:
                print 'Upgrading database from version: %d'%i
                func(self.conn)


    def close(self):
#        global _lock_file
#        _lock_file.close()
#        os.unlink(_lock_file.name)
#        _lock_file = None
        self.conn.close()

    @dynamic_property
    def user_version(self):
        doc = 'The user version of this database'
        def fget(self):
            return self.conn.get('pragma user_version;', all=False)
        return property(doc=doc, fget=fget)

    def is_empty(self):
        return not self.conn.get('SELECT id FROM books LIMIT 1', all=False)

    def refresh(self, sort_field, ascending):
        '''
        Rebuild self.data and self.cache. Filter results are lost.
        '''
        FIELDS = {
                  'title'        : 'sort',
                  'authors'      : 'author_sort',
                  'publisher'    : 'publisher',
                  'size'         : 'size',
                  'date'         : 'timestamp',
                  'timestamp'    : 'timestamp',
                  'formats'      : 'formats',
                  'rating'       : 'rating',
                  'tags'         : 'tags',
                  'series'       : 'series',
                 }
        field = FIELDS[sort_field]
        order = 'ASC'
        if not ascending:
            order = 'DESC'
        sort = field + ' ' + order
        if field == 'series':
            sort += ',series_index '+order
        elif field == 'title':
            sort += ',author_sort ' + order
        else:
            sort += ',title '+order

        self.cache = self.conn.get('SELECT * from meta ORDER BY '+sort)
        self.data  = self.cache
        self.conn.commit()

    def refresh_ids(self, ids):
        indices = map(self.index, ids)
        for id, idx in zip(ids, indices):
            row = self.conn.get('SELECT * from meta WHERE id=?', (id,), all=False)
            self.data[idx] = row
        return indices

    def filter(self, filters, refilter=False, OR=False):
        '''
        Filter data based on filters. All the filters must match for an item to
        be accepted. Matching is case independent regexp matching.
        @param filters: A list of SearchToken objects
        @param refilter: If True filters are applied to the results of the previous
                         filtering.
        @param OR: If True, keeps a match if any one of the filters matches. If False,
        keeps a match only if all the filters match
        '''
        if not filters:
            self.data = self.data if refilter else self.cache
        else:
            matches = []
            for item in self.data if refilter else self.cache:
                if OR:
                    keep = False
                    for token in filters:
                        if token.match(item):
                            keep = True
                            break
                    if keep:
                        matches.append(item)
                else:
                    keep = True
                    for token in filters:
                        if not token.match(item):
                            keep = False
                            break
                    if keep:
                        matches.append(item)
            self.data = matches

    def rows(self):
        return len(self.data) if self.data else 0

    def id(self, index):
        return self.data[index][0]

    def row(self, id):
        for r, record in enumerate(self.data):
            if record[0] == id:
                return r

    def title(self, index, index_is_id=False):
        if not index_is_id:
            return self.data[index][1]
        try:
            return self.conn.get('SELECT title FROM meta WHERE id=?',(index,), all=False)
        except:
            return _('Unknown')

    def authors(self, index, index_is_id=False):
        '''
        Authors as a comma separated list or None.
        In the comma separated list, commas in author names are replaced by | symbols
        '''
        if not index_is_id:
            return self.data[index][2]
        try:
            return self.conn.get('SELECT authors FROM meta WHERE id=?',(index,), all=False)
        except:
            pass

    def author_id(self, index, index_is_id=False):
        id  = index if index_is_id else self.id(index)
        return self.conn.get('SELECT author from books_authors_link WHERE book=?', (id,), all=False)

    def isbn(self, idx, index_is_id=False):
        id = idx if index_is_id else self.id(idx)
        return self.conn.get('SELECT isbn FROM books WHERE id=?',(id,), all=False)

    def author_sort(self, index, index_is_id=False):
        id = index if index_is_id else self.id(index)
        return self.conn.get('SELECT author_sort FROM books WHERE id=?', (id,), all=False)

    def publisher(self, index, index_is_id=False):
        if index_is_id:
            return self.conn.get('SELECT publisher FROM meta WHERE id=?', (index,), all=False)
        return self.data[index][3]

    def publisher_id(self, index, index_is_id=False):
        id  = index if index_is_id else self.id(index)
        return self.conn.get('SELECT publisher from books_publishers_link WHERE book=?', (id,), all=False)

    def rating(self, index, index_is_id=False):
        if index_is_id:
            return self.conn.get('SELECT rating FROM meta WHERE id=?', (index,), all=False)
        return self.data[index][4]

    def timestamp(self, index, index_is_id=False):
        if index_is_id:
            return self.conn.get('SELECT timestamp FROM meta WHERE id=?', (index,), all=False)
        return self.data[index][5]

    def max_size(self, index, index_is_id=False):
        if index_is_id:
            return self.conn.get('SELECT size FROM meta WHERE id=?', (index,), all=False)
        return self.data[index][4]

    def cover(self, index, index_is_id=False):
        '''Cover as a data string or None'''
        id = index if index_is_id else self.id(index)
        data = self.conn.get('SELECT data FROM covers WHERE book=?', (id,), all=False)
        if not data:
            return None
        return(decompress(data))

    def tags(self, index, index_is_id=False):
        '''tags as a comma separated list or None'''
        id = index if index_is_id else self.id(index)
        matches = self.conn.get('SELECT concat(name) FROM tags WHERE tags.id IN (SELECT tag from books_tags_link WHERE book=?)', (id,))
        if not matches or not matches[0][0]:
            return None
        matches = [t.lower().strip() for t in matches[0][0].split(',')]
        return ','.join(matches)

    def series_id(self, index, index_is_id=False):
        id  = index if index_is_id else self.id(index)
        return self.conn.get('SELECT series from books_series_link WHERE book=?', (id,), all=False)

    def series(self, index, index_is_id=False):
        id = self.series_id(index, index_is_id)
        return self.conn.get('SELECT name from series WHERE id=?', (id,), all=False)

    def series_index(self, index, index_is_id=False):
        ans = None
        if not index_is_id:
            ans = self.data[index][10]
        else:
            ans = self.conn.get('SELECT series_index FROM books WHERE id=?', (index,), all=False)
        try:
            return float(ans)
        except:
            return 1.0

    def books_in_series(self, series_id):
        '''
        Return an ordered list of all books in the series.
        The list contains book ids.
        '''
        ans = self.conn.get('SELECT book from books_series_link WHERE series=?',
                                (series_id,))
        if not ans:
            return []
        ans = [id[0] for id in ans]
        ans.sort(cmp = lambda x, y: cmp(self.series_index(x, True), self.series_index(y, True)))
        return ans

    def books_in_series_of(self, index, index_is_id=False):
        '''
        Return an ordered list of all books in the series that the book identified by index belongs to.
        If the book does not belong to a series return an empty list. The list contains book ids.
        '''
        series_id = self.series_id(index, index_is_id=index_is_id)
        return self.books_in_series(series_id)


    def comments(self, index, index_is_id=False):
        '''Comments as string or None'''
        id = index if index_is_id else self.id(index)
        return self.conn.get('SELECT text FROM comments WHERE book=?', (id,), all=False)

    def formats(self, index, index_is_id=False):
        ''' Return available formats as a comma separated list '''
        id = index if index_is_id else self.id(index)
        return self.conn.get('SELECT concat(format) FROM data WHERE data.book=?', (id,), all=False)

    def sizeof_format(self, index, format, index_is_id=False):
        ''' Return size of C{format} for book C{index} in bytes'''
        id = index if index_is_id else self.id(index)
        format = format.upper()
        return self.conn.get('SELECT uncompressed_size FROM data WHERE data.book=? AND data.format=?', (id, format), all=False)


    def format(self, index, format, index_is_id=False):
        id = index if index_is_id else self.id(index)
        return decompress(self.conn.get('SELECT data FROM data WHERE book=? AND format=?', (id, format), all=False))

    def all_series(self):
        return [ (i[0], i[1]) for i in \
                self.conn.get('SELECT id, name FROM series')]

    def series_name(self, series_id):
        return self.conn.get('SELECT name FROM series WHERE id=%d'%series_id,
                all=False)

    def author_name(self, author_id):
        return self.conn.get('SELECT name FROM authors WHERE id=%d'%author_id,
                all=False)

    def tag_name(self, tag_id):
        return self.conn.get('SELECT name FROM tags WHERE id=%d'%tag_id,
                all=False)

    def all_authors(self):
        return [ (i[0], i[1]) for i in \
                self.conn.get('SELECT id, name FROM authors')]

    def all_author_names(self):
        return filter(None, [i[0].strip().replace('|', ',') for i in self.conn.get(
            'SELECT name FROM authors')])

    def all_publishers(self):
        return [ (i[0], i[1]) for i in \
                self.conn.get('SELECT id, name FROM publishers')]

    def all_tags(self):
        return [i[0].strip() for i in self.conn.get('SELECT name FROM tags') if i[0].strip()]

    def all_tags2(self):
        return [ (i[0], i[1]) for i in \
                self.conn.get('SELECT id, name FROM tags')]

    def all_titles(self):
        return [ (i[0], i[1]) for i in \
                self.conn.get('SELECT id, title FROM books')]

    def conversion_options(self, id, format):
        data = self.conn.get('SELECT data FROM conversion_options WHERE book=? AND format=?', (id, format.upper()), all=False)
        if data:
            return cPickle.loads(str(data))
        return None

    def has_conversion_options(self, ids, format='PIPE'):
        ids = tuple(ids)
        if len(ids) > 50000:
            return True
        if len(ids) == 1:
            ids = '(%d)'%ids[0]
        else:
            ids = repr(ids)
        return self.conn.get('''
            SELECT data FROM conversion_options WHERE book IN %s AND
        format=? LIMIT 1'''%(ids,), (format,), all=False) is not None

    def delete_conversion_options(self, id, format, commit=True):
        self.conn.execute('DELETE FROM conversion_options WHERE book=? AND format=?',
                (id, format.upper()))
        if commit:
            self.conn.commit()


    def add_format(self, index, ext, stream, index_is_id=False):
        '''
        Add the format specified by ext. If it already exists it is replaced.
        '''
        id = index if index_is_id else self.id(index)
        stream.seek(0, 2)
        usize = stream.tell()
        stream.seek(0)
        data = sqlite.Binary(compress(stream.read()))
        exts = self.formats(index, index_is_id=index_is_id)
        if not exts:
            exts = []
        if not ext:
            ext = ''
        ext = ext.lower()
        if ext in exts:
            self.conn.execute('UPDATE data SET data=? WHERE format=? AND book=?',
                              (data, ext, id))
            self.conn.execute('UPDATE data SET uncompressed_size=? WHERE format=? AND book=?',
                              (usize, ext, id))
        else:
            self.conn.execute('INSERT INTO data(book, format, uncompressed_size, data) VALUES (?, ?, ?, ?)',
                              (id, ext, usize, data))
        self.conn.commit()

    def remove_format(self, index, ext, index_is_id=False):
        id = index if index_is_id else self.id(index)
        self.conn.execute('DELETE FROM data WHERE book=? AND format=?', (id, ext.lower()))
        self.conn.commit()

    def set(self, row, column, val):
        '''
        Convenience method for setting the title, authors, publisher or rating
        '''
        id = self.data[row][0]
        col = {'title':1, 'authors':2, 'publisher':3, 'rating':4, 'tags':7}[column]

        self.data[row][col] = val
        for item in self.cache:
            if item[0] == id:
                item[col] = val
                break
        if column == 'authors':
            val = string_to_authors(val)
            self.set_authors(id, val)
        elif column == 'title':
            self.set_title(id, val)
        elif column == 'publisher':
            self.set_publisher(id, val)
        elif column == 'rating':
            self.set_rating(id, val)
        elif column == 'tags':
            self.set_tags(id, val.split(','), append=False)

    def set_conversion_options(self, id, format, options):
        data = sqlite.Binary(cPickle.dumps(options, -1))
        oid = self.conn.get('SELECT id FROM conversion_options WHERE book=? AND format=?', (id, format.upper()), all=False)
        if oid:
            self.conn.execute('UPDATE conversion_options SET data=? WHERE id=?', (data, oid))
        else:
            self.conn.execute('INSERT INTO conversion_options(book,format,data) VALUES (?,?,?)', (id,format.upper(),data))
        self.conn.commit()


    def set_authors(self, id, authors):
        '''
        @param authors: A list of authors.
        '''
        self.conn.execute('DELETE FROM books_authors_link WHERE book=?',(id,))
        for a in authors:
            if not a:
                continue
            a = a.strip()
            author = self.conn.get('SELECT id from authors WHERE name=?', (a,), all=False)
            if author:
                aid = author
                # Handle change of case
                self.conn.execute('UPDATE authors SET name=? WHERE id=?', (a, aid))
            else:
                aid = self.conn.execute('INSERT INTO authors(name) VALUES (?)', (a,)).lastrowid
            try:
                self.conn.execute('INSERT INTO books_authors_link(book, author) VALUES (?,?)', (id, aid))
            except sqlite.IntegrityError: # Sometimes books specify the same author twice in their metadata
                pass
        self.conn.commit()

    def set_author_sort(self, id, sort):
        self.conn.execute('UPDATE books SET author_sort=? WHERE id=?', (sort, id))
        self.conn.commit()

    def set_title(self, id, title):
        if not title:
            return
        self.conn.execute('UPDATE books SET title=? WHERE id=?', (title, id))
        self.conn.commit()

    def set_isbn(self, id, isbn):
        self.conn.execute('UPDATE books SET isbn=? WHERE id=?', (isbn, id))
        self.conn.commit()

    def set_publisher(self, id, publisher):
        self.conn.execute('DELETE FROM books_publishers_link WHERE book=?',(id,))
        if publisher:
            pub = self.conn.get('SELECT id from publishers WHERE name=?', (publisher,), all=False)
            if pub:
                aid = pub
            else:
                aid = self.conn.execute('INSERT INTO publishers(name) VALUES (?)', (publisher,)).lastrowid
            self.conn.execute('INSERT INTO books_publishers_link(book, publisher) VALUES (?,?)', (id, aid))
        self.conn.commit()

    def set_comment(self, id, text):
        self.conn.execute('DELETE FROM comments WHERE book=?', (id,))
        self.conn.execute('INSERT INTO comments(book,text) VALUES (?,?)', (id, text))
        self.conn.commit()

    def delete_tags(self, tags):
        for tag in tags:
            self.delete_tag(tag)

    def unapply_tags(self, book_id, tags):
        for tag in tags:
            id = self.conn.get('SELECT id FROM tags WHERE name=?', (tag,), all=False)
            if id:
                self.conn.execute('DELETE FROM books_tags_link WHERE tag=? AND book=?', (id, book_id))
        self.conn.commit()

    def set_tags(self, id, tags, append=False):
        '''
        @param tags: list of strings
        @param append: If True existing tags are not removed
        '''
        if not append:
            self.conn.execute('DELETE FROM books_tags_link WHERE book=?', (id,))
        for tag in set(tags):
            tag = tag.lower().strip()
            if not tag:
                continue
            t = self.conn.get('SELECT id FROM tags WHERE name=?', (tag,), all=False)
            if t:
                tid = t
            else:
                tid = self.conn.execute('INSERT INTO tags(name) VALUES(?)', (tag,)).lastrowid

            if not self.conn.get('SELECT book FROM books_tags_link WHERE book=? AND tag=?',
                                        (id, tid), all=False):
                self.conn.execute('INSERT INTO books_tags_link(book, tag) VALUES (?,?)',
                              (id, tid))
        self.conn.commit()


    def set_series(self, id, series):
        self.conn.execute('DELETE FROM books_series_link WHERE book=?',(id,))
        if series:
            s = self.conn.get('SELECT id from series WHERE name=?', (series,), all=False)
            if s:
                aid = s
            else:
                aid = self.conn.execute('INSERT INTO series(name) VALUES (?)', (series,)).lastrowid
            self.conn.execute('INSERT INTO books_series_link(book, series) VALUES (?,?)', (id, aid))
        self.conn.commit()
        row = self.row(id)
        if row is not None:
            self.data[row][9] = series

    def remove_unused_series(self):
        for id, in self.conn.get('SELECT id FROM series'):
            if not self.conn.get('SELECT id from books_series_link WHERE series=?', (id,)):
                self.conn.execute('DELETE FROM series WHERE id=?', (id,))
        self.conn.commit()

    def set_series_index(self, id, idx):
        idx = int(idx)
        self.conn.execute('UPDATE books SET series_index=? WHERE id=?', (int(idx), id))
        self.conn.commit()
        row = self.row(id)
        if row is not None:
            self.data[row][10] = idx

    def set_rating(self, id, rating):
        rating = int(rating)
        self.conn.execute('DELETE FROM books_ratings_link WHERE book=?',(id,))
        rat = self.conn.get('SELECT id FROM ratings WHERE rating=?', (rating,), all=False)
        rat = rat if rat else self.conn.execute('INSERT INTO ratings(rating) VALUES (?)', (rating,)).lastrowid
        self.conn.execute('INSERT INTO books_ratings_link(book, rating) VALUES (?,?)', (id, rat))
        self.conn.commit()

    def set_cover(self, id, data):
        self.conn.execute('DELETE FROM covers where book=?', (id,))
        if data:
            usize = len(data)
            data = compress(data)
            self.conn.execute('INSERT INTO covers(book, uncompressed_size, data) VALUES (?,?,?)',
                              (id, usize, sqlite.Binary(data)))
        self.conn.commit()

    def set_metadata(self, id, mi):
        '''
        Set metadata for the book C{id} from the L{MetaInformation} object C{mi}
        '''
        if mi.title:
            self.set_title(id, mi.title)
        if not mi.authors:
                mi.authors = ['Unknown']
        authors = []
        for a in mi.authors:
            authors += string_to_authors(a)
        self.set_authors(id, authors)
        if mi.author_sort:
            self.set_author_sort(id, mi.author_sort)
        if mi.publisher:
            self.set_publisher(id, mi.publisher)
        if mi.rating:
            self.set_rating(id, mi.rating)
        if mi.series:
            self.set_series(id, mi.series)
        if mi.cover_data[1] is not None:
            self.set_cover(id, mi.cover_data[1])




    def add_books(self, paths, formats, metadata, uris=[], add_duplicates=True):
        '''
        Add a book to the database. self.data and self.cache are not updated.
        @param paths: List of paths to book files of file-like objects
        '''
        formats, metadata, uris = iter(formats), iter(metadata), iter(uris)
        duplicates = []
        for path in paths:
            mi = metadata.next()
            format = formats.next()
            try:
                uri = uris.next()
            except StopIteration:
                uri = None
            if not add_duplicates and self.has_book(mi):
                duplicates.append((path, format, mi, uri))
                continue
            series_index = 1 if mi.series_index is None else mi.series_index
            aus = mi.author_sort if mi.author_sort else ', '.join(mi.authors)
            obj = self.conn.execute('INSERT INTO books(title, uri, series_index, author_sort) VALUES (?, ?, ?, ?)',
                              (mi.title, uri, series_index, aus))
            id = obj.lastrowid
            self.conn.commit()
            self.set_metadata(id, mi)
            stream = path if hasattr(path, 'read') else lopen(path, 'rb')
            stream.seek(0, 2)
            usize = stream.tell()
            stream.seek(0)

            self.conn.execute('INSERT INTO data(book, format, uncompressed_size, data) VALUES (?,?,?,?)',
                              (id, format, usize, sqlite.Binary(compress(stream.read()))))
            if not hasattr(path, 'read'):
                stream.close()
        self.conn.commit()
        if duplicates:
            paths    = tuple(duplicate[0] for duplicate in duplicates)
            formats  = tuple(duplicate[1] for duplicate in duplicates)
            metadata = tuple(duplicate[2] for duplicate in duplicates)
            uris     = tuple(duplicate[3] for duplicate in duplicates)
            return (paths, formats, metadata, uris)
        return None



    def index(self, id, cache=False):
        data = self.cache if cache else self.data
        for i in range(len(data)):
            if data[i][0] == id:
                return i

    def get_feeds(self):
        feeds = self.conn.get('SELECT title, script FROM feeds')
        for title, script in feeds:
            yield title, script

    def get_feed(self, id):
        return self.conn.get('SELECT script FROM feeds WHERE id=%d'%id,
                all=False)

    def update_feed(self, id, script, title):
        self.conn.execute('UPDATE feeds set title=? WHERE id=?', (title, id))
        self.conn.execute('UPDATE feeds set script=? WHERE id=?', (script, id))
        self.conn.commit()

    def remove_feeds(self, ids):
        for x in ids:
            self.conn.execute('DELETE FROM feeds WHERE id=?', (x,))
        self.conn.commit()

    def add_feed(self, title, script):
        if isbytestring(title):
            title = title.decode('utf-8')
        if isbytestring(script):
            script = script.decode('utf-8')
        self.conn.execute('INSERT INTO feeds(title, script) VALUES (?, ?)',
                                  (title, script))
        self.conn.commit()


    def set_feeds(self, feeds):
        self.conn.execute('DELETE FROM feeds')
        for title, script in feeds:
            self.conn.execute('INSERT INTO feeds(title, script) VALUES (?, ?)',
                                  (title, script))
        self.conn.commit()

    def delete_book(self, id):
        '''
        Removes book from self.cache, self.data and underlying database.
        '''
        try:
            self.cache.pop(self.index(id, cache=True))
            self.data.pop(self.index(id, cache=False))
        except TypeError: #If data and cache are the same object
            pass
        self.conn.execute('DELETE FROM books WHERE id=?', (id,))
        self.conn.commit()

    def get_metadata(self, idx, index_is_id=False):
        '''
        Convenience method to return metadata as a L{MetaInformation} object.
        '''
        aum = self.authors(idx, index_is_id=index_is_id)
        if aum: aum = [a.strip().replace('|', ',') for a in aum.split(',')]
        mi = MetaInformation(self.title(idx, index_is_id=index_is_id), aum)
        mi.author_sort = self.author_sort(idx, index_is_id=index_is_id)
        mi.comments    = self.comments(idx, index_is_id=index_is_id)
        mi.publisher   = self.publisher(idx, index_is_id=index_is_id)
        tags = self.tags(idx, index_is_id=index_is_id)
        if tags:
            mi.tags = [i.strip() for i in tags.split(',')]
        mi.series = self.series(idx, index_is_id=index_is_id)
        if mi.series:
            mi.series_index = self.series_index(idx, index_is_id=index_is_id)
        mi.rating = self.rating(idx, index_is_id=index_is_id)
        mi.isbn = self.isbn(idx, index_is_id=index_is_id)
        id = idx if index_is_id else self.id(idx)
        mi.application_id = id
        return mi

    def vacuum(self):
        self.conn.execute('VACUUM;')
        self.conn.commit()

    def all_ids(self):
        return [i[0] for i in self.conn.get('SELECT id FROM books')]






    def has_id(self, id):
        return self.conn.get('SELECT id FROM books where id=?', (id,), all=False) is not None




class SearchToken(object):

    FIELD_MAP = { 'title'       : 1,
                  'author'      : 2,
                  'publisher'   : 3,
                  'tag'         : 7,
                  'comments'    : 8,
                  'series'      : 9,
                  'format'      : 13,
                 }

    def __init__(self, text_token):
        self.index = -1
        text_token = text_token.strip()
        for field in self.FIELD_MAP.keys():
            if text_token.lower().startswith(field+':'):
                text_token = text_token[len(field)+1:]
                self.index = self.FIELD_MAP[field]
                break

        self.negate = False
        if text_token.startswith('!'):
            self.negate = True
            text_token = text_token[1:]

        self.pattern = re.compile(text_token, re.IGNORECASE)

    def match(self, item):
        if self.index >= 0:
            text = item[self.index]
            if not text:
                text = ''
        else:
            text = ' '.join([item[i] if item[i] else '' for i in self.FIELD_MAP.values()])
        return bool(self.pattern.search(text)) ^ self.negate

def text_to_tokens(text):
    OR = False
    match = re.match(r'\[(.*)\]', text)
    if match:
        text = match.group(1)
        OR = True
    tokens = []
    quot = re.search('"(.*?)"', text)
    while quot:
        tokens.append(quot.group(1))
        text = text.replace('"'+quot.group(1)+'"', '')
        quot = re.search('"(.*?)"', text)
    tokens += text.split(' ')
    ans = []
    for i in tokens:
        try:
            ans.append(SearchToken(i))
        except sre_constants.error:
            continue
    return ans, OR

if __name__ == '__main__':
    sqlite.enable_callback_tracebacks(True)
    db = LibraryDatabase('/home/kovid/temp/library1.db.orig')
