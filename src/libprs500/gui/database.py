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
"""
Backend that implements storage of ebooks in an sqlite database.
"""
import sqlite3 as sqlite
import os
from zlib import compress, decompress
from stat import ST_SIZE
from libprs500.lrf.meta import LRFMetaFile, LRFException
from libprs500.metadata.meta import get_metadata
from cStringIO import StringIO as cStringIO

class LibraryDatabase(object):
    
    BOOKS_SQL = \
    """
    create table if not exists books_meta(id INTEGER PRIMARY KEY, title TEXT,
                      authors TEXT, publisher TEXT, size INTEGER,  tags TEXT,
                      date DATE DEFAULT CURRENT_TIMESTAMP, 
                      comments TEXT, rating INTEGER);
    create table if not exists books_data(id INTEGER, extension TEXT, 
                      uncompressed_size INTEGER, data BLOB);
    create table if not exists books_cover(id INTEGER, 
                      uncompressed_size INTEGER, data BLOB); 
    """
    
    def __init__(self, dbpath):    
        self.con = sqlite.connect(dbpath)
        # Allow case insensitive field access by name
        self.con.row_factory = sqlite.Row 
        self.con.executescript(LibraryDatabase.BOOKS_SQL)
    
    def get_cover(self, _id):
        raw = self.con.execute("select data from books_cover where id=?", \
                (_id,)).next()["data"]
        return decompress(str(raw)) if raw else None
    
    def get_extensions(self, _id):
        exts = []
        cur = self.con.execute("select extension from books_data where id=?", \
                                (_id,))
        for row in cur:
            exts.append(row["extension"])
        return exts
    
    def add_book(self, path):
        _file = os.path.abspath(path)
        title, size, cover = os.path.basename(_file), \
                                       os.stat(_file)[ST_SIZE], None
        ext = title[title.rfind(".")+1:].lower() if title.find(".") > -1 else None
        mi = get_metadata(open(_file, "r+b"), ext)
        tags = []
        if not mi.title:
            mi.title = title
        if mi.category:
            tags.append(mi.category)
        if mi.classification:
            tags.append(mi.classification)
        if tags:
            tags = ', '.join(tags)
        else:
            tags = None
        data = open(_file).read()
        usize = len(data)
        data = compress(data)
        csize = 0
        if cover:
            csize = len(cover) 
            cover = sqlite.Binary(compress(cover))
        self.con.execute("insert into books_meta (title, authors, publisher, "+\
                         "size, tags, comments, rating) values "+\
                         "(?,?,?,?,?,?,?)", \
                         (mi.title, mi.author, mi.publisher, size, tags, \
                          mi.comments, None))
        _id =  self.con.execute("select max(id) from books_meta").next()[0]    
        self.con.execute("insert into books_data values (?,?,?,?)", \
                            (_id, ext, usize, sqlite.Binary(data)))
        self.con.execute("insert into books_cover values (?,?,?)", \
                            (_id, csize, cover)) 
        self.con.commit()
        return _id
    
    def get_row_by_id(self, _id, columns):
        """ 
        Return C{columns} of meta data as a dict.
        @param columns: list of column names 
        """
        cols = ",".join([ c for c in columns])
        cur = self.con.execute("select " + cols + " from books_meta where id=?"\
                                    , (_id,))
        row, r = cur.next(), {}
        for c in columns: 
            r[c] = row[c]
        return r
    
    def commit(self): 
        self.con.commit()
    
    def delete_by_id(self, _id):
        self.con.execute("delete from books_meta where id=?", (_id,))
        self.con.execute("delete from books_data where id=?", (_id,))
        self.con.execute("delete from books_cover where id=?", (_id,))
        self.commit()
    
    def get_table(self, columns):
        """ Return C{columns} of the metadata table as a list of dicts. """
        cols = ",".join([ c for c in columns])
        cur = self.con.execute("select " + cols + " from books_meta")
        rows = []
        for row in cur:
            r = {}
            for c in columns: 
                r[c] = row[c]
            rows.append(r)
        return rows
    
    def get_format(self, _id, ext):
        """ 
        Return format C{ext} corresponding to the logical book C{id} or 
        None if the format is unavailable. 
        Format is returned as a string of binary data suitable for
        C{ file.write} operations. 
        """ 
        ext = ext.lower()
        cur = self.con.execute("select data from books_data where id=? and "+\
                               "extension=?",(_id, ext))
        try: 
            data = cur.next()
        except: 
            pass
        else: 
            return decompress(str(data["data"]))
            
    def remove_format(self, _id, ext):
        """ Remove format C{ext} from book C{_id} """
        self.con.execute("delete from books_data where id=? and extension=?", \
                            (_id, ext))
        self.update_max_size(_id)
        self.con.commit()
    
    def add_format(self, _id, ext, data):
        """
        If data for format ext already exists, it is replaced
        @type ext: string or None
        @type data: string or file object
        """
        try:
            data.seek(0)
            data = data.read()
        except AttributeError: 
            pass
        metadata = self.get_metadata(_id)
        if ext: 
            ext = ext.strip().lower()
        if ext == "lrf":
            s = cStringIO()
            print >> s, data
            try:
                lrf = LRFMetaFile(s)
                lrf.author = metadata["authors"]
                lrf.title  = metadata["title"]
                # Not sure if I want to override the lrf freetext field
                # with a possibly null value
                #lrf.free_text = metadata["comments"]
            except LRFException:
                pass
            data = s.getvalue()
            s.close()
        size = len(data)
        
        data = sqlite.Binary(compress(data))
        cur = self.con.execute("select extension from books_data where id=? "+\
                               "and extension=?", (_id, ext))
        present = True
        try: 
            cur.next()
        except: 
            present = False
        if present:
            self.con.execute("update books_data set uncompressed_size=? \
                                where id=? and extension=?", (size, _id, ext))
            self.con.execute("update books_data set data=? where id=? "+\
                             "and extension=?", (data, _id, ext))
        else:
            self.con.execute("insert into books_data \
                (id, extension, uncompressed_size, data) values (?, ?, ?, ?)", \
                (_id, ext, size, data))
        oldsize = self.get_row_by_id(_id, ['size'])['size']
        if size > oldsize:
            self.con.execute("update books_meta set size=? where id=? ", \
                             (size, _id))
        self.con.commit()
    
    def get_metadata(self, _id):
        """ Return metadata in a dict """
        try: 
            row = self.con.execute("select * from books_meta where id=?", \
                                    (_id,)).next()
        except StopIteration: 
            return None
        data = {}
        for field in ("id", "title", "authors", "publisher", "size", "tags",
                      "date", "comments"):
            data[field] = row[field]
        return data
    
    def set_metadata(self, _id, title=None, authors=None, rating=None, \
                               publisher=None, tags=None, comments=None):
        """ 
        Update metadata fields for book C{_id}. Metadata is not updated
        in formats. See L{set_metadata_item}.
        """
        if authors and not len(authors): 
            authors = None
        if publisher and not len(publisher): 
            publisher = None
        if tags and not len(tags): 
            tags = None
        if comments and not len(comments): 
            comments = None
        self.con.execute('update books_meta set title=?, authors=?, '+\
                         'publisher=?, tags=?, comments=?, rating=? '+\
                         'where id=?', \
                         (title, authors, publisher, tags, comments, \
                          rating, _id))
        self.con.commit()
    
    def set_metadata_item(self, _id, col, val):
        """ 
        Convenience method used to set metadata. Metadata is updated 
        automatically in supported formats.
        @param col: If it is either 'title' or 'authors' the value is updated
                    in supported formats as well.
        """
        self.con.execute('update books_meta set '+col+'=? where id=?', \
                          (val, _id))    
        if col in ["authors", "title"]:      
            lrf = self.get_format(_id, "lrf")
            if lrf:
                c = cStringIO()
                c.write(lrf)
                lrf = LRFMetaFile(c)
                if col == "authors": 
                    lrf.authors = val
                else: lrf.title = val
                self.add_format(_id, "lrf", c.getvalue())
        self.con.commit()
    
    def update_cover(self, _id, cover, scaled=None):    
        """
        Update the stored cover. The cover is updated in supported formats 
        as well.
        @param cover: The cover data
        @param scaled: scaled version of cover that shoould be written to
                       format files. If None, cover is used.
        """
        data = None
        size = 0
        if cover:
            size = len(cover) 
            data = sqlite.Binary(compress(cover))    
        self.con.execute('update books_cover set uncompressed_size=?, data=? \
                          where id=?', (size, data, _id))        
        if not scaled:
            scaled = cover
        if scaled:
            lrf = self.get_format(_id, "lrf")
            if lrf:
                c = cStringIO()
                c.write(lrf)
                lrf = LRFMetaFile(c)            
                lrf.thumbnail = scaled
                self.add_format(_id, "lrf", c.getvalue())
                self.update_max_size(_id)
        self.commit()
    
    def update_max_size(self, _id):        
        cur = self.con.execute("select uncompressed_size from books_data \
                                where id=?", (_id,))
        maxsize = 0
        for row in cur:
            maxsize = row[0] if row[0] > maxsize else maxsize
        self.con.execute("update books_meta set size=? where id=? ", \
                             (maxsize, _id))
        self.con.commit()



#if __name__ == "__main__":
#  lbm = LibraryDatabase("/home/kovid/library.db")
#  lbm.add_book("/home/kovid/documents/ebooks/hobbfar01.lrf")
#  lbm.add_book("/home/kovid/documents/ebooks/hobbfar02.lrf")
#  lbm.add_book("/home/kovid/documents/ebooks/hobbfar03.lrf")
#  lbm.add_book("/home/kovid/documents/ebooks/hobblive01.lrf")
#  lbm.add_book("/home/kovid/documents/ebooks/hobbtawny01.lrf")
#  lbm.add_book("/home/kovid/documents/ebooks/hobbtawny02.lrf")
#  lbm.add_book("/home/kovid/documents/ebooks/hobbtawny03.lrf")
#  print lbm.get_table(["id","title"])
