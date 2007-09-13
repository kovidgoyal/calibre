##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
from libprs500 import __appname__
'''
Backend that implements storage of ebooks in an sqlite database.
'''
import sqlite3 as sqlite
import datetime, re, os, cPickle
from zlib import compress, decompress

class Concatenate(object):
    '''String concatenation aggregator for sqlite'''
    def __init__(self, sep=','):
        self.sep = sep
        self.ans = ''
        
    def step(self, value):
        self.ans += value + self.sep
    
    def finalize(self):
        if not self.ans:
            return None
        if self.sep:
            return self.ans[:-len(self.sep)]
        return self.ans

def _connect(path):
    conn =  sqlite.connect(path, detect_types=sqlite.PARSE_DECLTYPES|sqlite.PARSE_COLNAMES)
    conn.row_factory = lambda cursor, row : list(row)
    conn.create_aggregate('concat', 1, Concatenate)
    title_pat = re.compile('^(A|The|An\s+)', re.IGNORECASE)
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
            authors = authors.split('&')
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
                WHEN (SELECT COUNT(id) FROM books_tags_link WHERE book=OLD.book) > 0
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
    
    def __init__(self, dbpath):
        self.dbpath = dbpath
        self.conn = _connect(dbpath)
        self.cache = []
        self.data  = []
        if self.user_version == 0: # No tables have been created
            LibraryDatabase.create_version1(self.conn)
        if self.user_version == 1: # Upgrade to 2
            LibraryDatabase.upgrade_version1(self.conn)
        
    @apply
    def user_version():
        doc = 'The user version of this database'
        def fget(self):
            return self.conn.execute('pragma user_version;').next()[0]
        return property(doc=doc, fget=fget)
            
    def is_empty(self):
        return not self.conn.execute('SELECT id FROM books LIMIT 1').fetchone()
    
    def refresh(self, sort_field, ascending):
        '''
        Rebuild self.data and self.cache. Filter results are lost. 
        '''
        FIELDS = {'title'  : 'sort',
                  'authors':  'author_sort',
                  'publisher': 'publisher_sort',
                  'size': 'size',
                  'date': 'timestamp',
                  'rating': 'rating'
                  }
        field = FIELDS[sort_field]
        order = 'ASC'
        if not ascending:
            order = 'DESC'
        
        
        self.cache = self.conn.execute('SELECT * from meta ORDER BY '+field+' '
                                       +order).fetchall()
        self.data  = self.cache
        self.conn.commit()
        
    def filter(self, filters, refilter=False):
        '''
        Filter data based on filters. All the filters must match for an item to
        be accepted. Matching is case independent regexp matching.
        @param filters: A list of compiled regexps
        @param refilter: If True filters are applied to the results of the previous
                         filtering.
        '''
        if not filters:
            self.data = self.data if refilter else self.cache
        else:
            matches = []
            for item in self.data if refilter else self.cache:
                keep = True
                test = ' '.join([item[i] if item[i] else '' for i in (1,2,3,7,8,9)])
                for filter in filters:
                    if not filter.search(test):
                        keep = False
                        break
                if keep:
                    matches.append(item)
            self.data = matches
            
    def rows(self):
        return len(self.data) if self.data else 0
    
    def id(self, index):
        return self.data[index][0]
    
    def title(self, index):
        return self.data[index][1]
    
    def authors(self, index, index_is_id=False):
        ''' Authors as a comman separated list or None'''
        if not index_is_id:
            return self.data[index][2]
        return self.conn.execute('SELECT authors FROM meta WHERE id=?',(index,)).fetchone()[0]        
    
    def author_sort(self, index):
        id = self.id(index)
        return self.conn.execute('SELECT author_sort FROM books WHERE id=?', (id,)).fetchone()[0]
            
    def publisher(self, index):
        return self.data[index][3]
    
    def rating(self, index):
        return self.data[index][4]
        
    def timestamp(self, index):
        return self.data[index][5]
        
    def max_size(self, index):
        return self.data[index][6]
    
    def cover(self, index):
        '''Cover as a data string or None'''
        id = self.id(index)
        data = self.conn.execute('SELECT data FROM covers WHERE book=?', (id,)).fetchone()
        if not data or not data[0]:
            return None
        return(decompress(data[0]))
    
    def tags(self, index):
        '''tags as a comman separated list or None'''
        id = self.id(index)
        matches = self.conn.execute('SELECT concat(name) FROM tags WHERE tags.id IN (SELECT tag from books_tags_link WHERE book=?)', (id,)).fetchall()
        if not matches:
            return None
        return matches[0][0]
    
    def series_id(self, index):
        id = self.id(index)
        ans= self.conn.execute('SELECT series from books_series_link WHERE book=?', (id,)).fetchone()
        if ans:
            return ans[0]
        
    def series(self, index):
        id = self.series_id(index)
        ans = self.conn.execute('SELECT name from series WHERE id=?', (id,)).fetchone()
        if ans:
            return ans[0]
        
    def series_index(self, index):
        id = self.id(index)
        return self.conn.execute('SELECT series_index FROM books WHERE id=?', (id,)).fetchone()[0]
    
    def comments(self, index):
        '''Comments as string or None'''
        id = self.id(index)
        matches = self.conn.execute('SELECT text FROM comments WHERE book=?', (id,)).fetchall()
        if not matches:
            return None
        return matches[0][0]
    
    def formats(self, index, index_is_id=False):
        ''' Return available formats as a comma separated list '''
        id = index if index_is_id else self.id(index)
        matches = self.conn.execute('SELECT concat(format) FROM data WHERE data.book=?', (id,)).fetchall()
        if not matches:
            return None
        return matches[0][0]
    
    def format(self, index, format):
        id = self.id(index)
        return decompress(self.conn.execute('SELECT data FROM data WHERE book=? AND format=?', (id, format)).fetchone()[0])
    
    def all_series(self):
        return [ (i[0], i[1]) for i in \
                self.conn.execute('SELECT id, name FROM series').fetchall()]
    
    def conversion_options(self, id, format):
        data = self.conn.execute('SELECT data FROM conversion_options WHERE book=? AND format=?', (id, format.upper())).fetchone()
        if data:
            return cPickle.loads(str(data[0]))
        return None
        
    
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
        
    def remove_format(self, index, ext):
        id = self.id(index)
        self.conn.execute('DELETE FROM data WHERE book=? AND format=?', (id, ext.lower()))
        self.conn.commit()
        
    def set(self, row, column, val):
        ''' 
        Convenience method for setting the title, authors, publisher or rating 
        '''
        id = self.data[row][0]
        cols = {'title' : 1, 'authors': 2, 'publisher': 3, 'rating':4}
        col = cols[column]
        
        self.data[row][col] = val
        for item in self.cache:
            if item[0] == id:
                item[col] = val
                break
        if column == 'authors':
            val = val.split('&,')
            self.set_authors(id, val)
        elif column == 'title':
            self.set_title(id, val)
        elif column == 'publisher':
            self.set_publisher(id, val)
        elif column == 'rating':
            self.set_rating(id, val)
        
    def set_conversion_options(self, id, format, options):
        data = sqlite.Binary(cPickle.dumps(options))
        oid = self.conn.execute('SELECT id FROM conversion_options WHERE book=? AND format=?', (id, format.upper())).fetchone()
        if oid:
            self.conn.execute('UPDATE conversion_options SET data=? WHERE id=?', (data, oid[0]))
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
            author = self.conn.execute('SELECT id from authors WHERE name=?', (a,)).fetchone()
            if author:
                aid = author[0]
            else:
                aid = self.conn.execute('INSERT INTO authors(name) VALUES (?)', (a,)).lastrowid
            self.conn.execute('INSERT INTO books_authors_link(book, author) VALUES (?,?)', (id, aid))
        self.conn.commit()
        
    def set_author_sort(self, id, sort):
        self.conn.execute('UPDATE books SET author_sort=? WHERE id=?', (sort, id))
        self.conn.commit()
        
    def set_title(self, id, title):
        if not title:
            return
        self.conn.execute('UPDATE books SET title=? WHERE id=?', (title, id))
        self.conn.commit()
        
    def set_publisher(self, id, publisher):
        self.conn.execute('DELETE FROM books_publishers_link WHERE book=?',(id,))
        if publisher:
            pub = self.conn.execute('SELECT id from publishers WHERE name=?', (publisher,)).fetchone()
            if pub:
                aid = pub[0]
            else:
                aid = self.conn.execute('INSERT INTO publishers(name) VALUES (?)', (publisher,)).lastrowid
            self.conn.execute('INSERT INTO books_publishers_link(book, publisher) VALUES (?,?)', (id, aid))
        self.conn.commit()
        
    def set_comment(self, id, text):
        self.conn.execute('DELETE FROM comments WHERE book=?', (id,))
        self.conn.execute('INSERT INTO comments(book,text) VALUES (?,?)', (id, text))
        self.conn.commit()
    
    def set_tags(self, id, tags, append=False):
        '''
        @param tags: list of strings
        @param append: If True existing tags are not removed
        '''
        if not append:
            self.conn.execute('DELETE FROM books_tags_link WHERE book=?', (id,))
        tag = set(tags)
        for tag in tags:
            t = self.conn.execute('SELECT id from tags WHERE name=?', (tag,)).fetchone()
            if t:
                tid = t[0]
            else:
                tid = self.conn.execute('INSERT INTO tags(name) VALUES(?)', (tag,)).lastrowid
            if (append and not self.conn.execute('SELECT book FROM books_tags_link WHERE book=? AND tag=?',
                                        (id, tid)).fetchone()) or not append:
                self.conn.execute('INSERT INTO books_tags_link(book, tag) VALUES (?,?)',
                              (id, tid))
        self.conn.commit()
        
        
    def set_series(self, id, series):
        self.conn.execute('DELETE FROM books_series_link WHERE book=?',(id,))
        if series:
            s = self.conn.execute('SELECT id from series WHERE name=?', (series,)).fetchone()
            if s:
                aid = s[0]
            else:
                aid = self.conn.execute('INSERT INTO series(name) VALUES (?)', (series,)).lastrowid
            self.conn.execute('INSERT INTO books_series_link(book, series) VALUES (?,?)', (id, aid))
        self.conn.commit()
            
    def set_series_index(self, id, idx):
        self.conn.execute('UPDATE books SET series_index=? WHERE id=?', (int(idx), id))
        self.conn.commit()
    
    def set_rating(self, id, rating):
        rating = int(rating)
        self.conn.execute('DELETE FROM books_ratings_link WHERE book=?',(id,))
        rat = self.conn.execute('SELECT id FROM ratings WHERE rating=?', (rating,)).fetchone()
        rat = rat[0] if rat else self.conn.execute('INSERT INTO ratings(rating) VALUES (?)', (rating,)).lastrowid
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
    
    def add_books(self, paths, formats, metadata, uris=[]):
        '''
        Add a book to the database. self.data and self.cache are not updated.
        '''
        formats, metadata, uris = iter(formats), iter(metadata), iter(uris)
        for path in paths:
            mi = metadata.next()
            try:
                uri = uris.next()
            except StopIteration:
                uri = None
            if mi.series_index is None:
                mi.series_index = 1
            obj = self.conn.execute('INSERT INTO books(title, uri, series_index) VALUES (?, ?, ?)', 
                              (mi.title, uri, mi.series_index))
            id = obj.lastrowid
            self.conn.commit()
            if not mi.author:
                mi.author = 'Unknown'
            temp = mi.author.split(',')
            authors = []
            for a in temp:
                authors += a.split('&')
            self.set_authors(id, authors)
            if mi.author_sort:
                self.set_author_sort(id, mi.author_sort)
            if mi.publisher:
                self.set_publisher(id, mi.publisher)
            if mi.rating:
                self.set_rating(id, mi.rating)
            if mi.series:
                self.set_series(id, mi.series)
            stream = open(path, 'rb')
            stream.seek(0, 2)
            usize = stream.tell()
            stream.seek(0)
            format = formats.next()
            self.conn.execute('INSERT INTO data(book, format, uncompressed_size, data) VALUES (?,?,?,?)',
                              (id, format, usize, sqlite.Binary(compress(stream.read()))))
            stream.close()
        self.conn.commit()
        
        
    def index(self, id, cache=False):
        data = self.cache if cache else self.data
        for i in range(len(data)):
            if data[i][0] == id:
                return i
    
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
        
    def export_to_dir(self, dir, indices):
        by_author = {}
        for index in indices:
            id = self.id(index)
            au = self.conn.execute('SELECT author_sort FROM books WHERE id=?', 
                                   (id,)).fetchone()[0]
            if not au:
                au = self.authors(index)
                if not au:
                    au = 'Unknown'
                au = au.split(',')[0]         
            if not by_author.has_key(au):
                by_author[au] = []
            by_author[au].append(index)
        for au in by_author.keys():
            apath = os.path.join(dir, au)
            if not os.path.exists(apath):
                os.mkdir(apath)
            for idx in by_author[au]:
                title = self.title(idx)
                tpath = os.path.join(apath, title)
                id = str(self.id(idx))
                if not os.path.exists(tpath):
                    os.mkdir(tpath)
                for fmt in self.formats(idx).split(','):
                    data = self.format(idx, fmt)
                    f = open(os.path.join(tpath, title + ' - ' + au +'_'+id+'.'+fmt.lower()), 'wb')
                    f.write(data)
                    
if __name__ == '__main__':
    db = LibraryDatabase('/home/kovid/library1.db')
    