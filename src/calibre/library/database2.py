#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
The database used to store ebook metadata
'''
import os, re, sys, shutil, cStringIO, glob, collections
import sqlite3 as sqlite
from itertools import repeat

from PyQt4.QtCore import QCoreApplication, QThread, QReadWriteLock
from PyQt4.QtGui import QApplication, QPixmap, QImage
__app = None

from calibre.library.database import LibraryDatabase

copyfile = os.link if hasattr(os, 'link') else shutil.copyfile
filesystem_encoding = sys.getfilesystemencoding()
if filesystem_encoding is None: filesystem_encoding = 'utf-8'
 
_filename_sanitize = re.compile(r'[\0\\|\?\*<":>\+\[\]/]')
def sanitize_file_name(name, substitute='_'):
    '''
    Sanitize the filename `name`. All invalid characters are replaced by `substitute`.
    The set of invalid characters is the union of the invalid characters in Windows,
    OS X and Linux. Also removes leading an trailing whitespace.
    **WARNING:** This function also replaces path separators, so only pass file names
    and not full paths to it.
    *NOTE:* This function always returns byte strings, not unicode objects. The byte strings
    are encoded in the filesystem encoding of the platform, or UTF-8. 
    '''
    if isinstance(name, unicode):
        name = name.encode(filesystem_encoding, 'ignore')
    one = _filename_sanitize.sub(substitute, name)
    return re.sub(r'\s', ' ', one).strip()

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
            if self.id_map is None:
                self.build_id_map()
            while True:
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
    

class LibraryDatabase2(LibraryDatabase):
    '''
    An ebook metadata database that stores references to ebook files on disk.
    '''
    PATH_LIMIT = 40 if 'win32' in sys.platform else 100
    @apply
    def user_version():
        doc = 'The user version of this database'
        def fget(self):
            return self.conn.execute('pragma user_version;').next()[0]
        def fset(self, val):
            self.conn.execute('pragma user_version=%d'%int(val))
            self.conn.commit()
        return property(doc=doc, fget=fget, fset=fset)
    
    def connect(self):
        if 'win32' in sys.platform and len(self.library_path) + 4*self.PATH_LIMIT + 10 > 259:
            raise ValueError('Path to library too long. Must be less than %d characters.'%(259-4*self.PATH_LIMIT-10))
        exists = os.path.exists(self.dbpath)
        self.conn = sqlite.connect(self.dbpath, 
                                detect_types=sqlite.PARSE_DECLTYPES|sqlite.PARSE_COLNAMES)
        if exists and self.user_version == 0:
            self.conn.close()
            os.remove(self.dbpath)
            self.conn = sqlite.connect(self.dbpath, 
                                detect_types=sqlite.PARSE_DECLTYPES|sqlite.PARSE_COLNAMES)
        self.conn.row_factory = sqlite.Row if self.row_factory else  lambda cursor, row : list(row)
        self.conn.create_aggregate('concat', 1, Concatenate)
        title_pat = re.compile('^(A|The|An)\s+', re.IGNORECASE)
        
        def title_sort(title):
            match = title_pat.search(title)
            if match:
                prep = match.group(1)
                title = title.replace(prep, '') + ', ' + prep
            return title.strip()
        
        self.conn.create_function('title_sort', 1, title_sort)
        if self.user_version == 0: 
            self.initialize_database()
    
    def __init__(self, library_path, row_factory=False):
        if not os.path.exists(library_path):
            os.makedirs(library_path)
        self.library_path = os.path.abspath(library_path)
        self.row_factory = row_factory
        self.dbpath = os.path.join(library_path, 'metadata.db')
        if isinstance(self.dbpath, unicode):
            self.dbpath = self.dbpath.encode(filesystem_encoding)
        self.connect()
        
        
    def initialize_database(self):
        from calibre.resources import metadata_sqlite
        self.conn.executescript(metadata_sqlite)
        self.user_version = 1
    
    def path(self, index, index_is_id=False):
        'Return the relative path to the directory containing this books files as a unicode string.'
        id = index if index_is_id else self.id()
        path = self.conn.execute('SELECT path FROM books WHERE id=?', (id,)).fetchone()[0].replace('/', os.sep)
        return path
            
    
    def construct_path_name(self, id):
        '''
        Construct the directory name for this book based on its metadata.
        '''
        authors = self.authors(id, index_is_id=True)
        if not authors:
            authors = _('Unknown')
        author = sanitize_file_name(authors.split(',')[0][:self.PATH_LIMIT]).decode(filesystem_encoding)
        title  = sanitize_file_name(self.title(id, index_is_id=True)[:self.PATH_LIMIT]).decode(filesystem_encoding)
        path   = author + '/' + title + ' (%d)'%id
        return path
    
    def construct_file_name(self, id):
        '''
        Construct the file name for this book based on its metadata.
        '''
        authors = self.authors(id, index_is_id=True)
        if not authors:
            authors = _('Unknown')
        author = sanitize_file_name(authors.split(',')[0][:self.PATH_LIMIT]).decode(filesystem_encoding)
        title  = sanitize_file_name(self.title(id, index_is_id=True)[:self.PATH_LIMIT]).decode(filesystem_encoding)
        name   = title + ' - ' + author
        return name
    
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
            name = self.conn.execute('SELECT name FROM data WHERE book=? AND format=?', (id, format)).fetchone()[0]
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
                # Get data as string (cant use file as source and target files may be the same)
                f = self.format(id, format, index_is_id=True, as_file=False)
                if not  f:
                    continue
                stream = cStringIO.StringIO(f)
                self.add_format(id, format, stream, index_is_id=True, path=tpath)
        self.conn.execute('UPDATE books SET path=? WHERE id=?', (path, id))
        self.conn.commit()
        # Delete not needed directories
        norm = lambda x : os.path.abspath(os.path.normcase(x))
        if current_path and os.path.exists(spath):
            if norm(spath) != norm(tpath):
                shutil.rmtree(spath)
                parent  = os.path.dirname(spath)
                if len(os.listdir(parent)) == 0:
                    shutil.rmtree(parent)
            
    def cover(self, index, index_is_id=False, as_file=False, as_image=False):
        '''
        Return the cover image as a bytestring (in JPEG format) or None.
        
        `as_file` : If True return the image as an open file object
        `as_image`: If True return the image as a QImage object
        '''
        id = index if  index_is_id else self.id(index)
        path = os.path.join(self.library_path, self.path(id, index_is_id=True), 'cover.jpg')
        if os.access(path, os.R_OK):
            f = open(path, 'rb')
            if as_image:
                img = QImage()
                img.loadFromData(f.read())
                return img
            return f if as_file else f.read()
    
    def set_cover(self, id, data):
        '''
        Set the cover for this book.
        
        `data`: Can be either a QImage, QPixmap, file object or bytestring
        '''
        path = os.path.join(self.library_path, self.path(id, index_is_id=True), 'cover.jpg')
        if callable(getattr(data, 'save', None)):
            data.save(path)
        else:
            if not QCoreApplication.instance():
                global __app
                __app = QApplication([])
            p = QPixmap()
            if callable(getattr(data, 'read', None)):
                data = data.read()
            p.loadFromData(data)
            p.save(path)
            
    def format(self, index, format, index_is_id=False, as_file=False, mode='r+b'):
        '''
        Return the ebook format as a bytestring or `None` if the format doesn't exist,
        or we don't have permission to write to the ebook file. 
        
        `as_file`: If True the ebook format is returned as a file object opened in `mode` 
        '''
        id = index if index_is_id else self.id(index)
        path = os.path.join(self.library_path, self.path(id, index_is_id=True))
        name = self.conn.execute('SELECT name FROM data WHERE book=? AND format=?', (id, format)).fetchone()[0]
        if name:
            format = ('.' + format.lower()) if format else ''
            path = os.path.join(path, name+format)
            if os.access(path, os.R_OK|os.W_OK):
                f = open(path, mode)
                return f if as_file else f.read()
            self.remove_format(id, format, index_is_id=True)
        
    def add_format(self, index, format, stream, index_is_id=False, path=None):
        id = index if index_is_id else self.id(index)
        if path is None:
            path = os.path.join(self.library_path, self.path(id, index_is_id=True))
        name = self.conn.execute('SELECT name FROM data WHERE book=? AND format=?', (id, format)).fetchone()
        if name:
            self.conn.execute('DELETE FROM data WHERE book=? AND format=?', (id, format))
        name = self.construct_file_name(id)
        ext = ('.' + format.lower()) if format else ''
        shutil.copyfileobj(stream, open(os.path.join(path, name+ext), 'wb'))
        stream.seek(0, 2)
        size=stream.tell()
        self.conn.execute('INSERT INTO data (book,format,uncompressed_size,name) VALUES (?,?,?,?)',
                          (id, format.upper(), size, name))
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
        path = os.path.join(self.library_path, self.path(id, True))
        if os.path.exists(path):
            shutil.rmtree(path)
        self.conn.execute('DELETE FROM books WHERE id=?', (id,))
        self.conn.commit()
    
    def remove_format(self, index, format, index_is_id=False):
        id = index if index_is_id else self.id(index)
        path = os.path.join(self.library_path, self.path(id, index_is_id=True))
        name = self.conn.execute('SELECT name FROM data WHERE book=? AND format=?', (id, format)).fetchone()
        name = name[0] if name else False
        if name:
            ext = ('.' + format.lower()) if format else ''
            path = os.path.join(path, name+ext)
            if os.access(path, os.W_OK):
                os.remove(path)
            self.conn.execute('DELETE FROM data WHERE book=? AND format=?', (id, format.upper()))
            self.conn.commit()
    
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
        if mi.cover_data[1] is not None:
            self.set_cover(id, mi.cover_data[1])
        self.set_path(id, True)
        
    def set_authors(self, id, authors):
        '''
        `authors`: A list of authors.
        '''
        self.conn.execute('DELETE FROM books_authors_link WHERE book=?',(id,))
        for a in authors:
            if not a:
                continue
            a = a.strip()
            author = self.conn.execute('SELECT id from authors WHERE name=?', (a,)).fetchone()
            if author:
                aid = author[0]
                # Handle change of case
                self.conn.execute('UPDATE authors SET name=? WHERE id=?', (a, aid))
            else:
                aid = self.conn.execute('INSERT INTO authors(name) VALUES (?)', (a,)).lastrowid
            try:
                self.conn.execute('INSERT INTO books_authors_link(book, author) VALUES (?,?)', (id, aid))
            except sqlite.IntegrityError: # Sometimes books specify the same author twice in their metadata
                pass
        self.set_path(id, True)
        
    def set_title(self, id, title):
        if not title:
            return
        self.conn.execute('UPDATE books SET title=? WHERE id=?', (title, id))
        self.set_path(id, True)
    
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
            self.set_path(id, True)
            self.conn.commit()
            self.set_metadata(id, mi)
            stream = path if hasattr(path, 'read') else open(path, 'rb')
            stream.seek(0)
            
            self.add_format(id, format, stream, index_is_id=True)
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
     
    def import_book(self, mi, formats):
        series_index = 1 if mi.series_index is None else mi.series_index
        if not mi.authors:
            mi.authors = ['Unknown']
        aus = mi.author_sort if mi.author_sort else ', '.join(mi.authors)
        obj = self.conn.execute('INSERT INTO books(title, uri, series_index, author_sort) VALUES (?, ?, ?, ?)', 
                          (mi.title, None, series_index, aus))
        id = obj.lastrowid
        self.set_path(id, True)
        self.set_metadata(id, mi)
        for path in formats:
            ext = os.path.splitext(path)[1][1:].lower()
            stream = open(path, 'rb')
            self.add_format(id, ext, stream, index_is_id=True)
        self.conn.commit()
    
    def move_library_to(self, newloc):
        if not os.path.exists(newloc):
            os.makedirs(newloc)
        old_dirs = set([])
        for book in self.conn.execute('SELECT id, path FROM books').fetchall():
            path = book[1]
            if not path:
                continue
            dir = path.split('/')[0]
            srcdir = os.path.join(self.library_path, dir)
            tdir = os.path.join(newloc, dir)
            if os.path.exists(tdir):
                shutil.rmtree(tdir)
            shutil.copytree(srcdir, tdir)
            old_dirs.add(srcdir)
        
        dbpath = os.path.join(newloc, os.path.basename(self.dbpath))
        shutil.copyfile(self.dbpath, dbpath)
        opath = self.dbpath
        self.conn.close()
        self.library_path, self.dbpath = newloc, dbpath
        self.connect()
        try:
            os.unlink(opath)
            for dir in old_dirs:
                shutil.rmtree(dir)
        except:
            pass
            
    
    def migrate_old(self, db, progress):
        header = _(u'<p>Migrating old database to ebook library in %s<br><center>')%self.library_path
        progress.setValue(0)
        progress.setLabelText(header)
        QCoreApplication.processEvents()
        db.conn.row_factory = lambda cursor, row : tuple(row)
        books = db.conn.execute('SELECT id, title, sort, timestamp, uri, series_index, author_sort, isbn FROM books ORDER BY id ASC').fetchall()
        progress.setAutoReset(False)
        progress.setRange(0, len(books))
        
        for book in books:
            self.conn.execute('INSERT INTO books(id, title, sort, timestamp, uri, series_index, author_sort, isbn) VALUES(?, ?, ?, ?, ?, ?, ?, ?);', book)
            
        tables = '''
authors  ratings      tags    series    books_tags_link        
comments               publishers
books_authors_link     conversion_options     
books_publishers_link                   
books_ratings_link                        
books_series_link      feeds
'''.split()
        for table in tables:
            rows = db.conn.execute('SELECT * FROM %s ORDER BY id ASC'%table).fetchall() 
            for row in rows:
                self.conn.execute('INSERT INTO %s VALUES(%s)'%(table, ','.join(repeat('?', len(row)))), row)
                
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
        
        
