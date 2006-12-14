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
""" This module contains the logic for dealing with XML book lists found in the reader cache """
from xml.dom.ext import PrettyPrint
import xml.dom.minidom as dom
from base64 import b64decode as decode
from base64 import b64encode as encode
import time

MIME_MAP   = { "lrf":"application/x-sony-bbeb", "rtf":"application/rtf", "pdf":"application/pdf", "txt":"text/plain" }

class book_metadata_field(object):
  def __init__(self, attr, formatter=None, setter=None): 
    self.attr = attr 
    self.formatter = formatter
    self.setter = setter
  
  def __get__(self, obj, typ=None):
    """ Return a string. String may be empty if self.attr is absent """
    return self.formatter(obj.elem.getAttribute(self.attr)) if self.formatter else obj.elem.getAttribute(self.attr).strip()
  
  def __set__(self, obj, val):
      val = self.setter(val) if self.setter else val
      obj.elem.setAttribute(self.attr, str(val))

class Book(object):
    title               = book_metadata_field("title")
    author          = book_metadata_field("author", formatter=lambda x: x if x.strip() else "Unknown")
    mime           = book_metadata_field("mime")
    rpath            = book_metadata_field("path")
    id                  = book_metadata_field("id", formatter=int)
    sourceid       = book_metadata_field("sourceid", formatter=int)
    size              = book_metadata_field("size", formatter=int)
    # When setting this attribute you must use an epoch
    datetime      = book_metadata_field("date", formatter=lambda x:  time.strptime(x, "%a, %d %b %Y %H:%M:%S %Z"), setter=lambda x: time.strftime("%a, %d %b %Y %H:%M:%S GMT", time.gmtime(x)))
    
    @apply
    def thumbnail():
      def fget(self):
        th = self.elem.getElementsByTagName(self.prefix + "thumbnail")
        if len(th):
          for n in th[0].childNodes:
            if n.nodeType == n.ELEMENT_NODE:
              th = n
              break
          rc = ""
          for node in th.childNodes:
            if node.nodeType == node.TEXT_NODE: rc += node.data
          return decode(rc)
      return property(**locals())
          
    @apply
    def path():
      def fget(self):  return self.root + self.rpath
      return property(**locals())
      
    def __init__(self, node, prefix="xs1:", root="/Data/media/"):
      self.elem = node
      self.prefix = prefix
      self.root = root
        
    def __repr__(self):
      return self.title + " by " + self.author+ " at " + self.path
      
    def __str__(self):
      return self.__repr__()
  
  
def fix_ids(media, cache):  
  id = 0
  for child in media.root.childNodes:
    if child.nodeType == child.ELEMENT_NODE and child.hasAttribute("id"):
      child.setAttribute("id", str(id))
      id += 1
  mmaxid = id - 1
  id = mmaxid + 2
  if len(cache):
    for child in cache.root.childNodes:
      if child.nodeType == child.ELEMENT_NODE and child.hasAttribute("sourceid"):
        child.setAttribute("sourceid", str(mmaxid+1))
        child.setAttribute("id", str(id))
        id += 1
  media.document.documentElement.setAttribute("nextID", str(id))

class BookList(list):
  __getslice__ = None
  __setslice__ = None
  
  def __init__(self, prefix="xs1:", root="/Data/media/", file=None):
    list.__init__(self)
    if file:
      self.prefix = prefix
      self.proot = root
      file.seek(0)
      self.document = dom.parse(file)
      self.root = self.document.documentElement #: The root element containing all records
      if prefix == "xs1:": self.root = self.root.getElementsByTagName("records")[0]
      for book in self.document.getElementsByTagName(self.prefix + "text"): self.append(Book(book, root=root, prefix=prefix))
      
  def max_id(self):
    id = -1
    for child in self.root.childNodes:
      if child.nodeType == child.ELEMENT_NODE and child.hasAttribute("id"):
        c = int(child.getAttribute("id"))
        if c > id: id = c
    return id
      
  def has_id(self, id):
    """ Check if a book with id C{ == id} exists already. This *does not* check if id exists in the underlying XML file """
    ans = False
    for book in self: 
      if book.id == id:
        ans = True
        break
    return ans
  
  def delete_book(self, id):
    node = None
    for book in self:
      if book.id == id:
        node = book
        self.remove(book)
        break
    node.elem.parentNode.removeChild(node.elem)
    node.elem.unlink()
  
  def add_book(self, info, name, size, ctime):
    node = self.document.createElement(self.prefix + "text")
    mime = MIME_MAP[name[name.rfind(".")+1:]]
    id = self.max_id()+1
    sourceid = str(self[0].sourceid) if len(self) else "1"
    attrs = { "title":info["title"], "author":info["authors"], "page":"0", "part":"0", "scale":"0", "sourceid":sourceid,  "id":str(id), "date":"", "mime":mime, "path":name, "size":str(size)} 
    for attr in attrs.keys():
      node.setAttributeNode(self.document.createAttribute(attr))
      node.setAttribute(attr, attrs[attr])
    w, h, data = info["cover"] 
    if data:
      th = self.document.createElement(self.prefix + "thumbnail")
      th.setAttribute("width", str(w))
      th.setAttribute("height", str(h))
      jpeg = self.document.createElement(self.prefix + "jpeg")
      jpeg.appendChild(self.document.createTextNode(encode(data)))
      th.appendChild(jpeg)
      node.appendChild(th)
    self.root.appendChild(node)
    book = Book(node, root=self.proot, prefix=self.prefix)
    book.datetime = ctime
    self.append(book)
    
  def write(self, stream):
    PrettyPrint(self.document, stream)
