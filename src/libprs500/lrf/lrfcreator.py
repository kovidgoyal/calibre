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

from cStringIO import StringIO
from zlib import compress
from xml.dom import minidom as dom

from libprs500.lrf.meta import LRFMetaFile, LRFException

GIF_PIXEL = 'GIF89a\x01\x00\x01\x00\xf0\x00\x00Mhh\x00\x00\x00!\xf9\x04\x00\x00'\
            '\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'

def create_lrf_file():
    buff = StringIO()
    buff.write(LRFMetaFile.LRF_HEADER)
    buff.write("".join(['\0' for i in range(0x56 - 6)]))
    lrf = LRFMetaFile(buff)
    lrf.version = 999              # No reason
    lrf.xor_key = 0x30             # No reason
    lrf.root_object_id = 0x32      # No reason
    lrf.binding  = 0x01            # front to back 0x10 for back to front
    lrf.dpi      = 1600            # TODO: Play with this
    lrf.width    = 600             # TODO: Play with this
    lrf.height   = 800             # TODO: Play with this
    lrf.color_depth = 24           # Seems like a good idea
    lrf.toc_object_id = 0x42       # No reason
    lrf.thumbnail_type = 0x14      # GIF
    lrf.thumbnail_size = len(GIF_PIXEL)
    
    doc = dom.getDOMImplementation().createDocument(None, None, None)
    info = doc.createElement('Info')
    info.setAttribute('version', '1.0')
    book_info = doc.createElement('BookInfo')
    doc_info  = doc.createElement('DocInfo')
    info.appendChild(book_info)
    info.appendChild(doc_info)
    info = doc.toxml(encoding='utf-16')
    stream = compress(info)
    lrf.compressed_info_size = 4 + len(stream)
    lrf.uncompressed_info_size = len(info)
    buff.write(stream + GIF_PIXEL)
    pos = buff.tell()
    if pos%16 != 0:
        buff.write("".join(['\0' for i in range(16 - pos%16)]))
        
    
    buff.seek(0)
    return lrf
    
    

class LRFCreator(object):
    pass

if __name__ == "__main__":
    open('test.lrf', 'wb').write(create_lrf_file()._file.read())