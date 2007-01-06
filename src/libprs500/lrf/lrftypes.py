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

import struct

from libprs500.prstypes import field
from libprs500.lrf.meta import WORD, DWORD

class LRFTag(list):
    """
    Base class for all LRF tags.
    
    An LRFTag is simply a sequence of bytes. The first two bytes are the tag id.
    Tag ids are always of the form (encoded little endian) # f5 where # is a byte.
    Thus there can be atmost 256 distinct tags. 
    """
    id       = field(fmt=WORD, start=0)
    
    def __init__(self, _id, size):
        """
        @param _id: The tag id should be an integer
        @param _size: The initial size of this tag
        """
        list.__init__(self, ['\0' for i in range(size+4)])
        self.id = _id
        
    def pack(self, val, fmt=DWORD, start=0):
        """ 
        Encode C{val} and write it to buffer.
        
        @param fmt: See U{struct<http://docs.python.org/lib/module-struct.html>}
        @param start: Position in buffer at which to write encoded data
        """
        self[start:start+struct.calcsize(fmt)] = struct.pack(fmt, val)
        
    def unpack(self, fmt=DWORD, start=0):
        """ 
        Return decoded data from buffer. 
        
        @param fmt: See U{struct<http://docs.python.org/lib/module-struct.html>}
        @param start: Position in buffer from which to decode
        """
        end = start + struct.calcsize(fmt)    
        return struct.unpack(fmt, "".join(list.__getslice__(self, start, end)))
    
class ObjectStart(LRFTag):
    """ Tag that marks the start of an LRFObject """
    ID = 0xf500
    
    # Stored in 4 bytes. Thus there can be only 1024*1024*1024 objects in an LRF file
    object_id   = field(fmt=DWORD, start=0)
    # Stored in 2 bytes. Thus there can be at most 256**2 distinct object types.
    object_type = field(fmt=WORD, start=4)
    
    def __init__(self, _id, _type):
        LRFTag.__init__(self, ObjectStart.ID, 6)
        self.object_id   = _id
        self.object_type = _type
        
class ObjectEnd(LRFTag):
    """ Tag that marks the end of an LRFObject """
    ID = 0xf501
    
    def __init__(self):
        LRFTag.__init__(self, ObjectEnd.ID, 0)
        
class LRFObject(list):
    """
    Base class for all LRF objects. An LRF object is simply a sequence of 
    L{LRFTag}s. It must start with an L{ObjectStart} tag and end with
    an L{ObjectEnd} tag.
    """
    def __str__(self):
        return "".join(self)
    
class BookAttr(LRFObject):
    """
    Global properties for an LRF ebook. Root element of the LRF element 
    structure.
    """
    