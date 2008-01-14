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
'''
Support for reading the metadata from a lit file.
'''

import sys, struct, cStringIO, os

from libprs500.ebooks.metadata import MetaInformation
from libprs500.ebooks.metadata.opf import OPFReader

OPF_ATTR_MAP = [
    None,
    "href",   
    "%never-used",
    "%guid",
    "%minimum_level",
    "%attr5",
    "id",
    "href",
    "media-type",
    "fallback",
    "idref",
    "xmlns:dc",
    "xmlns:oebpackage",
    "role",
    "file-as",
    "event",
    "scheme",
    "title",
    "type",
    "unique-identifier",
    "name",
    "content",
    "xml:lang",                 
    ]

OPF_TAG_MAP = [
    None,
    "package",
    "dc:Title",
    "dc:Creator",
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    None,
    "manifest",
    "item",
    "spine",
    "itemref",
    "metadata",
    "dc-metadata",
    "dc:Subject",
    "dc:Description",
    "dc:Publisher",
    "dc:Contributor",
    "dc:Date",
    "dc:Type",
    "dc:Format",
    "dc:Identifier",
    "dc:Source",
    "dc:Language",
    "dc:Relation",
    "dc:Coverage",
    "dc:Rights",
    "x-metadata",
    "meta",
    "tours",
    "tour",
    "site",
    "guide",
    "reference",
    None,
   ]

class DirectoryEntry(object):
    def __init__(self, name, section, offset, size):
        self.name = name
        self.section = section
        self.offset = offset
        self.size = size
        
    def __str__(self):
        return '%s\n\tSection: %d\n\tOffset: %d\n\tSize: %d'%(self.name,
                                        self.section, self.offset, self.size)

class LitReadError(Exception):
    pass

def u32(bytes):
    b = struct.unpack('BBBB', bytes[:4])
    return b[0] + (b[1] << 8) + (b[2] << 16) + (b[3] << 32)

def u16(bytes):
    b = struct.unpack('BB', bytes[:2])
    return b[0] + (b[1] << 8)

def int32(bytes):
    return u32(bytes)&0x7FFFFFFF

def encint(bytes, remaining):
    pos, val = 0, 0
    while remaining > 0:
        b = ord(bytes[pos])
        pos += 1
        remaining -= 1
        val <<= 7
        val |= (b & 0x7f)
        if b & 0x80 == 0: break
    return val, bytes[pos:], remaining 

def read_utf8_char(bytes, pos):
    c = ord(bytes[pos])
    mask = 0x80
    if (c & mask):
        elsize = 0
        while c & mask:
            mask >>= 1
            elsize += 1
        if (mask <= 1) or (mask == 0x40):
            raise LitReadError('Invalid UTF8 character: %s'%(repr(bytes[pos])))
    else:
        elsize = 1
        
    
    if elsize > 1:
        if elsize + pos > len(bytes):
            raise LitReadError('Invalid UTF8 character: %s'%(repr(bytes[pos])))
        c &= (mask - 1)
        for i in range(1, elsize):
            b = ord(bytes[pos+i])
            if (b & 0xC0) != 0x80:
                raise LitReadError('Invalid UTF8 character: %s'%(repr(bytes[pos:pos+i])))
            c = (c << 6) | (b & 0x3F)
    return unichr(c), pos+elsize
            
FLAG_OPENING   = 1
FLAG_CLOSING   = 2
FLAG_BLOCK     = 4
FLAG_HEAD      = 8
FLAG_ATOM      = 16
XML_ENTITIES   = ['&amp;', '&apos;', '&lt;', '&gt;', '&quot;']

class UnBinary(object):
    def __init__(self, bin, manifest, attr_map=OPF_ATTR_MAP, tag_map=OPF_TAG_MAP, 
                 tag_to_attr_map=[[] for i in range(43)]):
        self.manifest = manifest
        self.pending_indent  = 0
        self.lingering_space = 0
        self.was_in_text     = 0
        self.attr_map = attr_map
        self.tag_map  = tag_map
        self.tag_to_attr_map = tag_to_attr_map
        self.opf = self.attr_map is OPF_ATTR_MAP
        self.bin = bin
        self.buf = cStringIO.StringIO()
        self.ampersands = []
        self.binary_to_text()
        self.raw = self.buf.getvalue().lstrip().decode('utf-8') 
        self.escape_ampersands() 

    def escape_ampersands(self):
        offset = 0
        for pos in self.ampersands:
            test = self.raw[pos+offset:pos+offset+6]
            if test.startswith('&#') and ';' in test:
                continue
            escape = True
            for ent in XML_ENTITIES:
                if test.startswith(ent):
                    escape = False
                    break
            if not escape:
                continue
            self.raw = self.raw[:pos+offset] + '&amp;' + self.raw[pos+offset+1:]
            offset += 4
            
    
    def write_spaces(self, depth):
        self.buf.write(u' '.join(u'' for i in range(depth)))
        
    def item_path(self, internal_id):
        for i in self.manifest:
            if i == internal_id:
                return i.path
        raise LitReadError('Could not find item %s'%(internal_id,))
    
    def __unicode__(self):
        return self.raw
    
    def binary_to_text(self, base=0, depth=0):
        space_enabled, saved_space_enabled = 1, 0
        was_indented, is_goingdown = 0, 0
        tag_name = current_map = None
        dynamic_tag = errors = in_censorship = 0
            
        state = 'text'
        index =  base
        flags = 0
        
        while index < len(self.bin):
            c, index = read_utf8_char(self.bin, index)
            if state == 'text':
                if ord(c) == 0:
                    state = 'get flags'
                    continue
                if (not self.was_in_text) or space_enabled:            
                    space_enabled = 0;
                    if c in (' ', '\t', '\n', '\r'): 
                        space_enabled += 1
                    else:
                        self.was_in_text = 1
                if c == '\v': 
                    c = '\n'
                pending_indent = 0
                if c == '&':
                    self.ampersands.append(self.buf.tell()-1)
                self.buf.write(c.encode('utf-8') if isinstance(c, unicode) else c)
            elif state == 'get flags':
                if ord(c) == 0:
                    state = 'text'
                    continue
                flags = ord(c)
                state = 'get tag'
            elif state == 'get tag':
                state = 'text' if ord(c) == 0 else 'get attr'
                if flags & FLAG_OPENING:
                    if space_enabled and ((not self.was_in_text) or (flags &(FLAG_BLOCK|FLAG_HEAD))):
                        self.pending_indent += 1
                    if self.pending_indent or self.opf:
                        was_indented += 1
                        self.buf.write(u'\n')
                        self.write_spaces(depth)
                        pending_indent = 0
                    if (flags & FLAG_HEAD) or (flags & FLAG_BLOCK) or \
                        self.opf or depth == 0:
                        pending_indent = 1
                    tag = ord(c)
                    self.buf.write('<')
                    if not (flags & FLAG_CLOSING):
                        is_goingdown = 1
                    if tag == 0x8000:
                        state = 'get custom length'
                        continue
                    if flags & FLAG_ATOM:
                        raise LitReadError('TODO: Atoms not yet implemented')
                    elif tag < len(self.tag_map):
                        tag_name = self.tag_map[tag]
                        current_map = self.tag_to_attr_map[tag]
                    else:
                        dynamic_tag += 1
                        errors += 1
                        tag_name = '?'+unichr(tag)+'?'
                        current_map = self.tag_to_attr_map[tag]
                        print 'WARNING: tag %s unknown'%(unichr(tag),)
                    
                    self.buf.write(unicode(tag_name).encode('utf-8'))
                elif flags & FLAG_CLOSING:
                    if depth == 0:
                        raise LitReadError('Extra closing tag')
                    self.lingering_space = space_enabled
                    return index
            elif state == 'get attr':
                in_censorship = 0
                if ord(c) == 0:
                    if not is_goingdown:
                        tag_name = None
                        dynamic_tag = 0
                        self.buf.write(' />')
                    else:
                        self.buf.write('>')
                        if not self.opf and (flags & (FLAG_BLOCK|FLAG_HEAD)):
                            pending_indent += 1
                        index = self.binary_to_text(base=index, depth=depth+1)
                        is_goingdown = 0
                        if not tag_name:
                            raise LitReadError('Tag ends before it begins.')
                        saved_space_enabled = space_enabled
                        space_enabled = self.lingering_space
                        if space_enabled and was_indented and not self.was_in_text:
                            self.buf.write('\n')
                            self.write_spaces(depth)
                        self.buf.write('</'+tag_name+'>')
                        if (space_enabled and self.opf) or (flags & (FLAG_BLOCK|FLAG_HEAD)):
                            self.pending_indent += 1
                        dynamic_tag = 0
                        tag_name = None
                        space_enabled = saved_space_enabled
                    
                    self.was_in_text = 0
                    state = 'text'
                else:
                    if ord(c) == 0x8000:
                        state = 'get attr length'
                        continue
                    attr = None
                    if ord(c) < len(current_map) and current_map[ord(c)]:
                        attr = current_map[ord(c)]                        
                    elif ord(c) < len(self.attr_map):
                        attr = self.attr_map[ord(c)]
                    
                    if not attr or not isinstance(attr, basestring):
                        raise LitReadError('Unknown attribute %d in tag %s'%(ord(c), tag_name))
                    
                    if attr.startswith('%'):
                        in_censorship = 1
                        state = 'get value length'
                        continue
                    
                    self.buf.write(' ' + unicode(attr).encode('utf-8') + '=')
                    if attr in ['href', 'src']:
                        state = 'get href'
                    else:
                        state = 'get value length'
            elif state == 'get value length':
                if not in_censorship:
                    self.buf.write('"')
                char_count = ord(c) - 1
                if not char_count:
                    if not in_censorship:
                        self.buf.write('"')
                    in_censorship = 0
                    state = 'get attr'
                state = 'get value'
                if ord(c) == 0xffff:
                    continue
                if char_count < 0 or char_count > len(self.bin)-index:
                    raise LitReadError('Invalid character count %d'%(char_count,))
            elif state == 'get value':
                if char_count == 0xfffe:
                    if not in_censorship:
                        self.buf.write(str(ord(c)-1))
                    in_censorship = 0
                    state = 'get attr'
                elif char_count:
                    if not in_censorship:
                        self.buf.write(c)
                    char_count -= 1
                if not char_count:
                    if not in_censorship:
                        self.buf.write('"')
                    in_censorship = 0
                    state = 'get attr'
            elif state == 'get custom length':
                char_count = ord(c) - 1
                if char_count <= 0 or char_count > len(self.bin)-index:
                    raise LitReadError('Invalid character count %d'%(char_count,))
                dynamic_tag += 1
                state = 'get custom'
                tag_name = ''
            elif state == 'get custom':
                tag += c
                char_count -= 1
                if not char_count:
                    self.buf.write(tag_name)
                    state = 'get attr'
            elif state == 'get attr length':
                char_count = ord(c) - 1
                if char_count <= 0 or char_count > len(self.bin)-index:
                    raise LitReadError('Invalid character count %d'%(char_count,))
                self.buf.write(' ')
                state = 'get custom attr'
            elif state == 'get custom attr':
                self.buf.write(c)
                char_count -= 1
                if not char_count:
                    self.buf.write('=')
                    state = 'get value length'
            elif state == 'get href':
                char_count = ord(c) - 1
                if char_count <= 0:
                    raise LitReadError('Invalid character count %d'%(char_count,))
                href = self.bin[index+1:index+char_count].decode('ascii')
                index += char_count 
                doc, m, frag = href.partition('#')
                path = self.item_path(doc)
                if m and frag:
                    path += m+frag
                self.buf.write((u'"%s"'%(path,)).encode('utf-8'))
                state = 'get attr'
        
        self.lingering_space = space_enabled
        return index 
    
class ManifestItem(object):
    
    def __init__(self, original, internal, mime_type, offset, root, state):
        self.original = original
        self.internal = internal
        self.mime_type = mime_type
        self.offset = offset
        self.root = root
        self.state = state
        self.prefix = 'images' if state == 'images' else 'css' if state == 'css' else ''
        self.prefix = self.prefix + os.sep if self.prefix else ''
        self.path = self.prefix + self.original
        
    def __eq__(self, other):
        if hasattr(other, 'internal'):
            return self.internal == other.internal
        return self.internal == other
    
    def __repr__(self):
        return self.internal + u'->' + self.path 

class LitFile(object):
    
    PIECE_SIZE    = 16
    
    @apply
    def magic():
        def fget(self):
            opos = self._stream.tell()
            self._stream.seek(0)
            val = self._stream.read(8)
            self._stream.seek(opos)
            return val
        return property(fget=fget)
    
    @apply
    def version():
        def fget(self):
            opos = self._stream.tell()
            self._stream.seek(8)
            val = u32(self._stream.read(4))
            self._stream.seek(opos)
            return val
        return property(fget=fget)
    
    @apply
    def hdr_len():
        def fget(self):
            opos = self._stream.tell()
            self._stream.seek(12)
            val = int32(self._stream.read(4))
            self._stream.seek(opos)
            return val
        return property(fget=fget)
    
    @apply
    def num_pieces():
        def fget(self):
            opos = self._stream.tell()
            self._stream.seek(16)
            val = int32(self._stream.read(4))
            self._stream.seek(opos)
            return val
        return property(fget=fget)
    
    @apply
    def sec_hdr_len():
        def fget(self):
            opos = self._stream.tell()
            self._stream.seek(20)
            val = int32(self._stream.read(4))
            self._stream.seek(opos)
            return val
        return property(fget=fget)
    
    @apply
    def guid():
        def fget(self):
            opos = self._stream.tell()
            self._stream.seek(24)
            val = self._stream.read(16)
            self._stream.seek(opos)
            return val
        return property(fget=fget)
    
    @apply
    def header():
        def fget(self):
            opos = self._stream.tell()
            size = self.hdr_len + self.num_pieces*self.PIECE_SIZE + self.sec_hdr_len
            self._stream.seek(0)
            val  = self._stream.read(size)
            self._stream.seek(opos)
            return val
        return property(fget=fget)
    
    def __init__(self, stream):
        self._stream = stream
        if self.magic != 'ITOLITLS':
            raise LitReadError('Not a valid LIT file')
        if self.version != 1:
            raise LitReadError('Unknown LIT version %d'%(self.version,))
        self.read_secondary_header()
        self.read_header_pieces()
        
        
    def read_secondary_header(self):
        opos = self._stream.tell()
        try:
            self._stream.seek(self.hdr_len + self.num_pieces*self.PIECE_SIZE)
            bytes = self._stream.read(self.sec_hdr_len)
            offset = int32(bytes[4:])
            
            while offset < len(bytes):
                blocktype = bytes[offset:offset+4]
                blockver  = u32(bytes[offset+4:])
            
                if blocktype == 'CAOL':
                    if blockver != 2:
                        raise LitReadError('Unknown CAOL block format %d'%(blockver,))
                    self.creator_id     = u32(bytes[offset+12:])
                    self.entry_chunklen = u32(bytes[offset+20:])
                    self.count_chunklen = u32(bytes[offset+24:])
                    self.entry_unknown  = u32(bytes[offset+28:])
                    self.count_unknown  = u32(bytes[offset+32:])
                    offset += 48
                elif blocktype == 'ITSF':
                    if blockver != 4:
                        raise LitReadError('Unknown ITSF block format %d'%(blockver,))
                    if u32(bytes[offset+4+16:]):
                        raise LitReadError('This file has a 64bit content offset')
                    self.content_offset = u32(bytes[offset+16:])
                    self.timestamp      = u32(bytes[offset+24:]) 
                    self.language_id    = u32(bytes[offset+28:])
                    offset += 48
                
            if not hasattr(self, 'content_offset'):
                raise LitReadError('Could not figure out the content offset')
        finally:
            self._stream.seek(opos)

    def read_header_pieces(self):
        opos = self._stream.tell()
        try:
            src = self.header[self.hdr_len:]
            for i in range(self.num_pieces):
                piece = src[i*self.PIECE_SIZE:(i+1)*self.PIECE_SIZE]
                if u32(piece[4:]) != 0 or u32(piece[12:]) != 0:
                    raise LitReadError('Piece %s has 64bit value'%(repr(piece),))
                offset, size = u32(piece), int32(piece[8:])
                self._stream.seek(offset)
                piece = self._stream.read(size)
                if i == 0:
                    continue # Dont need this piece
                elif i == 1:
                    if u32(piece[8:])  != self.entry_chunklen or \
                       u32(piece[12:]) != self.entry_unknown:
                        raise LitReadError('Secondary header does not match piece')
                    self.read_directory(piece)
                elif i == 2:
                    if u32(piece[8:])  != self.count_chunklen or \
                       u32(piece[12:]) != self.count_unknown:
                        raise LitReadError('Secondary header does not match piece')
                    continue # No data needed from this piece
                elif i == 3:
                    self.piece3_guid = piece
                elif i == 4:
                    self.piece4_guid = piece
        finally:
            self._stream.seek(opos)
                
    def read_directory(self, piece):
        self.entries = []
        if not piece.startswith('IFCM'):
            raise LitReadError('Header piece #1 is not main directory.')
        chunk_size, num_chunks = int32(piece[8:12]), int32(piece[24:28])
        
        if 32 + chunk_size*num_chunks != len(piece):
            raise LitReadError('IFCM HEADER has incorrect length')
        
        for chunk in range(num_chunks):
            p = 32 + chunk*chunk_size
            if piece[p:p+4] != 'AOLL':
                continue
            remaining = chunk_size - int32(piece[p+4:p+8]) - 48
            if remaining < 0:
                raise LitReadError('AOLL remaining count is negative')
            
            entries = u16(piece[p+chunk_size-2:])
            
            if entries <= 0: # Hopefully everything will work even without a correct entries count
                entries = (2**16)-1 
            
            piece = piece[p+48:]
            i = 0
            while i < entries:
                if remaining <= 0: break
                namelen, piece, remaining = encint(piece, remaining)
                if namelen != (namelen & 0x7fffffff):
                    raise LitReadError('Directory entry had 64bit name length.')
                if namelen > remaining - 3:
                    raise LitReadError('Read past end of directory chunk')
                name = piece[:namelen]
                piece = piece[namelen:]
                section, piece, remaining = encint(piece, remaining)
                offset, piece, remaining = encint(piece, remaining)
                size, piece, remaining = encint(piece, remaining)
                
                entry = DirectoryEntry(name, section, offset, size)
                if name == '::DataSpace/NameList':
                    self.read_section_names(entry)
                elif name == '/manifest':
                    self.read_manifest(entry)
                elif name == '/meta':
                    self.read_meta(entry)
                self.entries.append(entry)
                i += 1
            
            if not hasattr(self, 'sections'):
                raise LitReadError('Lit file does not have a valid NameList')
            
            if not hasattr(self, 'manifest'):
                raise LitReadError('Lit file does not have a valid manifest')
                
    def read_section_names(self, entry):
        opos = self._stream.tell()
        try:
            self._stream.seek(self.content_offset + entry.offset)
            raw = self._stream.read(entry.size)
            if len(raw) < 4:
                raise LitReadError('Invalid Namelist section')
            pos = 4
            self.num_sections = u16(raw[2:pos])
            
            self.sections = {}
            for section in range(self.num_sections):
                size = u16(raw[pos:pos+2])
                pos += 2
                size = size*2 + 2
                if pos + size > len(raw):
                    raise LitReadError('Invalid Namelist section')
                self.sections[section] = raw[pos:pos+size].decode('utf-16-le')
                pos += size                
        finally:
            self._stream.seek(opos)
                
    def read_manifest(self, entry):
        opos = self._stream.tell()
        try:
            self.manifest = []
            self._stream.seek(self.content_offset + entry.offset)
            raw = self._stream.read(entry.size)
            pos = 0
            while pos < len(raw):
                size = ord(raw[pos])
                if size == 0: break
                pos += 1
                root = raw[pos:pos+size].decode('utf8')
                pos += size
                if pos >= len(raw):
                    raise LitReadError('Truncated manifest.')
                for state in ['spine', 'not spine', 'css', 'images']:
                    num_files = int32(raw[pos:pos+4])
                    pos += 4
                    if num_files == 0: continue
                    
                    i = 0
                    while i < num_files:
                        if pos+5 >= len(raw):
                            raise LitReadError('Truncated manifest.')
                        offset = u32(raw[pos:pos+4])
                        pos += 4
                        
                        slen = ord(raw[pos])
                        pos += 1
                        internal = raw[pos:pos+slen].decode('utf8')
                        pos += slen
                        
                        slen = ord(raw[pos])
                        pos += 1
                        original = raw[pos:pos+slen].decode('utf8')
                        pos += slen
                        
                        slen = ord(raw[pos])
                        pos += 1
                        mime_type = raw[pos:pos+slen].decode('utf8')
                        pos += slen +1
                        
                        self.manifest.append(ManifestItem(original, internal, mime_type, offset, root, state))                        
                        i += 1
        finally:
            self._stream.seek(opos)
            
    def read_meta(self, entry):
        opos = self._stream.tell()
        try:
            self._stream.seek(self.content_offset + entry.offset)
            raw = self._stream.read(entry.size)
            xml = \
'''\
<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE package
  PUBLIC "+//ISBN 0-9673008-1-9//DTD OEB 1.0.1 Package//EN"
  "http://openebook.org/dtds/oeb-1.0.1/oebpkg101.dtd">
'''+\
                unicode(UnBinary(raw, self.manifest))
            self.meta = xml
        finally:
            self._stream.seek(opos)

def get_metadata(stream):
    try:
        litfile = LitFile(stream)
        src = litfile.meta.encode('utf-8')
        mi = OPFReader(cStringIO.StringIO(src))
    except:
        title = stream.name if hasattr(stream, 'name') and stream.name else 'Unknown'
        mi = MetaInformation(title, ['Unknown'])
    return mi
        
        

def main(args=sys.argv):
    if len(args) != 2:
        print >>sys.stderr, 'Usage: %s file.lit'%(args[0],)
        return 1
    mi = get_metadata(open(args[1], 'rb'))
    print unicode(mi)
    return 0

if __name__ == '__main__':
    sys.exit(main())