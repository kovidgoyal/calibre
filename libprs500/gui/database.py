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
import sqlite3 as sqlite
import os, os.path, zlib
from stat import ST_SIZE
from libprs500.lrf.meta import LRFMetaFile


class LibraryDatabase(object):
  
  BOOKS_SQL = """
                           create table if not exists books_meta(id INTEGER PRIMARY KEY, title TEXT, authors TEXT, publisher TEXT, size INTEGER,  tags TEXT,
                                                                                       cover BLOB, date DATE DEFAULT CURRENT_TIMESTAMP, comments TEXT );
                           create table if not exists books_data(id INTEGER, extension TEXT, data BLOB);
                           """
                              
  def __init__(self, dbpath):    
    self.con = sqlite.connect(dbpath)
    self.con.row_factory = sqlite.Row # Allow case insensitive field access by name
    self.con.executescript(LibraryDatabase.BOOKS_SQL)
      
  def get_cover(self, id):
    raw = self.con.execute("select cover from books_meta where id=?", (id,)).next()["cover"]
    return zlib.decompress(str(raw)) if raw else None
    
  def get_extensions(self, id):
    exts = []
    cur = self.con.execute("select extension from books_data where id=?", (id,))
    for row in cur:
      exts.append(row["extension"])
    return exts
  
  def add_book(self, path):
    file = os.path.abspath(path)
    title, author, publisher, size, cover = os.path.basename(file), None, None, os.stat(file)[ST_SIZE], None
    ext = title[title.rfind(".")+1:].lower() if title.find(".") > -1 else None
    if ext == "lrf":
      lrf = LRFMetaFile(open(file, "r+b"))
      title, author, cover, publisher = lrf.title, lrf.author.strip(), lrf.thumbnail, lrf.publisher.strip()
      if "unknown" in publisher.lower(): publisher = None
      if "unknown" in author.lower(): author = None
    file = zlib.compress(open(file).read())
    if cover: cover = sqlite.Binary(zlib.compress(cover))
    self.con.execute("insert into books_meta (title, authors, publisher, size, tags, cover, comments) values (?,?,?,?,?,?)", (title, author, publisher, size, None, cover, None))    
    id =  self.con.execute("select max(id) from books_meta").next()[0]    
    self.con.execute("insert into books_data values (?,?,?)", (id, ext, sqlite.Binary(file)))
    self.con.commit()
    
  def get_row_by_id(self, id, columns):
    """ @param columns: list of column names """
    cols = ",".join([ c for c in columns])
    cur = self.con.execute("select " + cols + " from books_meta where id=?", (id,))
    row, r = cur.next(), {}
    for c in columns: r[c] = row[c]
    return r
  
  def get_table(self, columns):
    cols = ",".join([ c for c in columns])
    cur = self.con.execute("select " + cols + " from books_meta")
    rows = []
    for row in cur:
      r = {}
      for c in columns: r[c] = row[c]
      rows.append(r)
    return rows
  
  def get_format(self, id, ext):
    ext = ext.lower()
    cur = self.cur.execute("select data from books_data where id=? and extension=?",(id, ext))
    try: data = cur.next()
    except: pass
    else: return zlib.decompress(str(data["data"]))
      
  def add_format(self, id, ext, data):
    cur = self.con.execute("select extension from books_data where id=? and extension=?", (id, ext))
    present = True
    try: cur.next()
    except: present = False
    if present:
      self.con.execute("update books_data set data=? where id=? and extension=?", (data, id, ext))
    else:
      self.con.execute("insert into books_data (id, extension, data) values (?, ?, ?)", (id, ext, data))
    self.con.commit()
  
  def get_meta_data(self, id):
    try: row = self.con.execute("select * from books_meta where id=?", (id,)).next()
    except StopIteration: return None
    data = {}
    for field in ("id", "title", "authors", "publisher", "size", "tags", "cover", "date"):
      data[field] = row[field]
    return data
    
  def set_metadata(self, id, title=None, authors=None, publisher=None, tags=None, cover=None, comments=None):
    if authors and not len(authors): authors = None
    if publisher and not len(publisher): publisher = None
    if tags and not len(tags): tags = None
    if comments and not len(comments): comments = None
    if cover: cover = sqlite.Binary(zlib.compress(cover))
    self.con.execute('update books_meta set title=?, authors=?, publisher=?, tags=?, cover=?, comments=? where id=?', (title, authors, publisher, tags, cover, comments, id))
    self.con.commit()
  
  def search(self, query): pass

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
