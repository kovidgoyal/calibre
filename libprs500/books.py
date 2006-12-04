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
from xml.dom.ext import PrettyPrint as PrettyPrint
import xml.dom.minidom as dom
from base64 import b64decode as decode
import time

class book_metadata_field(object):
  def __init__(self, attr, formatter=None): 
    self.attr = attr 
    self.formatter = formatter
  def __get__(self, obj, typ=None):
    """ Return a string. String may be empty if self.attr is absent """
    return self.formatter(obj.elem.getAttribute(self.attr)) if self.formatter else obj.elem.getAttribute(self.attr).strip()

class Book(object):
    title               = book_metadata_field("title")
    author          = book_metadata_field("author", formatter=lambda x: x if x.strip() else "Unknown")
    mime           = book_metadata_field("mime")
    rpath            = book_metadata_field("path")
    id                  = book_metadata_field("id", formatter=int)
    size              = book_metadata_field("size", formatter=int)
    datetime      = book_metadata_field("date", formatter=lambda x:  time.strptime(x, "%a, %d %b %Y %H:%M:%S %Z"))
    
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
  
class BookList(list):
  def __init__(self, prefix="xs1:", root="/Data/media/", file=None):
    list.__init__(self)
    if file:
      self.prefix = prefix
      self.root = root
      file.seek(0)
      self.document = dom.parse(file)
      for book in self.document.getElementsByTagName(self.prefix + "text"): self.append(Book(book, root=root, prefix=prefix))
    self._file = file    
