from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
The database used to store ebook metadata
'''
import os, re, sys, shutil, cStringIO, glob, collections, textwrap, \
       itertools, functools, traceback
from itertools import repeat
from datetime import datetime
from math import floor

from PyQt4.QtCore import QThread, QReadWriteLock
try:
    from PIL import Image as PILImage
    PILImage
except ImportError:
    import Image as PILImage


from PyQt4.QtGui import QImage

from calibre.ebooks.metadata import title_sort
from calibre.library.database import LibraryDatabase
from calibre.library.sqlite import connect, IntegrityError, DBThread
from calibre.utils.search_query_parser import SearchQueryParser
from calibre.ebooks.metadata import string_to_authors, authors_to_string, \
                                    MetaInformation, authors_to_sort_string
from calibre.ebooks.metadata.meta import get_metadata, metadata_from_formats
from calibre.constants import preferred_encoding, iswindows, isosx, filesystem_encoding
from calibre.ptempfile import PersistentTemporaryFile
from calibre.customize.ui import run_plugins_on_import

from calibre.utils.filenames import ascii_filename
from calibre.ebooks import BOOK_EXTENSIONS

if iswindows:
    import calibre.utils.winshell as winshell

def delete_file(path):
    try:
        winshell.delete_file(path, silent=True, no_confirm=True)
    except:
        os.remove(path)

def delete_tree(path, permanent=False):
    if permanent:
        shutil.rmtree(path)
    else:
        try:
            if not permanent:
                winshell.delete_file(path, silent=True, no_confirm=True)
        except:
            shutil.rmtree(path)

copyfile = os.link if hasattr(os, 'link') else shutil.copyfile

FIELD_MAP = {'id':0, 'title':1, 'authors':2, 'publisher':3, 'rating':4, 'timestamp':5,
             'size':6, 'tags':7, 'comments':8, 'series':9, 'series_index':10,
             'sort':11, 'author_sort':12, 'formats':13, 'isbn':14, 'path':15,
             'lccn':16, 'pubdate':17, 'flags':18, 'uuid':19, 'cover':20}
INDEX_MAP = dict(zip(FIELD_MAP.values(), FIELD_MAP.keys()))


class CoverCache(QThread):

    def __init__(self, library_path, parent=None):
        QThread.__init__(self, parent)
        self.library_path = library_path
        self.id_map = None
        self.id_map_lock = QReadWriteLock()
        self.load_queue = collections.deque()
        self.load_queue_lock = QReadWriteLock(QReadWriteLock.Recursive)
        self.cache = {}
        self.cache_lock = QReadWriteLock()
        self.id_map_stale = True
        self.keep_running = True

    def build_id_map(self):
        self.id_map_lock.lockForWrite()
        self.id_map = {}
        for f in glob.glob(os.path.join(self.library_path, '*', '* (*)', 'cover.jpg')):
            c = os.path.basename(os.path.dirname(f))
            try:
                id = int(re.search(r'\((\d+)\)', c[c.rindex('('):]).group(1))
                self.id_map[id] = f
            except:
                continue
        self.id_map_lock.unlock()
        self.id_map_stale = False


    def set_cache(self, ids):
        self.cache_lock.lockForWrite()
        already_loaded = set([])
        for id in self.cache.keys():
            if id in ids:
                already_loaded.add(id)
            else:
                self.cache.pop(id)
        self.cache_lock.unlock()
        ids = [i for i in ids if i not in already_loaded]
        self.load_queue_lock.lockForWrite()
        self.load_queue = collections.deque(ids)
        self.load_queue_lock.unlock()


    def run(self):
        while self.keep_running:
            if self.id_map is None or self.id_map_stale:
                self.build_id_map()
            while True: # Load images from the load queue
                self.load_queue_lock.lockForWrite()
                try:
                    id = self.load_queue.popleft()
                except IndexError:
                    break
                finally:
                    self.load_queue_lock.unlock()

                self.cache_lock.lockForRead()
                need = True
                if id in self.cache.keys():
                    need = False
                self.cache_lock.unlock()
                if not need:
                    continue
                path = None
                self.id_map_lock.lockForRead()
                if id in self.id_map.keys():
                    path = self.id_map[id]
                else:
                    self.id_map_stale = True
                self.id_map_lock.unlock()
                if path and os.access(path, os.R_OK):
                    try:
                        img = QImage()
                        data = open(path, 'rb').read()
                        img.loadFromData(data)
                        if img.isNull():
                            continue
                    except:
                        continue
                    self.cache_lock.lockForWrite()
                    self.cache[id] = img
                    self.cache_lock.unlock()

            self.sleep(1)

    def stop(self):
        self.keep_running = False

    def cover(self, id):
        val = None
        if self.cache_lock.tryLockForRead(50):
            val = self.cache.get(id, None)
            self.cache_lock.unlock()
        return val

    def clear_cache(self):
        self.cache_lock.lockForWrite()
        self.cache = {}
        self.cache_lock.unlock()

    def refresh(self, ids):
        self.cache_lock.lockForWrite()
        for id in ids:
            self.cache.pop(id, None)
        self.cache_lock.unlock()
        self.load_queue_lock.lockForWrite()
        for id in ids:
            self.load_queue.appendleft(id)
        self.load_queue_lock.unlock()

class ResultCache(SearchQueryParser):

    '''
    Stores sorted and filtered metadata in memory.
    '''

    def __init__(self):
        self._map = self._map_filtered = self._data = []
        self.first_sort = True
        SearchQueryParser.__init__(self)

    def __getitem__(self, row):
        return self._data[self._map_filtered[row]]

    def __len__(self):
        return len(self._map_filtered)

    def __iter__(self):
        for id in self._map_filtered:
            yield self._data[id]

    def universal_set(self):
        return set([i[0] for i in self._data if i is not None])

    def get_matches(self, location, query):
        matches = set([])
        if query and query.strip():
            location = location.lower().strip()
            query = query.lower()
            if not isinstance(query, unicode):
                query = query.decode('utf-8')
            if location in ('tag', 'author', 'format'):
                location += 's'
            all = ('title', 'authors', 'publisher', 'tags', 'comments', 'series', 'formats', 'isbn', 'rating', 'cover')
            MAP = {}
            for x in all:
                MAP[x] = FIELD_MAP[x]
            EXCLUDE_FIELDS = [MAP['rating'], MAP['cover']]
            location = [location] if location != 'all' else list(MAP.keys())
            for i, loc in enumerate(location):
                location[i] = MAP[loc]
            try:
                rating_query = int(query) * 2
            except:
                rating_query = None
            for item in self._data:
                if item is None: continue
                for loc in location:
                    if query == 'false' and not item[loc]:
                        if isinstance(item[loc], basestring):
                            if item[loc].strip() != '':
                                continue
                        matches.add(item[0])
                        break
                    if query == 'true' and item[loc]:
                        if isinstance(item[loc], basestring):
                            if item[loc].strip() == '':
                                continue
                        matches.add(item[0])
                        break
                    if rating_query and item[loc] and loc == MAP['rating'] and rating_query == int(item[loc]):
                        matches.add(item[0])
                        break
                    if item[loc] and loc not in EXCLUDE_FIELDS and query in item[loc].lower():
                        matches.add(item[0])
                        break

        return matches

    def remove(self, id):
        self._data[id] = None
        if id in self._map:
            self._map.remove(id)
        if id in self._map_filtered:
            self._map_filtered.remove(id)

    def set(self, row, col, val, row_is_id=False):
        id = row if row_is_id else self._map_filtered[row]
        self._data[id][col] = val

    def get(self, row, col, row_is_id=False):
        id = row if row_is_id else self._map_filtered[row]
        return self._data[id][col]

    def index(self, id, cache=False):
        x = self._map if cache else self._map_filtered
        return x.index(id)

    def row(self, id):
        return self.index(id)

    def has_id(self, id):
        try:
            return self._data[id] is not None
        except IndexError:
            pass
        return False

    def refresh_ids(self, db, ids):
        '''
        Refresh the data in the cache for books identified by ids.
        Returns a list of affected rows or None if the rows are filtered.
        '''
        for id in ids:
            try:
                self._data[id] = db.conn.get('SELECT * from meta WHERE id=?',
                        (id,))[0]
                self._data[id].append(db.has_cover(id, index_is_id=True))
            except IndexError:
                return None
        try:
            return map(self.row, ids)
        except ValueError:
            pass
        return None

    def books_added(self, ids, db):
        if not ids:
            return
        self._data.extend(repeat(None, max(ids)-len(self._data)+2))
        for id in ids:
            self._data[id] = db.conn.get('SELECT * from meta WHERE id=?', (id,))[0]
            self._data[id].append(db.has_cover(id, index_is_id=True))
        self._map[0:0] = ids
        self._map_filtered[0:0] = ids

    def books_deleted(self, ids):
        for id in ids:
            self._data[id] = None
            if id in self._map: self._map.remove(id)
            if id in self._map_filtered: self._map_filtered.remove(id)

    def count(self):
        return len(self._map)

    def refresh(self, db, field=None, ascending=True):
        temp = db.conn.get('SELECT * FROM meta')
        self._data = list(itertools.repeat(None, temp[-1][0]+2)) if temp else []
        for r in temp:
            self._data[r[0]] = r
        for item in self._data:
            if item is not None:
                item.append(db.has_cover(item[0], index_is_id=True))
        self._map = [i[0] for i in self._data if i is not None]
        if field is not None:
            self.sort(field, ascending)
        self._map_filtered = list(self._map)

    def seriescmp(self, x, y):
        try:
            ans = cmp(self._data[x][9].lower(), self._data[y][9].lower())
        except AttributeError: # Some entries may be None
            ans = cmp(self._data[x][9], self._data[y][9])
        if ans != 0: return ans
        return cmp(self._data[x][10], self._data[y][10])

    def cmp(self, loc, x, y, asstr=True, subsort=False):
        try:
            ans = cmp(self._data[x][loc].lower(), self._data[y][loc].lower()) if \
                asstr else cmp(self._data[x][loc], self._data[y][loc])
        except AttributeError: # Some entries may be None
            ans = cmp(self._data[x][loc], self._data[y][loc])
        if subsort and ans == 0:
            return cmp(self._data[x][11].lower(), self._data[y][11].lower())
        return ans

    def sort(self, field, ascending, subsort=False):
        field = field.lower().strip()
        if field in ('author', 'tag', 'comment'):
            field += 's'
        if   field == 'date': field = 'timestamp'
        elif field == 'title': field = 'sort'
        elif field == 'authors': field = 'author_sort'
        if self.first_sort:
            subsort = True
            self.first_sort = False
        fcmp = self.seriescmp if field == 'series' else \
            functools.partial(self.cmp, FIELD_MAP[field], subsort=subsort,
                              asstr=field not in ('size', 'rating', 'timestamp'))

        self._map.sort(cmp=fcmp, reverse=not ascending)
        self._map_filtered = [id for id in self._map if id in self._map_filtered]

    def search(self, query):
        if not query or not query.strip():
            self._map_filtered = list(self._map)
            return
        matches = sorted(self.parse(query))
        self._map_filtered = [id for id in self._map if id in matches]


class Tag(object):

    def __init__(self, name, id=None, count=0, state=0):
        self.name = name
        self.id = id
        self.count = count
        self.state = state


class LibraryDatabase2(LibraryDatabase):
    '''
    An ebook metadata database that stores references to ebook files on disk.
    '''
    PATH_LIMIT = 40 if 'win32' in sys.platform else 100
    @dynamic_property
    def user_version(self):
        doc = 'The user version of this database'

        def fget(self):
            return self.conn.get('pragma user_version;', all=False)

        def fset(self, val):
            self.conn.execute('pragma user_version=%d'%int(val))
            self.conn.commit()

        return property(doc=doc, fget=fget, fset=fset)

    def connect(self):
        if 'win32' in sys.platform and len(self.library_path) + 4*self.PATH_LIMIT + 10 > 259:
            raise ValueError('Path to library too long. Must be less than %d characters.'%(259-4*self.PATH_LIMIT-10))
        exists = os.path.exists(self.dbpath)
        self.conn = connect(self.dbpath, self.row_factory)
        if exists and self.user_version == 0:
            self.conn.close()
            os.remove(self.dbpath)
            self.conn = connect(self.dbpath, self.row_factory)
        if self.user_version == 0:
            self.initialize_database()

    def __init__(self, library_path, row_factory=False):
        if not os.path.exists(library_path):
            os.makedirs(library_path)
        self.listeners = set([])
        self.library_path = os.path.abspath(library_path)
        self.row_factory = row_factory
        self.dbpath = os.path.join(library_path, 'metadata.db')
        self.dbpath = os.environ.get('CALIBRE_OVERRIDE_DATABASE_PATH',
                self.dbpath)
        if isinstance(self.dbpath, unicode):
            self.dbpath = self.dbpath.encode(filesystem_encoding)
        self.connect()
        self.is_case_sensitive = not iswindows and not isosx and \
            not os.path.exists(self.dbpath.replace('metadata.db', 'MeTAdAtA.dB'))
        # Upgrade database
        while True:
            meth = getattr(self, 'upgrade_version_%d'%self.user_version, None)
            if meth is None:
                break
            else:
                print 'Upgrading database to version %d...'%(self.user_version+1)
                meth()
                self.conn.commit()
                self.user_version += 1

        self.data    = ResultCache()
        self.search  = self.data.search
        self.refresh = functools.partial(self.data.refresh, self)
        self.sort    = self.data.sort
        self.index   = self.data.index
        self.refresh_ids = functools.partial(self.data.refresh_ids, self)
        self.row     = self.data.row
        self.has_id  = self.data.has_id
        self.count   = self.data.count

        self.refresh()
        self.last_update_check = self.last_modified()


        def get_property(idx, index_is_id=False, loc=-1):
            row = self.data._data[idx] if index_is_id else self.data[idx]
            if row is not None:
                return row[loc]

        for prop in ('author_sort', 'authors', 'comment', 'comments', 'isbn',
                     'publisher', 'rating', 'series', 'series_index', 'tags',
                     'title', 'timestamp', 'uuid'):
            setattr(self, prop, functools.partial(get_property,
                    loc=FIELD_MAP['comments' if prop == 'comment' else prop]))

    def initialize_database(self):
        metadata_sqlite = open(P('metadata_sqlite.sql'), 'rb').read()
        self.conn.executescript(metadata_sqlite)
        self.user_version = 1

    def upgrade_version_1(self):
        '''
        Normalize indices.
        '''
        self.conn.executescript(textwrap.dedent('''\
        DROP INDEX authors_idx;
        CREATE INDEX authors_idx ON books (author_sort COLLATE NOCASE, sort COLLATE NOCASE);
        DROP INDEX series_idx;
        CREATE INDEX series_idx ON series (name COLLATE NOCASE);
        CREATE INDEX series_sort_idx ON books (series_index, id);
        '''))

    def upgrade_version_2(self):
        ''' Fix Foreign key constraints for deleting from link tables. '''
        script = textwrap.dedent('''\
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
        ''')
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


    def last_modified(self):
        ''' Return last modified time as a UTC datetime object'''
        return datetime.utcfromtimestamp(os.stat(self.dbpath).st_mtime)

    def check_if_modified(self):
        if self.last_modified() > self.last_update_check:
            self.refresh()
        self.last_update_check = datetime.utcnow()

    def path(self, index, index_is_id=False):
        'Return the relative path to the directory containing this books files as a unicode string.'
        row = self.data._data[index] if index_is_id else self.data[index]
        return row[FIELD_MAP['path']].replace('/', os.sep)


    def abspath(self, index, index_is_id=False):
        'Return the absolute path to the directory containing this books files as a unicode string.'
        path = os.path.join(self.library_path, self.path(index, index_is_id=index_is_id))
        if not os.path.exists(path):
            os.makedirs(path)
        return path


    def construct_path_name(self, id):
        '''
        Construct the directory name for this book based on its metadata.
        '''
        authors = self.authors(id, index_is_id=True)
        if not authors:
            authors = _('Unknown')
        author = ascii_filename(authors.split(',')[0][:self.PATH_LIMIT]).decode(filesystem_encoding, 'ignore')
        title  = ascii_filename(self.title(id, index_is_id=True)[:self.PATH_LIMIT]).decode(filesystem_encoding, 'ignore')
        path   = author + '/' + title + ' (%d)'%id
        return path

    def construct_file_name(self, id):
        '''
        Construct the file name for this book based on its metadata.
        '''
        authors = self.authors(id, index_is_id=True)
        if not authors:
            authors = _('Unknown')
        author = ascii_filename(authors.split(',')[0][:self.PATH_LIMIT]).decode(filesystem_encoding, 'replace')
        title  = ascii_filename(self.title(id, index_is_id=True)[:self.PATH_LIMIT]).decode(filesystem_encoding, 'replace')
        name   = title + ' - ' + author
        while name.endswith('.'):
            name = name[:-1]
        return name

    def rmtree(self, path, permanent=False):
        if not self.normpath(self.library_path).startswith(self.normpath(path)):
            delete_tree(path, permanent=permanent)

    def normpath(self, path):
        path = os.path.abspath(os.path.realpath(path))
        if not self.is_case_sensitive:
            path = path.lower()
        return path

    def set_path(self, index, index_is_id=False):
        '''
        Set the path to the directory containing this books files based on its
        current title and author. If there was a previous directory, its contents
        are copied and it is deleted.
        '''
        id = index if  index_is_id else self.id(index)
        path = self.construct_path_name(id)
        current_path = self.path(id, index_is_id=True).replace(os.sep, '/')
        formats = self.formats(id, index_is_id=True)
        formats = formats.split(',') if formats else []
        # Check if the metadata used to construct paths has changed
        fname = self.construct_file_name(id)
        changed = False
        for format in formats:
            name = self.conn.get('SELECT name FROM data WHERE book=? AND format=?', (id, format), all=False)
            if name and name != fname:
                changed = True
                break
        if path == current_path and not changed:
            return

        tpath = os.path.join(self.library_path, *path.split('/'))
        if not os.path.exists(tpath):
            os.makedirs(tpath)
        spath = os.path.join(self.library_path, *current_path.split('/'))

        if current_path and os.path.exists(spath): # Migrate existing files
            cdata = self.cover(id, index_is_id=True)
            if cdata is not None:
                open(os.path.join(tpath, 'cover.jpg'), 'wb').write(cdata)
            for format in formats:
                # Get data as string (can't use file as source and target files may be the same)
                f = self.format(id, format, index_is_id=True, as_file=False)
                if not  f:
                    continue
                stream = cStringIO.StringIO(f)
                self.add_format(id, format, stream, index_is_id=True, path=tpath)
        self.conn.execute('UPDATE books SET path=? WHERE id=?', (path, id))
        self.conn.commit()
        self.data.set(id, FIELD_MAP['path'], path, row_is_id=True)
        # Delete not needed directories
        if current_path and os.path.exists(spath):
            if self.normpath(spath) != self.normpath(tpath):
                self.rmtree(spath, permanent=True)
                parent  = os.path.dirname(spath)
                if len(os.listdir(parent)) == 0:
                    self.rmtree(parent, permanent=True)

    def add_listener(self, listener):
        '''
        Add a listener. Will be called on change events with two arguments.
        Event name and list of affected ids.
        '''
        self.listeners.add(listener)

    def notify(self, event, ids=[]):
        'Notify all listeners'
        for listener in self.listeners:
            try:
                listener(event, ids)
            except:
                traceback.print_exc()
                continue

    def cover(self, index, index_is_id=False, as_file=False, as_image=False,
              as_path=False):
        '''
        Return the cover image as a bytestring (in JPEG format) or None.

        `as_file` : If True return the image as an open file object
        `as_image`: If True return the image as a QImage object
        '''
        id = index if  index_is_id else self.id(index)
        path = os.path.join(self.library_path, self.path(id, index_is_id=True), 'cover.jpg')
        if os.access(path, os.R_OK):
            if as_path:
                return path
            f = open(path, 'rb')
            if as_image:
                img = QImage()
                img.loadFromData(f.read())
                return img
            return f if as_file else f.read()

    def timestamp(self, index, index_is_id=False):
        if index_is_id:
            return self.conn.get('SELECT timestamp FROM meta WHERE id=?', (index,), all=False)
        return self.data[index][FIELD_MAP['timestamp']]

    def pubdate(self, index, index_is_id=False):
        if index_is_id:
            return self.conn.get('SELECT pubdate FROM meta WHERE id=?', (index,), all=False)
        return self.data[index][FIELD_MAP['pubdate']]

    def get_metadata(self, idx, index_is_id=False, get_cover=False):
        '''
        Convenience method to return metadata as a L{MetaInformation} object.
        '''
        aum = self.authors(idx, index_is_id=index_is_id)
        if aum: aum = [a.strip().replace('|', ',') for a in aum.split(',')]
        mi = MetaInformation(self.title(idx, index_is_id=index_is_id), aum)
        mi.author_sort = self.author_sort(idx, index_is_id=index_is_id)
        mi.comments    = self.comments(idx, index_is_id=index_is_id)
        mi.publisher   = self.publisher(idx, index_is_id=index_is_id)
        mi.timestamp   = self.timestamp(idx, index_is_id=index_is_id)
        mi.pubdate     = self.pubdate(idx, index_is_id=index_is_id)
        mi.uuid        = self.uuid(idx, index_is_id=index_is_id)
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
        if get_cover:
            mi.cover = self.cover(id, index_is_id=True, as_path=True)
        return mi

    def has_book(self, mi):
        title = mi.title
        if title:
            if not isinstance(title, unicode):
                title = title.decode(preferred_encoding, 'replace')
            return bool(self.conn.get('SELECT id FROM books where title=?', (title,), all=False))
        return False

    def has_cover(self, index, index_is_id=False):
        id = index if  index_is_id else self.id(index)
        path = os.path.join(self.library_path, self.path(id, index_is_id=True), 'cover.jpg')
        return os.access(path, os.R_OK)

    def remove_cover(self, id):
        path = os.path.join(self.library_path, self.path(id, index_is_id=True), 'cover.jpg')
        if os.path.exists(path):
            os.remove(path)

    def set_cover(self, id, data):
        '''
        Set the cover for this book.

        `data`: Can be either a QImage, QPixmap, file object or bytestring
        '''
        path = os.path.join(self.library_path, self.path(id, index_is_id=True), 'cover.jpg')
        if callable(getattr(data, 'save', None)):
            data.save(path)
        else:
            f = data
            if not callable(getattr(data, 'read', None)):
                f = cStringIO.StringIO(data)
            im = PILImage.open(f)
            im.convert('RGB').save(path, 'JPEG')

    def all_formats(self):
        formats = self.conn.get('SELECT format from data')
        if not formats:
            return set([])
        return set([f[0] for f in formats])

    def formats(self, index, index_is_id=False):
        ''' Return available formats as a comma separated list or None if there are no available formats '''
        id = index if index_is_id else self.id(index)
        try:
            formats = self.conn.get('SELECT format FROM data WHERE book=?', (id,))
            formats = map(lambda x:x[0], formats)
        except:
            return None
        ans = []
        for format in formats:
            if self.format_abspath(id, format, index_is_id=True) is not None:
                ans.append(format)
        if not ans:
            return None
        return ','.join(ans)

    def has_format(self, index, format, index_is_id=False):
        return self.format_abspath(index, format, index_is_id) is not None

    def format_abspath(self, index, format, index_is_id=False):
        'Return absolute path to the ebook file of format `format`'
        id = index if index_is_id else self.id(index)
        try:
            name = self.conn.get('SELECT name FROM data WHERE book=? AND format=?', (id, format), all=False)
        except:
            return None
        if name:
            path = os.path.join(self.library_path, self.path(id, index_is_id=True))
            format = ('.' + format.lower()) if format else ''
            fmt_path = os.path.join(path, name+format)
            if os.path.exists(fmt_path):
                return fmt_path
            candidates = glob.glob(os.path.join(path, '*'+format))
            if format and candidates and os.path.exists(candidates[0]):
                shutil.copyfile(candidates[0], fmt_path)
                return fmt_path

    def format(self, index, format, index_is_id=False, as_file=False, mode='r+b'):
        '''
        Return the ebook format as a bytestring or `None` if the format doesn't exist,
        or we don't have permission to write to the ebook file.

        `as_file`: If True the ebook format is returned as a file object opened in `mode`
        '''
        path = self.format_abspath(index, format, index_is_id=index_is_id)
        if path is not None:
            f = open(path, mode)
            ret = f if as_file else f.read()
            if not as_file:
                f.close()
            return ret

    def add_format_with_hooks(self, index, format, fpath, index_is_id=False,
                              path=None, notify=True):
        npath = self.run_import_plugins(fpath, format)
        format = os.path.splitext(npath)[-1].lower().replace('.', '').upper()
        return self.add_format(index, format, open(npath, 'rb'),
                               index_is_id=index_is_id, path=path, notify=notify)

    def add_format(self, index, format, stream, index_is_id=False, path=None, notify=True):
        id = index if index_is_id else self.id(index)
        if path is None:
            path = os.path.join(self.library_path, self.path(id, index_is_id=True))
        name = self.conn.get('SELECT name FROM data WHERE book=? AND format=?', (id, format), all=False)
        if name:
            self.conn.execute('DELETE FROM data WHERE book=? AND format=?', (id, format))
        name = self.construct_file_name(id)
        ext = ('.' + format.lower()) if format else ''
        dest = os.path.join(path, name+ext)
        pdir = os.path.dirname(dest)
        if not os.path.exists(pdir):
            os.makedirs(pdir)
        with open(dest, 'wb') as f:
            shutil.copyfileobj(stream, f)
        stream.seek(0, 2)
        size=stream.tell()
        self.conn.execute('INSERT INTO data (book,format,uncompressed_size,name) VALUES (?,?,?,?)',
                          (id, format.upper(), size, name))
        self.conn.commit()
        self.refresh_ids([id])
        if notify:
            self.notify('metadata', [id])

    def delete_book(self, id, notify=True):
        '''
        Removes book from the result cache and the underlying database.
        '''
        try:
            path = os.path.join(self.library_path, self.path(id, index_is_id=True))
        except:
            path = None
        self.data.remove(id)
        if path and os.path.exists(path):
            try:
                winshell.delete_file(path, no_confirm=True, silent=True)
            except:
                self.rmtree(path)
            parent = os.path.dirname(path)
            if len(os.listdir(parent)) == 0:
                self.rmtree(parent)
        self.conn.execute('DELETE FROM books WHERE id=?', (id,))
        self.conn.commit()
        self.clean()
        self.data.books_deleted([id])
        if notify:
            self.notify('delete', [id])

    def remove_format(self, index, format, index_is_id=False, notify=True):
        id = index if index_is_id else self.id(index)
        name = self.conn.get('SELECT name FROM data WHERE book=? AND format=?', (id, format), all=False)
        if name:
            path = self.format_abspath(id, format, index_is_id=True)
            try:
                delete_file(path)
            except:
                traceback.print_exc()
            self.conn.execute('DELETE FROM data WHERE book=? AND format=?', (id, format.upper()))
            self.conn.commit()
            self.refresh_ids([id])
            if notify:
                self.notify('metadata', [id])

    def clean(self):
        '''
        Remove orphaned entries.
        '''
        st = 'DELETE FROM %(table)s WHERE (SELECT COUNT(id) FROM books_%(ltable)s_link WHERE %(ltable_col)s=%(table)s.id) < 1;'
        self.conn.execute(st%dict(ltable='authors', table='authors', ltable_col='author'))
        self.conn.execute(st%dict(ltable='publishers', table='publishers', ltable_col='publisher'))
        self.conn.execute(st%dict(ltable='tags', table='tags', ltable_col='tag'))
        self.conn.execute(st%dict(ltable='series', table='series', ltable_col='series'))
        self.conn.commit()

    def get_recipes(self):
        return self.conn.get('SELECT id, script FROM feeds')

    def get_recipe(self, id):
        return self.conn.get('SELECT script FROM feeds WHERE id=?', (id,), all=False)

    def get_categories(self, sort_on_count=False):
        categories = {}
        def get(name, category, field='name'):
            ans = self.conn.get('SELECT DISTINCT %s FROM %s'%(field, name))
            ans = [x[0].strip() for x in ans]
            try:
                ans.remove('')
            except ValueError: pass
            categories[category] = list(map(Tag, ans))
            tags = categories[category]
            if name != 'data':
                for tag in tags:
                    id = self.conn.get('SELECT id FROM %s WHERE %s=?'%(name,
                        field), (tag.name,), all=False)
                    tag.id = id
                for tag in tags:
                    if tag.id is not None:
                        tag.count = self.conn.get('SELECT COUNT(id) FROM books_%s_link WHERE %s=?'%(name, category), (tag.id,), all=False)
            else:
                for tag in tags:
                    tag.count = self.conn.get('SELECT COUNT(format) FROM data WHERE format=?',
                            (tag.name,), all=False)
            tags.sort(reverse=sort_on_count, cmp=(lambda
                x,y:cmp(x.count,y.count)) if sort_on_count else (lambda
                    x,y:cmp(x.name, y.name)))
        for x in (('authors', 'author'), ('tags', 'tag'), ('publishers', 'publisher'),
                  ('series', 'series')):
            get(*x)
        get('data', 'format', 'format')

        categories['news'] = []
        newspapers = self.conn.get('SELECT name FROM tags WHERE id IN (SELECT DISTINCT tag FROM books_tags_link WHERE book IN (select book from books_tags_link where tag IN (SELECT id FROM tags WHERE name=?)))', (_('News'),))
        if newspapers:
            newspapers = [f[0] for f in newspapers]
            try:
                newspapers.remove(_('News'))
            except ValueError:
                pass
            categories['news'] = list(map(Tag, newspapers))
            for tag in categories['news']:
                tag.count = self.conn.get('SELECT COUNT(id) FROM books_tags_link WHERE tag IN (SELECT DISTINCT id FROM tags WHERE name=?)', (tag.name,), all=False)

        return categories


    def tags_older_than(self, tag, delta):
        tag = tag.lower().strip()
        now = datetime.now()
        for r in self.data._data:
            if r is not None:
                if (now - r[FIELD_MAP['timestamp']]) > delta:
                    tags = r[FIELD_MAP['tags']]
                    if tags and tag in tags.lower():
                        yield r[FIELD_MAP['id']]

    def get_next_series_num_for(self, series):
        series_id = self.conn.get('SELECT id from series WHERE name=?',
                (series,), all=False)
        if series_id is None:
            return 1.0
        series_num = self.conn.get(
            ('SELECT MAX(series_index) FROM books WHERE id IN '
            '(SELECT book FROM books_series_link where series=?)'),
            (series_id,), all=False)
        if series_num is None:
            return 1.0
        return floor(series_num+1)

    def set(self, row, column, val):
        '''
        Convenience method for setting the title, authors, publisher or rating
        '''
        id = self.data[row][0]
        col = {'title':1, 'authors':2, 'publisher':3, 'rating':4, 'tags':7}[column]

        self.data.set(row, col, val)
        if column == 'authors':
            val = string_to_authors(val)
            self.set_authors(id, val, notify=False)
        elif column == 'title':
            self.set_title(id, val, notify=False)
        elif column == 'publisher':
            self.set_publisher(id, val, notify=False)
        elif column == 'rating':
            self.set_rating(id, val, notify=False)
        elif column == 'tags':
            self.set_tags(id, val.split(','), append=False, notify=False)
        self.data.refresh_ids(self, [id])
        self.set_path(id, True)
        self.notify('metadata', [id])

    def set_metadata(self, id, mi):
        '''
        Set metadata for the book `id` from the `MetaInformation` object `mi`
        '''
        if mi.title:
            self.set_title(id, mi.title)
        if not mi.authors:
                mi.authors = [_('Unknown')]
        authors = []
        for a in mi.authors:
            authors += string_to_authors(a)
        self.set_authors(id, authors, notify=False)
        if mi.author_sort:
            self.set_author_sort(id, mi.author_sort, notify=False)
        if mi.publisher:
            self.set_publisher(id, mi.publisher, notify=False)
        if mi.rating:
            self.set_rating(id, mi.rating, notify=False)
        if mi.series:
            self.set_series(id, mi.series, notify=False)
        if mi.cover_data[1] is not None:
            self.set_cover(id, mi.cover_data[1])
        elif mi.cover is not None and os.access(mi.cover, os.R_OK):
            self.set_cover(id, open(mi.cover, 'rb').read())
        if mi.tags:
            self.set_tags(id, mi.tags, notify=False)
        if mi.comments:
            self.set_comment(id, mi.comments, notify=False)
        if mi.isbn and mi.isbn.strip():
            self.set_isbn(id, mi.isbn, notify=False)
        if mi.series_index:
            self.set_series_index(id, mi.series_index, notify=False)
        if mi.pubdate:
            self.set_pubdate(id, mi.pubdate, notify=False)
        if getattr(mi, 'timestamp', None) is not None:
            self.set_timestamp(id, mi.timestamp, notify=False)
        self.set_path(id, True)
        self.notify('metadata', [id])

    def set_authors(self, id, authors, notify=True):
        '''
        `authors`: A list of authors.
        '''
        if not authors:
            authors = [_('Unknown')]
        self.conn.execute('DELETE FROM books_authors_link WHERE book=?',(id,))
        self.conn.execute('DELETE FROM authors WHERE (SELECT COUNT(id) FROM books_authors_link WHERE author=authors.id) < 1')
        for a in authors:
            if not a:
                continue
            a = a.strip().replace(',', '|')
            if not isinstance(a, unicode):
                a = a.decode(preferred_encoding, 'replace')
            author = self.conn.get('SELECT id from authors WHERE name=?', (a,), all=False)
            if author:
                aid = author
                # Handle change of case
                self.conn.execute('UPDATE authors SET name=? WHERE id=?', (a, aid))
            else:
                aid = self.conn.execute('INSERT INTO authors(name) VALUES (?)', (a,)).lastrowid
            try:
                self.conn.execute('INSERT INTO books_authors_link(book, author) VALUES (?,?)',
                                   (id, aid))
            except IntegrityError: # Sometimes books specify the same author twice in their metadata
                pass
        ss = authors_to_sort_string(authors)
        self.conn.execute('UPDATE books SET author_sort=? WHERE id=?',
                          (ss, id))
        self.conn.commit()
        self.data.set(id, FIELD_MAP['authors'],
                      ','.join([a.replace(',', '|') for a in authors]),
                      row_is_id=True)
        self.data.set(id, FIELD_MAP['author_sort'], ss, row_is_id=True)
        self.set_path(id, True)
        if notify:
            self.notify('metadata', [id])

    def set_title(self, id, title, notify=True):
        if not title:
            return
        if not isinstance(title, unicode):
            title = title.decode(preferred_encoding, 'replace')
        self.conn.execute('UPDATE books SET title=? WHERE id=?', (title, id))
        self.data.set(id, FIELD_MAP['title'], title, row_is_id=True)
        self.data.set(id, FIELD_MAP['sort'],  title_sort(title), row_is_id=True)
        self.set_path(id, True)
        self.conn.commit()
        if notify:
            self.notify('metadata', [id])

    def set_timestamp(self, id, dt, notify=True):
        if dt:
            self.conn.execute('UPDATE books SET timestamp=? WHERE id=?', (dt, id))
            self.data.set(id, FIELD_MAP['timestamp'], dt, row_is_id=True)
            self.conn.commit()
            if notify:
                self.notify('metadata', [id])

    def set_pubdate(self, id, dt, notify=True):
        if dt:
            self.conn.execute('UPDATE books SET pubdate=? WHERE id=?', (dt, id))
            self.data.set(id, FIELD_MAP['pubdate'], dt, row_is_id=True)
            self.conn.commit()
            if notify:
                self.notify('metadata', [id])


    def set_publisher(self, id, publisher, notify=True):
        self.conn.execute('DELETE FROM books_publishers_link WHERE book=?',(id,))
        self.conn.execute('DELETE FROM publishers WHERE (SELECT COUNT(id) FROM books_publishers_link WHERE publisher=publishers.id) < 1')
        if publisher:
            if not isinstance(publisher, unicode):
                publisher = publisher.decode(preferred_encoding, 'replace')
            pub = self.conn.get('SELECT id from publishers WHERE name=?', (publisher,), all=False)
            if pub:
                aid = pub
            else:
                aid = self.conn.execute('INSERT INTO publishers(name) VALUES (?)', (publisher,)).lastrowid
            self.conn.execute('INSERT INTO books_publishers_link(book, publisher) VALUES (?,?)', (id, aid))
            self.conn.commit()
            self.data.set(id, FIELD_MAP['publisher'], publisher, row_is_id=True)
            if notify:
                self.notify('metadata', [id])

    def get_tags(self, id):
        result = self.conn.get(
        'SELECT name FROM tags WHERE id IN (SELECT tag FROM books_tags_link WHERE book=?)',
        (id,), all=True)
        if not result:
            return set([])
        return set([r[0] for r in result])

    def set_tags(self, id, tags, append=False, notify=True):
        '''
        @param tags: list of strings
        @param append: If True existing tags are not removed
        '''
        if not append:
            self.conn.execute('DELETE FROM books_tags_link WHERE book=?', (id,))
            self.conn.execute('DELETE FROM tags WHERE (SELECT COUNT(id) FROM books_tags_link WHERE tag=tags.id) < 1')
        otags = self.get_tags(id)
        for tag in (set(tags)-otags):
            tag = tag.strip()
            if not tag:
                continue
            if not isinstance(tag, unicode):
                tag = tag.decode(preferred_encoding, 'replace')
            existing_tags = self.all_tags()
            lt = [t.lower() for t in existing_tags]
            try:
                idx = lt.index(tag.lower())
            except ValueError:
                idx = -1
            if idx > -1:
                etag = existing_tags[idx]
                tid = self.conn.get('SELECT id FROM tags WHERE name=?', (etag,), all=False)
                if etag != tag:
                    self.conn.execute('UPDATE tags SET name=? WHERE id=?', (tag, tid))
            else:
                tid = self.conn.execute('INSERT INTO tags(name) VALUES(?)', (tag,)).lastrowid

            if not self.conn.get('SELECT book FROM books_tags_link WHERE book=? AND tag=?',
                                        (id, tid), all=False):
                self.conn.execute('INSERT INTO books_tags_link(book, tag) VALUES (?,?)',
                              (id, tid))
        self.conn.commit()
        tags = ','.join(self.get_tags(id))
        self.data.set(id, FIELD_MAP['tags'], tags, row_is_id=True)
        if notify:
            self.notify('metadata', [id])

    def unapply_tags(self, book_id, tags, notify=True):
        for tag in tags:
            id = self.conn.get('SELECT id FROM tags WHERE name=?', (tag,), all=False)
            if id:
                self.conn.execute('DELETE FROM books_tags_link WHERE tag=? AND book=?', (id, book_id))
        self.conn.commit()
        self.data.refresh_ids(self, [book_id])
        if notify:
            self.notify('metadata', [id])

    def is_tag_used(self, tag):
        existing_tags = self.all_tags()
        lt = [t.lower() for t in existing_tags]
        try:
            lt.index(tag.lower())
            return True
        except ValueError:
            return False

    def delete_tag(self, tag):
        existing_tags = self.all_tags()
        lt = [t.lower() for t in existing_tags]
        try:
            idx = lt.index(tag.lower())
        except ValueError:
            idx = -1
        if idx > -1:
            id = self.conn.get('SELECT id FROM tags WHERE name=?', (existing_tags[idx],), all=False)
            if id:
                self.conn.execute('DELETE FROM books_tags_link WHERE tag=?', (id,))
                self.conn.execute('DELETE FROM tags WHERE id=?', (id,))
                self.conn.commit()


    def set_series(self, id, series, notify=True):
        self.conn.execute('DELETE FROM books_series_link WHERE book=?',(id,))
        self.conn.execute('DELETE FROM series WHERE (SELECT COUNT(id) FROM books_series_link WHERE series=series.id) < 1')
        if series:
            if not isinstance(series, unicode):
                series = series.decode(preferred_encoding, 'replace')
            s = self.conn.get('SELECT id from series WHERE name=?', (series,), all=False)
            if s:
                aid = s
            else:
                aid = self.conn.execute('INSERT INTO series(name) VALUES (?)', (series,)).lastrowid
            self.conn.execute('INSERT INTO books_series_link(book, series) VALUES (?,?)', (id, aid))
        self.conn.commit()
        try:
            row = self.row(id)
            if row is not None:
                self.data.set(row, 9, series)
        except ValueError:
            pass
        self.data.set(id, FIELD_MAP['series'], series, row_is_id=True)
        if notify:
            self.notify('metadata', [id])

    def set_series_index(self, id, idx, notify=True):
        if idx is None:
            idx = 1.0
        idx = float(idx)
        self.conn.execute('UPDATE books SET series_index=? WHERE id=?', (idx, id))
        self.conn.commit()
        self.data.set(id, FIELD_MAP['series_index'], idx, row_is_id=True)
        if notify:
            self.notify('metadata', [id])

    def set_rating(self, id, rating, notify=True):
        rating = int(rating)
        self.conn.execute('DELETE FROM books_ratings_link WHERE book=?',(id,))
        rat = self.conn.get('SELECT id FROM ratings WHERE rating=?', (rating,), all=False)
        rat = rat if rat else self.conn.execute('INSERT INTO ratings(rating) VALUES (?)', (rating,)).lastrowid
        self.conn.execute('INSERT INTO books_ratings_link(book, rating) VALUES (?,?)', (id, rat))
        self.conn.commit()
        self.data.set(id, FIELD_MAP['rating'], rating, row_is_id=True)
        if notify:
            self.notify('metadata', [id])

    def set_comment(self, id, text, notify=True):
        self.conn.execute('DELETE FROM comments WHERE book=?', (id,))
        self.conn.execute('INSERT INTO comments(book,text) VALUES (?,?)', (id, text))
        self.conn.commit()
        self.data.set(id, FIELD_MAP['comments'], text, row_is_id=True)
        if notify:
            self.notify('metadata', [id])

    def set_author_sort(self, id, sort, notify=True):
        self.conn.execute('UPDATE books SET author_sort=? WHERE id=?', (sort, id))
        self.conn.commit()
        self.data.set(id, FIELD_MAP['author_sort'], sort, row_is_id=True)
        if notify:
            self.notify('metadata', [id])

    def set_isbn(self, id, isbn, notify=True):
        self.conn.execute('UPDATE books SET isbn=? WHERE id=?', (isbn, id))
        self.conn.commit()
        self.data.set(id, FIELD_MAP['isbn'], isbn, row_is_id=True)
        if notify:
            self.notify('metadata', [id])

    def add_news(self, path, arg):
        format = os.path.splitext(path)[1][1:].lower()
        stream = path if hasattr(path, 'read') else open(path, 'rb')
        stream.seek(0)
        mi = get_metadata(stream, format, use_libprs_metadata=False)
        stream.seek(0)
        mi.series_index = 1.0
        mi.tags = [_('News')]
        if arg['add_title_tag']:
            mi.tags += [arg['title']]
        if arg['custom_tags']:
            mi.tags += arg['custom_tags']
        obj = self.conn.execute('INSERT INTO books(title, author_sort) VALUES (?, ?)',
                              (mi.title, mi.authors[0]))
        id = obj.lastrowid
        self.data.books_added([id], self)
        self.set_path(id, index_is_id=True)
        self.conn.commit()
        self.set_metadata(id, mi)

        self.add_format(id, format, stream, index_is_id=True)
        if not hasattr(path, 'read'):
            stream.close()
        self.conn.commit()
        self.data.refresh_ids(self, [id]) # Needed to update format list and size
        return id

    def run_import_plugins(self, path_or_stream, format):
        format = format.lower()
        if hasattr(path_or_stream, 'seek'):
            path_or_stream.seek(0)
            pt = PersistentTemporaryFile('_import_plugin.'+format)
            shutil.copyfileobj(path_or_stream, pt, 1024**2)
            pt.close()
            path = pt.name
        else:
            path = path_or_stream
        return run_plugins_on_import(path, format)

    def create_book_entry(self, mi, cover=None, add_duplicates=True):
        if not add_duplicates and self.has_book(mi):
            return None
        series_index = 1.0 if mi.series_index is None else mi.series_index
        aus = mi.author_sort if mi.author_sort else ', '.join(mi.authors)
        title = mi.title
        if isinstance(aus, str):
            aus = aus.decode(preferred_encoding, 'replace')
        if isinstance(title, str):
            title = title.decode(preferred_encoding)
        obj = self.conn.execute('INSERT INTO books(title, series_index, author_sort) VALUES (?, ?, ?)',
                            (title, series_index, aus))
        id = obj.lastrowid
        self.data.books_added([id], self)
        self.set_path(id, True)
        self.conn.commit()
        self.set_metadata(id, mi)
        if cover is not None:
            self.set_cover(id, cover)
        return id


    def add_books(self, paths, formats, metadata, add_duplicates=True):
        '''
        Add a book to the database. The result cache is not updated.
        :param:`paths` List of paths to book files or file-like objects
        '''
        formats, metadata = iter(formats), iter(metadata)
        duplicates = []
        ids = []
        for path in paths:
            mi = metadata.next()
            format = formats.next()
            if not add_duplicates and self.has_book(mi):
                duplicates.append((path, format, mi))
                continue
            series_index = 1.0 if mi.series_index is None else mi.series_index
            aus = mi.author_sort if mi.author_sort else ', '.join(mi.authors)
            title = mi.title
            if isinstance(aus, str):
                aus = aus.decode(preferred_encoding, 'replace')
            if isinstance(title, str):
                title = title.decode(preferred_encoding)
            obj = self.conn.execute('INSERT INTO books(title, series_index, author_sort) VALUES (?, ?, ?)',
                              (title, series_index, aus))
            id = obj.lastrowid
            self.data.books_added([id], self)
            ids.append(id)
            self.set_path(id, True)
            self.conn.commit()
            self.set_metadata(id, mi)
            npath = self.run_import_plugins(path, format)
            format = os.path.splitext(npath)[-1].lower().replace('.', '').upper()
            stream = open(npath, 'rb')
            self.add_format(id, format, stream, index_is_id=True)
            stream.close()
        self.conn.commit()
        self.data.refresh_ids(self, ids) # Needed to update format list and size
        if duplicates:
            paths    = list(duplicate[0] for duplicate in duplicates)
            formats  = list(duplicate[1] for duplicate in duplicates)
            metadata = list(duplicate[2] for duplicate in duplicates)
            return (paths, formats, metadata), len(ids)
        return None, len(ids)

    def import_book(self, mi, formats, notify=True):
        series_index = 1.0 if mi.series_index is None else mi.series_index
        if not mi.title:
            mi.title = _('Unknown')
        if not mi.authors:
            mi.authors = [_('Unknown')]
        aus = mi.author_sort if mi.author_sort else authors_to_sort_string(mi.authors)
        if isinstance(aus, str):
            aus = aus.decode(preferred_encoding, 'replace')
        title = mi.title if isinstance(mi.title, unicode) else \
                mi.title.decode(preferred_encoding, 'replace')
        obj = self.conn.execute('INSERT INTO books(title, series_index, author_sort) VALUES (?, ?, ?)',
                          (title, series_index, aus))
        id = obj.lastrowid
        self.data.books_added([id], self)
        self.set_path(id, True)
        self.set_metadata(id, mi)
        for path in formats:
            ext = os.path.splitext(path)[1][1:].lower()
            if ext == 'opf':
                continue
            self.add_format_with_hooks(id, ext, path, index_is_id=True)
        self.conn.commit()
        self.data.refresh_ids(self, [id]) # Needed to update format list and size
        if notify:
            self.notify('add', [id])

    def get_top_level_move_items(self):
        items = set(os.listdir(self.library_path))
        paths = set([])
        for x in self.data.universal_set():
            path = self.path(x, index_is_id=True)
            path = path.split(os.sep)[0]
            paths.add(path)
        paths.add('metadata.db')
        path_map = {}
        for x in paths:
            path_map[x] = x
        if not self.is_case_sensitive:
            for x in items:
                path_map[x.lower()] = x
            items = set(path_map)
            paths = set([x.lower() for x in paths])
        items = items.intersection(paths)
        return items, path_map

    def move_library_to(self, newloc, progress=lambda x: x):
        if not os.path.exists(newloc):
            os.makedirs(newloc)
        old_dirs = set([])
        items, path_map = self.get_top_level_move_items()
        for x in items:
            src = os.path.join(self.library_path, x)
            dest = os.path.join(newloc, path_map[x])
            if os.path.isdir(src):
                if os.path.exists(dest):
                    shutil.rmtree(dest)
                shutil.copytree(src, dest)
                old_dirs.add(src)
            else:
                if os.path.exists(dest):
                    os.remove(dest)
                shutil.copyfile(src, dest)
            x = path_map[x]
            if not isinstance(x, unicode):
                x = x.decode(filesystem_encoding, 'replace')
            progress(x)

        dbpath = os.path.join(newloc, os.path.basename(self.dbpath))
        opath = self.dbpath
        self.conn.close()
        self.library_path, self.dbpath = newloc, dbpath
        self.connect()
        try:
            os.unlink(opath)
        except:
            pass
        for dir in old_dirs:
            try:
                shutil.rmtree(dir)
            except:
                pass

    def __iter__(self):
        for record in self.data._data:
            if record is not None:
                yield record

    def all_ids(self):
        x = FIELD_MAP['id']
        for i in iter(self):
            yield i[x]

    def get_data_as_dict(self, prefix=None, authors_as_string=False):
        '''
        Return all metadata stored in the database as a dict. Includes paths to
        the cover and each format.

        :param prefix: The prefix for all paths. By default, the prefix is the absolute path
        to the library folder.
        '''
        if prefix is None:
            prefix = self.library_path
        FIELDS = set(['title', 'authors', 'author_sort', 'publisher', 'rating',
            'timestamp', 'size', 'tags', 'comments', 'series', 'series_index',
            'isbn', 'uuid', 'pubdate'])
        data = []
        for record in self.data:
            if record is None: continue
            x = {}
            for field in FIELDS:
                x[field] = record[FIELD_MAP[field]]
            data.append(x)
            x['id'] = record[FIELD_MAP['id']]
            x['formats'] = []
            if not x['authors']:
                x['authors'] = _('Unknown')
            x['authors'] = [i.replace('|', ',') for i in x['authors'].split(',')]
            if authors_as_string:
                x['authors'] = authors_to_string(x['authors'])
            x['tags'] = [i.replace('|', ',').strip() for i in x['tags'].split(',')] if x['tags'] else []
            path = os.path.join(prefix, self.path(record[FIELD_MAP['id']], index_is_id=True))
            x['cover'] = os.path.join(path, 'cover.jpg')
            if not self.has_cover(x['id'], index_is_id=True):
                x['cover'] = None
            formats = self.formats(record[FIELD_MAP['id']], index_is_id=True)
            if formats:
                for fmt in formats.split(','):
                    path = self.format_abspath(x['id'], fmt, index_is_id=True)
                    if path is None:
                        continue
                    if prefix != self.library_path:
                        path = os.path.relpath(path, self.library_path)
                        path = os.path.join(prefix, path)
                    x['formats'].append(path)
                    x['fmt_'+fmt.lower()] = path
                x['available_formats'] = [i.upper() for i in formats.split(',')]

        return data

    def migrate_old(self, db, progress):
        from PyQt4.QtCore import QCoreApplication
        header = _(u'<p>Migrating old database to ebook library in %s<br><center>')%self.library_path
        progress.setValue(0)
        progress.setLabelText(header)
        QCoreApplication.processEvents()
        db.conn.row_factory = lambda cursor, row : tuple(row)
        db.conn.text_factory = lambda x : unicode(x, 'utf-8', 'replace')
        books = db.conn.get('SELECT id, title, sort, timestamp, series_index, author_sort, isbn FROM books ORDER BY id ASC')
        progress.setAutoReset(False)
        progress.setRange(0, len(books))

        for book in books:
            self.conn.execute('INSERT INTO books(id, title, sort, timestamp, series_index, author_sort, isbn) VALUES(?, ?, ?, ?, ?, ?, ?, ?);', book)

        tables = '''
authors  ratings      tags    series    books_tags_link
comments               publishers
books_authors_link     conversion_options
books_publishers_link
books_ratings_link
books_series_link      feeds
'''.split()
        for table in tables:
            rows = db.conn.get('SELECT * FROM %s ORDER BY id ASC'%table)
            for row in rows:
                self.conn.execute('INSERT INTO %s VALUES(%s)'%(table, ','.join(repeat('?', len(row)))), row)

        self.conn.commit()
        self.refresh('timestamp', True)
        for i, book in enumerate(books):
            progress.setLabelText(header+_(u'Copying <b>%s</b>')%book[1])
            id = book[0]
            self.set_path(id, True)
            formats = db.formats(id, index_is_id=True)
            if not formats:
                formats = []
            else:
                formats = formats.split(',')
            for format in formats:
                data = db.format(id, format, index_is_id=True)
                if data:
                    self.add_format(id, format, cStringIO.StringIO(data), index_is_id=True)
            cover = db.cover(id, index_is_id=True)
            if cover:
                self.set_cover(id, cover)
            progress.setValue(i+1)
        self.conn.commit()
        progress.setLabelText(_('Compacting database'))
        self.vacuum()
        progress.reset()
        return len(books)

    def find_books_in_directory(self, dirpath, single_book_per_directory):
        dirpath = os.path.abspath(dirpath)
        if single_book_per_directory:
            formats = []
            for path in os.listdir(dirpath):
                path = os.path.abspath(os.path.join(dirpath, path))
                if os.path.isdir(path) or not os.access(path, os.R_OK):
                    continue
                ext = os.path.splitext(path)[1]
                if not ext:
                    continue
                ext = ext[1:].lower()
                if ext not in BOOK_EXTENSIONS and ext != 'opf':
                    continue
                formats.append(path)
            yield formats
        else:
            books = {}
            for path in os.listdir(dirpath):
                path = os.path.abspath(os.path.join(dirpath, path))
                if os.path.isdir(path) or not os.access(path, os.R_OK):
                    continue
                ext = os.path.splitext(path)[1]
                if not ext:
                    continue
                ext = ext[1:].lower()
                if ext not in BOOK_EXTENSIONS:
                    continue

                key = os.path.splitext(path)[0]
                if not books.has_key(key):
                    books[key] = []
                books[key].append(path)

            for formats in books.values():
                yield formats

    def import_book_directory_multiple(self, dirpath, callback=None):
        duplicates = []
        for formats in self.find_books_in_directory(dirpath, False):
            mi = metadata_from_formats(formats)
            if mi.title is None:
                continue
            if self.has_book(mi):
                duplicates.append((mi, formats))
                continue
            self.import_book(mi, formats)
            if callable(callback):
                if callback(mi.title):
                    break
        return duplicates

    def import_book_directory(self, dirpath, callback=None):
        dirpath = os.path.abspath(dirpath)
        formats = self.find_books_in_directory(dirpath, True)
        formats = list(formats)[0]
        if not formats:
            return
        mi = metadata_from_formats(formats)
        if mi.title is None:
            return
        if self.has_book(mi):
            return [(mi, formats)]
        self.import_book(mi, formats)
        if callable(callback):
            callback(mi.title)

    def recursive_import(self, root, single_book_per_directory=True, callback=None):
        root = os.path.abspath(root)
        duplicates  = []
        for dirpath in os.walk(root):
            res = self.import_book_directory(dirpath[0], callback=callback) if \
                single_book_per_directory else \
                  self.import_book_directory_multiple(dirpath[0], callback=callback)
            if res is not None:
                duplicates.extend(res)
            if callable(callback):
                if callback(''):
                    break

        return duplicates

    def get_custom_recipes(self):
        for id, title, script in self.conn.get('SELECT id,title,script FROM feeds'):
            yield id, title, script


    def check_integrity(self, callback):
        callback(0., _('Checking SQL integrity...'))
        user_version = self.user_version
        sql = self.conn.dump()
        self.conn.close()
        dest = self.dbpath+'.tmp'
        if os.path.exists(dest):
            os.remove(dest)
        conn = None
        try:
            ndb = DBThread(dest, None)
            ndb.connect()
            conn = ndb.conn
            conn.execute('create table temp_sequence(id INTEGER PRIMARY KEY AUTOINCREMENT)')
            conn.commit()
            conn.executescript(sql)
            conn.commit()
            conn.execute('pragma user_version=%d'%user_version)
            conn.commit()
            conn.execute('drop table temp_sequence')
            conn.commit()
            conn.close()
        except:
            if conn is not None:
                try:
                    conn.close()
                except:
                    pass
            if os.path.exists(dest):
                os.remove(dest)
            raise
        else:
            os.remove(self.dbpath)
            shutil.copyfile(dest, self.dbpath)
            self.connect()
            self.refresh()
        if os.path.exists(dest):
            os.remove(dest)
        callback(0.1, _('Checking for missing files.'))
        bad = {}
        us = self.data.universal_set()
        total = float(len(us))
        for i, id in enumerate(us):
            formats = self.data.get(id, FIELD_MAP['formats'], row_is_id=True)
            if not formats:
                formats = []
            else:
                formats = [x.lower() for x in formats.split(',')]
            actual_formats = self.formats(id, index_is_id=True)
            if not actual_formats:
                actual_formats = []
            else:
                actual_formats = [x.lower() for x in actual_formats.split(',')]

            for fmt in formats:
                if fmt in actual_formats:
                    continue
                if id not in bad:
                    bad[id] = []
                bad[id].append(fmt)
            callback(0.1+0.9*(1+i)/total, _('Checked id') + ' %d'%id)

        for id in bad:
            for fmt in bad[id]:
                self.conn.execute('DELETE FROM data WHERE book=? AND format=?', (id, fmt.upper()))
        self.conn.commit()
        self.refresh_ids(list(bad.keys()))

        return bad



