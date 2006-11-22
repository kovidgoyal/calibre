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
This module presents an easy to use interface for getting and setting meta information in LRF files.
Just create an L{LRFMetaFile} object and use its properties to get and set meta information. For example:
  lrf = LRFMetaFile("mybook.lrf")
  print lrf.title, lrf.author
  lrf.category = "History"
"""

import struct, array, zlib, StringIO
import xml.dom.minidom as dom
from xml.dom.ext import Print as Print
from libprs500.prstypes import field

BYTE          = "<B"  #: Unsigned char little endian encoded in 1 byte 
WORD        = "<H"  #: Unsigned short little endian encoded in 2 bytes 
DWORD     = "<I"    #: Unsigned integer little endian encoded in 4 bytes
QWORD     = "<Q"  #: Unsigned long long little endian encoded in 8 bytes

class versioned_field(field):
  def __init__(self, vfield, version, start=0, fmt=WORD):
    field.__init__(self, start=start, fmt=fmt)
    self.vfield, self.version = vfield, version
    
  def enabled(self):
    return self.vfield > self.version
    
  def __get__(self, obj, typ=None):
    if self.enabled(): return field.__get__(self, obj, typ=typ)
    else: return None
    
  def __set__(self, obj, val):
    if not self.enabled(): raise LRFException("Trying to set disabled field")
    else: field.__set__(self, obj, val)

class LRFException(Exception):
  pass

class fixed_stringfield(object):
  """ A field storing a variable length string. """
  def __init__(self, length=8, start=0):
    """
    @param length: Size of this string 
    @param start: The byte at which this field is stored in the buffer
    """
    self._length = length
    self._start = start
    
  def __get__(self, obj, typ=None):    
    length = str(self._length)
    return obj.unpack(start=self._start, fmt="<"+length+"s")[0]
    
  def __set__(self, obj, val):
    if val.__class__.__name__ != 'str': val = str(val)
    if len(val) != self._length: raise LRFException("Trying to set fixed_stringfield with a string of  incorrect length")
    obj.pack(val, start=self._start, fmt="<"+str(len(val))+"s")
    
  def __repr__(self):
    return "A string of length " + str(self._length) + " starting at byte " + str(self._start)

class xml_field(object):
  def __init__(self, tag_name):
    self.tag_name = tag_name
    
  def __get__(self, obj, typ=None):
    document = dom.parseString(obj.info)
    elem = document.getElementsByTagName(self.tag_name)[0]
    elem.normalize() 
    if not elem.hasChildNodes(): return ""      
    return elem.firstChild.data.strip()
    
  def __set__(self, obj, val):
    document = dom.parseString(obj.info)
    elem = document.getElementsByTagName(self.tag_name)[0]      
    elem.normalize()
    while elem.hasChildNodes(): elem.removeChild(elem.lastChild)
    elem.appendChild(dom.Text())
    elem.firstChild.data = val
    s = StringIO.StringIO()
    Print(document, s)
    obj.info = s.getvalue()
    s.close()

class LRFMetaFile(object):
  
  LRF_HEADER = "L\0R\0F\0\0\0"
  
  lrf_header               = fixed_stringfield(length=8, start=0)
  version                    = field(fmt=WORD, start=8)
  xor_key                   = field(fmt=WORD, start=10)
  root_object_id         = field(fmt=DWORD, start=12)
  number_of_objets   = field(fmt=QWORD, start=16)
  object_table_offset = field(fmt=QWORD, start=24)
  binding                    = field(fmt=BYTE, start=36)
  dpi                           = field(fmt=WORD, start=38)
  width                       = field(fmt=WORD, start=42)
  height                     = field(fmt=WORD, start=44)
  color_depth            = field(fmt=BYTE, start=46)
  toc_object_id          = field(fmt=DWORD, start=0x44)
  toc_object_offset    = field(fmt=DWORD, start=0x48)
  compressed_info_size = field(fmt=WORD, start=0x4c)
  thumbnail_type        = versioned_field(version, 800, fmt=WORD, start=0x4e)
  thumbnail_size         = versioned_field(version, 800, fmt=DWORD, start=0x50)
  uncompressed_info_size = versioned_field(compressed_info_size, 0, fmt=DWORD, start=0x54)
  
  title                          = xml_field("Title")
  author                     = xml_field("Author")
  book_id                   = xml_field("BookID")
  publisher                 = xml_field("Publisher")
  label                        = xml_field("Label")
  category                 = xml_field("Category")
  
  language                 = xml_field("Language")
  creator                    = xml_field("Creator")
  creation_date          = xml_field("CreationDate") #: Format is %Y-%m-%d
  producer                  = xml_field("Producer")
  page                        = xml_field("Page")
  
  def safe(func):
    def restore_pos(*args, **kwargs):      
      obj = args[0]
      pos = obj._file.tell()
      res = func(*args, **kwargs)
      obj._file.seek(0,2)
      if obj._file.tell() >= pos:  obj._file.seek(pos)
      return res
    return restore_pos
    
  def safe_property(func):
    def decorator(f):
      def restore_pos(*args, **kwargs):      
        obj = args[0]
        pos = obj._file.tell()
        res = f(*args, **kwargs)
        obj._file.seek(0,2)
        if obj._file.tell() >= pos:  obj._file.seek(pos)
        return res
      return restore_pos
    locals_ = func()
    if locals_.has_key("fget"): locals_["fget"] = decorator(locals_["fget"])
    if locals_.has_key("fset"): locals_["fset"] = decorator(locals_["fset"])
    return property(**locals_)
  
  @safe_property
  def info():
    doc=""" Document meta information in raw XML format """
    def fget(self):
      if self.compressed_info_size == 0:
        raise LRFException("This document has no meta info")      
      size = self.compressed_info_size - 4
      self._file.seek(self.info_start)      
      try:
        stream =  zlib.decompress(self._file.read(size))        
        if len(stream) != self.uncompressed_info_size:          
          raise LRFException("Decompression of document meta info yielded unexpected results")
        return stream
      except zlib.error, e:
        raise LRFException("Unable to decompress document meta information")
    
    def fset(self, info):
      self.uncompressed_info_size = len(info)
      stream = zlib.compress(info)
      self.compressed_info_size = len(stream) + 4
      self._file.seek(self.info_start)
      self._file.write(stream)
      self._file.flush()
    return locals()
  
  @safe_property
  def thumbail_pos():
    def fget(self):
      return self.info_start+ self.compressed_info_size-4
    return locals()
  
  @safe_property
  def thumbnail():    
    def fget(self):
      if self.thumbnail_size:        
        self._file.seek(self.thumbail_pos)
        print hex(self._file.tell())
        return self._file.read(self.thumbnail_size)
    def fset(self, data):
      if self.version <= 800: raise LRFException("Cannot store thumbnails in LRF files of version <= 800")
      orig_size = self.thumbnail_size
      self._file.seek(self.thumbail_pos+orig_size)
      rest_of_file = self._file.read()
      self.thumbnail_size = len(data)
      self._file.seek(self.thumbnail_pos)
      self.file.write(data+rest_of_file)
      delta = len(data) - orig_size
      self.object_table_offset  = self.object_table_offset + delta
      self.toc_object_offset     = self.toc_object_offset + delta
      self._file.flush()
    return locals()
  
  def __init__(self, file):
    """ @param file: A file object opened in the r+b mode """
    file.seek(0,2)
    self.size = file.tell()
    self._file = file
    if self.lrf_header != LRFFile.LRF_HEADER:
      raise LRFException(file.name + " has an invalid LRF header. Are you sure it is an LRF file?")    
    self.info_start = 0x58 if self.version > 800 else 0x53 #: Byte at which the compressed meta information starts
    
  @safe
  def unpack(self, fmt=DWORD, start=0):
    """ 
    Return decoded data from file.
    
    @param fmt: See U{struct<http://docs.python.org/lib/module-struct.html>}
    @param start: Position in file from which to decode
    """
    end = start + struct.calcsize(fmt)
    self._file.seek(start)
    ret =  struct.unpack(fmt, self._file.read(end-start))
    return ret
    
  @safe
  def pack(self, *args, **kwargs):
    """ 
    Encode C{args} and write them to file. C{kwargs} must contain the keywords C{fmt} and C{start}
    
    @param args: The values to pack
    @param fmt: See U{struct<http://docs.python.org/lib/module-struct.html>}
    @param start: Position in file at which to write encoded data
    """
    encoded = struct.pack(kwargs["fmt"], *args)
    self._file.seek(kwargs["start"])
    self._file.write(encoded)
    self._file.flush()
    
  def __add__(self, tb):
    """ Return a LRFFile rather than a list as the sum """
    return LRFFile(list.__add__(self, tb))
    
  def __getslice__(self, start, end):
    """ Return a LRFFile rather than a list as the slice """
    return LRFFile(list.__getslice__(self, start, end))
  
