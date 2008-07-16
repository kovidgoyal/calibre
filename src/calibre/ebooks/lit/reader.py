__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
'''
Support for reading the metadata from a lit file.
'''

import sys, struct, cStringIO, os
import functools
from itertools import repeat

from calibre import relpath
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf import OPFReader
from calibre.ebooks.lit import LitError
from calibre.ebooks.lit.maps import OPF_MAP, HTML_MAP

OPF_DECL = """"<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE package 
  PUBLIC "+//ISBN 0-9673008-1-9//DTD OEB 1.0.1 Package//EN"
  "http://openebook.org/dtds/oeb-1.0.1/oebpkg101.dtd">
"""
XHTML_DECL = """<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE html PUBLIC
 "+//ISBN 0-9673008-1-9//DTD OEB 1.0.1 Document//EN"
 "http://openebook.org/dtds/oeb-1.0.1/oebdoc101.dtd">
"""

class DirectoryEntry(object):
    def __init__(self, name, section, offset, size):
        self.name = name
        self.section = section
        self.offset = offset
        self.size = size
        
    def __repr__(self):
        return "<DirectoryEntry name='%s' section='%d' offset='%d' size='%d'>" \
            % (self.name, self.section, self.offset, self.size)
        
    def __str__(self):
        return repr(self)

def u32(bytes):
    return struct.unpack('<L', bytes[:4])[0]

def u16(bytes):
    return struct.unpack('<H', bytes[:2])[0]

def int32(bytes):
    return struct.unpack('<l', bytes[:4])[0]

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
            raise LitError('Invalid UTF8 character: %s' % repr(bytes[pos]))
    else:
        elsize = 1
    if elsize > 1:
        if elsize + pos > len(bytes):
            raise LitError('Invalid UTF8 character: %s' % repr(bytes[pos]))
        c &= (mask - 1)
        for i in range(1, elsize):
            b = ord(bytes[pos+i])
            if (b & 0xC0) != 0x80:
                raise LitError(
                    'Invalid UTF8 character: %s' % repr(bytes[pos:pos+i]))
            c = (c << 6) | (b & 0x3F)
    return unichr(c), pos+elsize
            
FLAG_OPENING   = 1
FLAG_CLOSING   = 2
FLAG_BLOCK     = 4
FLAG_HEAD      = 8
FLAG_ATOM      = 16
XML_ENTITIES   = ['&amp;', '&apos;', '&lt;', '&gt;', '&quot;']

class UnBinary(object):
    def __init__(self, bin, manifest, map=OPF_MAP):
        self.manifest = manifest
        self.tag_map, self.attr_map, self.tag_to_attr_map = map
        self.opf = map is OPF_MAP
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
    
    def item_path(self, internal_id):
        for i in self.manifest:
            if i == internal_id:
                return i.path
        raise LitError('Could not find item %s'%(internal_id,))
    
    def __unicode__(self):
        return self.raw
    
    def binary_to_text(self, base=0, depth=0):
        tag_name = current_map = None
        dynamic_tag = errors = 0
        in_censorship = is_goingdown = False
        state = 'text'
        index =  base
        flags = 0
        
        while index < len(self.bin):
            c, index = read_utf8_char(self.bin, index)
            oc = ord(c)
            
            if state == 'text':
                if oc == 0:
                    state = 'get flags'
                    continue
                elif c == '\v':
                    c = '\n'
                elif c == '&':
                    self.ampersands.append(self.buf.tell()-1)
                self.buf.write(c.encode('utf-8'))
            
            elif state == 'get flags':
                if oc == 0:
                    state = 'text'
                    continue
                flags = oc
                state = 'get tag'
            
            elif state == 'get tag':
                state = 'text' if oc == 0 else 'get attr'
                if flags & FLAG_OPENING:
                    tag = oc
                    self.buf.write('<')
                    if not (flags & FLAG_CLOSING):
                        is_goingdown = True
                    if tag == 0x8000:
                        state = 'get custom length'
                        continue
                    if flags & FLAG_ATOM:
                        raise LitError('TODO: Atoms not yet implemented')
                    elif tag < len(self.tag_map):
                        tag_name = self.tag_map[tag]
                        current_map = self.tag_to_attr_map[tag]
                    else:
                        dynamic_tag += 1
                        errors += 1
                        tag_name = '?'+unichr(tag)+'?'
                        current_map = self.tag_to_attr_map[tag]
                        print 'WARNING: tag %s unknown' % unichr(tag)
                    self.buf.write(unicode(tag_name).encode('utf-8'))
                elif flags & FLAG_CLOSING:
                    if depth == 0:
                        raise LitError('Extra closing tag')
                    return index
            
            elif state == 'get attr':
                in_censorship = False
                if oc == 0:
                    if not is_goingdown:
                        tag_name = None
                        dynamic_tag = 0
                        self.buf.write(' />')
                    else:
                        self.buf.write('>')
                        index = self.binary_to_text(base=index, depth=depth+1)
                        is_goingdown = False
                        if not tag_name:
                            raise LitError('Tag ends before it begins.')
                        self.buf.write('</'+tag_name+'>')
                        dynamic_tag = 0
                        tag_name = None
                    state = 'text'
                else:
                    if oc == 0x8000:
                        state = 'get attr length'
                        continue
                    attr = None
                    if oc in current_map and current_map[oc]:
                        attr = current_map[oc]
                    elif oc in self.attr_map:
                        attr = self.attr_map[oc]
                    if not attr or not isinstance(attr, basestring):
                        raise LitError(
                            'Unknown attribute %d in tag %s' % (oc, tag_name))
                    if attr.startswith('%'):
                        in_censorship = True
                        state = 'get value length'
                        continue
                    self.buf.write(' ' + unicode(attr).encode('utf-8') + '=')
                    if attr in ['href', 'src']:
                        state = 'get href length'
                    else:
                        state = 'get value length'
            
            elif state == 'get value length':
                if not in_censorship:
                    self.buf.write('"')
                count = oc - 1
                if count == 0:
                    if not in_censorship:
                        self.buf.write('"')
                    in_censorship = False
                    state = 'get attr'
                    continue
                state = 'get value'
                if oc == 0xffff:
                    continue
                if count < 0 or count > (len(self.bin) - index):
                    raise LitError('Invalid character count %d' % count)
            
            elif state == 'get value':
                if count == 0xfffe:
                    if not in_censorship:
                        self.buf.write('%s"' % (oc - 1))
                    in_censorship = False
                    state = 'get attr'
                elif count > 0:
                    if not in_censorship:
                        self.buf.write(c)
                    count -= 1
                if count == 0:
                    if not in_censorship:
                        self.buf.write('"')
                    in_censorship = False
                    state = 'get attr'
            
            elif state == 'get custom length':
                count = oc - 1
                if count <= 0 or count > len(self.bin)-index:
                    raise LitError('Invalid character count %d' % count)
                dynamic_tag += 1
                state = 'get custom'
                tag_name = ''
            
            elif state == 'get custom':
                tag_name += c
                count -= 1
                if count == 0:
                    self.buf.write(tag_name)
                    state = 'get attr'
            
            elif state == 'get attr length':
                count = oc - 1
                if count <= 0 or count > (len(self.bin) - index):
                    raise LitError('Invalid character count %d' % count)
                self.buf.write(' ')
                state = 'get custom attr'
            
            elif state == 'get custom attr':
                self.buf.write(c)
                count -= 1
                if count == 0:
                    self.buf.write('=')
                    state = 'get value length'

            elif state == 'get href length':
                count = oc - 1
                if count <= 0 or count > (len(self.bin) - index):
                    raise LitError('Invalid character count %d' % count)
                href = ''
                state = 'get href'
                    
            elif state == 'get href':
                href += c
                count -= 1
                if count == 0:
                    doc, m, frag = href[1:].partition('#')
                    path = self.item_path(doc)
                    if m and frag:
                        path += m + frag
                    self.buf.write((u'"%s"' % path).encode('utf-8'))
                    state = 'get attr'
        return index
    
class ManifestItem(object):
    def __init__(self, original, internal, mime_type, offset, root, state):
        self.original = original
        self.internal = internal
        self.mime_type = mime_type
        self.offset = offset
        self.root = root
        self.state = state
        self.prefix = 'images' \
            if state == 'images' else 'css' if state == 'css' else ''
        self.prefix = self.prefix + os.sep if self.prefix else ''
        self.path = self.prefix + self.original
        
    def __eq__(self, other):
        if hasattr(other, 'internal'):
            return self.internal == other.internal
        return self.internal == other
    
    def __repr__(self):
        return self.internal + u'->' + self.path 

def preserve(function):
    def wrapper(self, *args, **kwargs):
        opos = self._stream.tell()
        try:
            return function(self, *args, **kwargs)
        finally:
            self._stream.seek(opos)
    functools.update_wrapper(wrapper, function)
    return wrapper
    
class LitFile(object):
    PIECE_SIZE = 16

    def magic():
        @preserve
        def fget(self):
            self._stream.seek(0)
            return self._stream.read(8)
        return property(fget=fget)
    magic = magic()
    
    def version():
        def fget(self):
            self._stream.seek(8)
            return u32(self._stream.read(4))
        return property(fget=fget)
    version = version()
    
    def hdr_len():
        @preserve
        def fget(self):
            self._stream.seek(12)
            return int32(self._stream.read(4))
        return property(fget=fget)
    hdr_len = hdr_len()
    
    def num_pieces():
        @preserve
        def fget(self):
            self._stream.seek(16)
            return int32(self._stream.read(4))
        return property(fget=fget)
    num_pieces = num_pieces()
    
    def sec_hdr_len():
        @preserve
        def fget(self):
            self._stream.seek(20)
            return int32(self._stream.read(4))
        return property(fget=fget)
    sec_hdr_len = sec_hdr_len()
    
    def guid():
        @preserve
        def fget(self):
            self._stream.seek(24)
            return self._stream.read(16)
        return property(fget=fget)
    guid = guid()
    
    def header():
        @preserve
        def fget(self):
            size = self.hdr_len \
                + (self.num_pieces * self.PIECE_SIZE) \
                + self.sec_hdr_len
            self._stream.seek(0)
            return self._stream.read(size)
        return property(fget=fget)
    header = header()        
    
    def __init__(self, stream):
        self._stream = stream
        if self.magic != 'ITOLITLS':
            raise LitError('Not a valid LIT file')
        if self.version != 1:
            raise LitError('Unknown LIT version %d'%(self.version,))
        self.read_secondary_header()
        self.read_header_pieces()

    @preserve
    def read_secondary_header(self):
        self._stream.seek(self.hdr_len + self.num_pieces*self.PIECE_SIZE)
        bytes = self._stream.read(self.sec_hdr_len)
        offset = int32(bytes[4:])
        while offset < len(bytes):
            blocktype = bytes[offset:offset+4]
            blockver  = u32(bytes[offset+4:])
            if blocktype == 'CAOL':
                if blockver != 2:
                    raise LitError(
                        'Unknown CAOL block format %d' % blockver)
                self.creator_id     = u32(bytes[offset+12:])
                self.entry_chunklen = u32(bytes[offset+20:])
                self.count_chunklen = u32(bytes[offset+24:])
                self.entry_unknown  = u32(bytes[offset+28:])
                self.count_unknown  = u32(bytes[offset+32:])
                offset += 48
            elif blocktype == 'ITSF':
                if blockver != 4:
                    raise LitError(
                        'Unknown ITSF block format %d' % blockver)
                if u32(bytes[offset+4+16:]):
                    raise LitError('This file has a 64bit content offset')
                self.content_offset = u32(bytes[offset+16:])
                self.timestamp      = u32(bytes[offset+24:]) 
                self.language_id    = u32(bytes[offset+28:])
                offset += 48
        if not hasattr(self, 'content_offset'):
            raise LitError('Could not figure out the content offset')
    
    @preserve
    def read_header_pieces(self):
        src = self.header[self.hdr_len:]
        for i in range(self.num_pieces):
            piece = src[i*self.PIECE_SIZE:(i+1)*self.PIECE_SIZE]
            if u32(piece[4:]) != 0 or u32(piece[12:]) != 0:
                raise LitError('Piece %s has 64bit value' % repr(piece))
            offset, size = u32(piece), int32(piece[8:])
            self._stream.seek(offset)
            piece = self._stream.read(size)
            if i == 0:
                continue # Dont need this piece
            elif i == 1:
                if u32(piece[8:])  != self.entry_chunklen or \
                   u32(piece[12:]) != self.entry_unknown:
                    raise LitError('Secondary header does not match piece')
                self.read_directory(piece)
            elif i == 2:
                if u32(piece[8:])  != self.count_chunklen or \
                   u32(piece[12:]) != self.count_unknown:
                    raise LitError('Secondary header does not match piece')
                continue # No data needed from this piece
            elif i == 3:
                self.piece3_guid = piece
            elif i == 4:
                self.piece4_guid = piece
                
    def read_directory(self, piece):
        self.entries = []
        if not piece.startswith('IFCM'):
            raise LitError('Header piece #1 is not main directory.')
        chunk_size, num_chunks = int32(piece[8:12]), int32(piece[24:28])
        
        if (32 + chunk_size * num_chunks) != len(piece):
            raise LitError('IFCM HEADER has incorrect length')
        
        for chunk in range(num_chunks):
            p = 32 + chunk * chunk_size
            if piece[p:p+4] != 'AOLL':
                continue
            remaining = chunk_size - int32(piece[p+4:p+8]) - 48
            if remaining < 0:
                raise LitError('AOLL remaining count is negative')
            
            entries = u16(piece[p+chunk_size-2:])
            if entries <= 0:            
                # Hopefully everything will work even without a correct entries
                # count
                entries = (2 ** 16) - 1
            
            piece = piece[p+48:]
            i = 0
            while i < entries:
                if remaining <= 0: break
                namelen, piece, remaining = encint(piece, remaining)
                if namelen != (namelen & 0x7fffffff):
                    raise LitError('Directory entry had 64bit name length.')
                if namelen > remaining - 3:
                    raise LitError('Read past end of directory chunk')
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
                raise LitError('Lit file does not have a valid NameList')
            
            if not hasattr(self, 'manifest'):
                raise LitError('Lit file does not have a valid manifest')

    @preserve
    def read_section_names(self, entry):
        self._stream.seek(self.content_offset + entry.offset)
        raw = self._stream.read(entry.size)
        if len(raw) < 4:
            raise LitError('Invalid Namelist section')
        pos = 4
        self.num_sections = u16(raw[2:pos])
        
        self.sections = {}
        for section in range(self.num_sections):
            size = u16(raw[pos:pos+2])
            pos += 2
            size = size*2 + 2
            if pos + size > len(raw):
                raise LitError('Invalid Namelist section')
            self.sections[section] = raw[pos:pos+size].decode('utf-16-le')
            pos += size                

    @preserve
    def read_manifest(self, entry):
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
                raise LitError('Truncated manifest.')
            for state in ['spine', 'not spine', 'css', 'images']:
                num_files = int32(raw[pos:pos+4])
                pos += 4
                if num_files == 0: continue
                
                i = 0
                while i < num_files:
                    if pos+5 >= len(raw):
                        raise LitError('Truncated manifest.')
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
                    pos += slen + 1
                    
                    self.manifest.append(
                        ManifestItem(original, internal, mime_type,
                                     offset, root, state))
                    i += 1

    @preserve
    def read_meta(self, entry):
        self._stream.seek(self.content_offset + entry.offset)
        raw = self._stream.read(entry.size)
        xml = OPF_DECL + unicode(UnBinary(raw, self.manifest))
        self.meta = xml

    @preserve
    def read_image(self, internal_name):
        cover_entry = None
        for entry in self.entries:
            if internal_name in entry.name:
                cover_entry = entry
                break
        self._stream.seek(self.content_offset + cover_entry.offset)
        return self._stream.read(cover_entry.size)

def get_metadata(stream):
    try:
        litfile = LitFile(stream)
        src = litfile.meta.encode('utf-8')
        mi = OPFReader(cStringIO.StringIO(src), dir=os.getcwd())
        cover_url, cover_item = mi.cover, None
        if cover_url:
            cover_url = relpath(cover_url, os.getcwd())
            for item in litfile.manifest:
                if item.path == cover_url:
                    cover_item = item.internal
        if cover_item is not None:
            ext = cover_url.rpartition('.')[-1]
            if not ext:
                ext = 'jpg'
            else:
                ext = ext.lower()
            cd = litfile.read_image(cover_item)
            mi.cover_data = (ext, cd) if cd else (None, None)            
    except:
        title = stream.name if hasattr(stream, 'name') and stream.name else 'Unknown'
        mi = MetaInformation(title, ['Unknown'])
    return mi

def main(args=sys.argv):
    if len(args) != 2:
        print >>sys.stderr, _('Usage: %s file.lit')%(args[0],)
        return 1
    mi = get_metadata(open(args[1], 'rb'))
    print unicode(mi)
    if mi.cover_data[1]:
        cover = os.path.abspath(os.path.splitext(os.path.basename(args[1]))[0] + '.' + mi.cover_data[0]) 
        open(cover, 'wb').write(mi.cover_data[1])
        print _('Cover saved to'), cover
    return 0

if __name__ == '__main__':
    sys.exit(main())
