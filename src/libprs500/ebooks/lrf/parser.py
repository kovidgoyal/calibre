##    Copyright (C) 2007 Kovid Goyal kovid@kovidgoyal.net
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
''''''

import sys, struct, array, os

from libprs500.ebooks.lrf.meta import LRFMetaFile, LRFException
from libprs500.ebooks.lrf.objects import get_object

class LRFDocument(LRFMetaFile):
    
    def __init__(self, stream, temp_dir):
        LRFMetaFile.__init__(self, stream)
        self.temp_dir = os.path.abspath(os.path.expanduser(temp_dir))
        self.scramble_key = self.xor_key
        self.parse_objects()
        
    def parse_objects(self):
        self.objects = {}
        self._file.seek(self.object_index_offset)
        obj_array = array.array("I", self._file.read(4*4*self.number_of_objects))
        if ord(array.array("i",[1]).tostring()[0])==0: #big-endian
            obj_array.byteswap()
        for i in range(self.number_of_objects):
            objid, objoff, objsize = obj_array[i*4:i*4+3]
            self.parse_object(objid, objoff, objsize)
            
    def parse_object(self, objid, objoff, objsize):
        self.objects[objid] = get_object(self._file, objid, objoff, objsize, self.scramble_key)
        
    def get_byte(self):
        return struct.unpack("<B", self.stream.read(1))[0]
    
    def get_word(self):
        return struct.unpack("<H", self.stream.read(2))[0]
    
    def get_dword(self):
        return struct.unpack("<I", self.stream.read(4))[0]
    
    def get_qword(self):
        return struct.unpack("<Q", self.stream.read(8))[0]

def main(args=sys.argv):
    LRFDocument(open(args[1], 'rb'), '.')
    return 0

if __name__ == '__main__':
    sys.exit(main())