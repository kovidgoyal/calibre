'''
Support for reading LIT files.
'''
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net> ' \
    'and Marshall T. Vandegrift <llasram@gmail.com>'

import sys, struct, cStringIO, os
import functools
import codecs
from itertools import repeat

from calibre import relpath
from calibre.ebooks.metadata import MetaInformation
from calibre.ebooks.metadata.opf import OPFReader
from calibre.ebooks.lit import LitError
from calibre.ebooks.lit.maps import OPF_MAP, HTML_MAP
import calibre.ebooks.lit.mssha1 as mssha1
import calibre.ebooks.lit.msdes as msdes
import calibre.utils.lzx as lzx

OPF_DECL = """<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE package 
  PUBLIC "+//ISBN 0-9673008-1-9//DTD OEB 1.0.1 Package//EN"
  "http://openebook.org/dtds/oeb-1.0.1/oebpkg101.dtd">
"""
HTML_DECL = """<?xml version="1.0" encoding="UTF-8" ?>
<!DOCTYPE html PUBLIC 
 "+//ISBN 0-9673008-1-9//DTD OEB 1.0.1 Document//EN"
 "http://openebook.org/dtds/oeb-1.0.1/oebdoc101.dtd">
"""

DESENCRYPT_GUID = "{67F6E4A2-60BF-11D3-8540-00C04F58C3CF}"
LZXCOMPRESS_GUID = "{0A9007C6-4076-11D3-8789-0000F8105754}"

CONTROL_TAG = 4
CONTROL_WINDOW_SIZE = 12
RESET_NENTRIES = 4
RESET_HDRLEN = 12
RESET_UCLENGTH = 16
RESET_INTERVAL = 32

FLAG_OPENING = (1 << 0)
FLAG_CLOSING = (1 << 1)
FLAG_BLOCK   = (1 << 2)
FLAG_HEAD    = (1 << 3)
FLAG_ATOM    = (1 << 4)
XML_ENTITIES = ['&amp;', '&apos;', '&lt;', '&gt;', '&quot;']

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

def msguid(bytes):
    values = struct.unpack("<LHHBBBBBBBB", bytes[:16])
    return "{%08lX-%04X-%04X-%02X%02X-%02X%02X%02X%02X%02X%02X}" % values

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
            self.raw = '&amp;'.join(
                (self.raw[:pos+offset], self.raw[pos+offset+1:]))
            offset += 4
    
    def item_path(self, internal_id):
        try:
            return self.manifest[internal_id].path
        except KeyError:
            return internal_id
    
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
                        self.buf.write(u''.join(
                                ('</', tag_name, '>')).encode('utf-8'))
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
                        self.buf.write(unicode(c).encode('utf-8'))
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
                    self.buf.write(unicode(tag_name).encode('utf-8'))
                    state = 'get attr'
            
            elif state == 'get attr length':
                count = oc - 1
                if count <= 0 or count > (len(self.bin) - index):
                    raise LitError('Invalid character count %d' % count)
                self.buf.write(' ')
                state = 'get custom attr'
            
            elif state == 'get custom attr':
                self.buf.write(unicode(c).encode('utf-8'))
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
    
class DirectoryEntry(object):
    def __init__(self, name, section, offset, size):
        self.name = name
        self.section = section
        self.offset = offset
        self.size = size
        
    def __repr__(self):
        return "DirectoryEntry(name=%s, section=%d, offset=%d, size=%d)" \
            % (repr(self.name), self.section, self.offset, self.size)
        
    def __str__(self):
        return repr(self)

class ManifestItem(object):
    def __init__(self, original, internal, mime_type, offset, root, state):
        self.original = original
        self.internal = internal
        self.mime_type = mime_type
        self.offset = offset
        self.root = root
        self.state = state
        # Some paths in Fictionwise "multiformat" LIT files contain '..' (!?)
        path = os.path.normpath(original).replace('\\', '/')
        while path.startswith('../'): path = path[3:]
        self.path = path
        
    def __eq__(self, other):
        if hasattr(other, 'internal'):
            return self.internal == other.internal
        return self.internal == other
    
    def __repr__(self):
        return "ManifestItem(internal=%s, path=%s)" \
            % (repr(self.internal), repr(self.path))

def preserve(function):
    def wrapper(self, *args, **kwargs):
        opos = self._stream.tell()
        try:
            return function(self, *args, **kwargs)
        finally:
            self._stream.seek(opos)
    functools.update_wrapper(wrapper, function)
    return wrapper
    
class LitReader(object):
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
    
    def __init__(self, filename_or_stream):
        if hasattr(filename_or_stream, 'read'):
            self._stream = filename_or_stream
        else:
            self._stream = open(filename_or_stream, 'rb')
        if self.magic != 'ITOLITLS':
            raise LitError('Not a valid LIT file')
        if self.version != 1:
            raise LitError('Unknown LIT version %d'%(self.version,))
        self.entries = {}
        self._read_secondary_header()
        self._read_header_pieces()
        self._read_section_names()
        self._read_manifest()
        self._read_meta()
        self._read_drm()

    @preserve
    def __len__(self):
        self._stream.seek(0, 2)
        return self._stream.tell()

    @preserve
    def _read_raw(self, offset, size):
        self._stream.seek(offset)
        return self._stream.read(size)

    def _read_content(self, offset, size):
        return self._read_raw(self.content_offset + offset, size)
    
    def _read_secondary_header(self):
        offset = self.hdr_len + (self.num_pieces * self.PIECE_SIZE)
        bytes = self._read_raw(offset, self.sec_hdr_len)
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
    
    def _read_header_pieces(self):
        src = self.header[self.hdr_len:]
        for i in range(self.num_pieces):
            piece = src[i * self.PIECE_SIZE:(i + 1) * self.PIECE_SIZE]
            if u32(piece[4:]) != 0 or u32(piece[12:]) != 0:
                raise LitError('Piece %s has 64bit value' % repr(piece))
            offset, size = u32(piece), int32(piece[8:])
            piece = self._read_raw(offset, size)
            if i == 0:
                continue # Dont need this piece
            elif i == 1:
                if u32(piece[8:])  != self.entry_chunklen or \
                   u32(piece[12:]) != self.entry_unknown:
                    raise LitError('Secondary header does not match piece')
                self._read_directory(piece)
            elif i == 2:
                if u32(piece[8:])  != self.count_chunklen or \
                   u32(piece[12:]) != self.count_unknown:
                    raise LitError('Secondary header does not match piece')
                continue # No data needed from this piece
            elif i == 3:
                self.piece3_guid = piece
            elif i == 4:
                self.piece4_guid = piece
                
    def _read_directory(self, piece):
        if not piece.startswith('IFCM'):
            raise LitError('Header piece #1 is not main directory.')
        chunk_size, num_chunks = int32(piece[8:12]), int32(piece[24:28])
        if (32 + (num_chunks * chunk_size)) != len(piece):
            raise LitError('IFCM HEADER has incorrect length')
        for i in xrange(num_chunks):
            offset = 32 + (i * chunk_size)
            chunk = piece[offset:offset + chunk_size]
            tag, chunk = chunk[:4], chunk[4:]
            if tag != 'AOLL': continue
            remaining, chunk = int32(chunk[:4]), chunk[4:]
            if remaining >= chunk_size:
                raise LitError('AOLL remaining count is negative')
            remaining = chunk_size - (remaining + 48)
            entries = u16(chunk[-2:])
            if entries == 0:
                # Hopefully will work even without a correct entries count
                entries = (2 ** 16) - 1
            chunk = chunk[40:]
            for j in xrange(entries):
                if remaining <= 0: break
                namelen, chunk, remaining = encint(chunk, remaining)
                if namelen != (namelen & 0x7fffffff):
                    raise LitError('Directory entry had 64bit name length.')
                if namelen > remaining - 3:
                    raise LitError('Read past end of directory chunk')
                name, chunk = chunk[:namelen], chunk[namelen:]
                section, chunk, remaining = encint(chunk, remaining)
                offset, chunk, remaining = encint(chunk, remaining)
                size, chunk, remaining = encint(chunk, remaining)
                entry = DirectoryEntry(name, section, offset, size)
                self.entries[name] = entry

    def _read_section_names(self):
        if '::DataSpace/NameList' not in self.entries:
            raise LitError('Lit file does not have a valid NameList')
        raw = self.get_file('::DataSpace/NameList')
        if len(raw) < 4:
            raise LitError('Invalid Namelist section')
        pos = 4
        self.num_sections = u16(raw[2:pos])
        self.section_names = [""]*self.num_sections
        self.section_data = [None]*self.num_sections
        for section in range(self.num_sections):
            size = u16(raw[pos:pos+2])
            pos += 2
            size = size*2 + 2
            if pos + size > len(raw):
                raise LitError('Invalid Namelist section')
            self.section_names[section] = \
                raw[pos:pos+size].decode('utf-16-le').rstrip('\000')
            pos += size

    def _read_manifest(self):
        if '/manifest' not in self.entries:
            raise LitError('Lit file does not have a valid manifest')
        raw = self.get_file('/manifest')
        self.manifest = {}
        while raw:
            slen, raw = ord(raw[0]), raw[1:]
            if slen == 0: break
            root, raw = raw[:slen].decode('utf8'), raw[slen:]
            if not raw:
                raise LitError('Truncated manifest')
            for state in ['spine', 'not spine', 'css', 'images']:
                num_files, raw = int32(raw), raw[4:]
                if num_files == 0: continue
                for i in xrange(num_files):
                    if len(raw) < 5:
                        raise LitError('Truncated manifest')
                    offset, raw = u32(raw), raw[4:]
                    slen, raw = ord(raw[0]), raw[1:]
                    internal, raw = raw[:slen].decode('utf8'), raw[slen:]
                    slen, raw = ord(raw[0]), raw[1:]
                    original, raw = raw[:slen].decode('utf8'), raw[slen:]
                    slen, raw = ord(raw[0]), raw[1:]
                    mime_type, raw = raw[:slen].decode('utf8'), raw[slen+1:]
                    self.manifest[internal] = ManifestItem(
                        original, internal, mime_type, offset, root, state)
        mlist = self.manifest.values()
        shared = mlist[0].path
        for item in mlist[1:]:
            path = item.path
            while shared and not path.startswith(shared):
                try: shared = shared[:shared.rindex("/", 0, -2) + 1]
                except ValueError: shared = None
            if not shared:
                break
        if shared:
            slen = len(shared)
            for item in mlist:
                item.path = item.path[slen:]

    def _read_meta(self):
        raw = self.get_file('/meta')
        try:
            xml = OPF_DECL + unicode(UnBinary(raw, self.manifest, OPF_MAP))
        except LitError:
            if 'PENGUIN group' not in raw: raise
            print "WARNING: attempting PENGUIN malformed OPF fix"
            raw = raw.replace(
                'PENGUIN group', '\x00\x01\x18\x00PENGUIN group', 1)
            xml = OPF_DECL + unicode(UnBinary(raw, self.manifest, OPF_MAP))
        self.meta = xml

    def _read_drm(self):
        self.drmlevel = 0
        if '/DRMStorage/Licenses/EUL' in self.entries:
            self.drmlevel = 5
        elif '/DRMStorage/DRMBookplate' in self.entries:
            self.drmlevel = 3
        elif '/DRMStorage/DRMSealed' in self.entries:
            self.drmlevel = 1
        else:
            return
        des = msdes.new(self._calculate_deskey())
        bookkey = des.decrypt(self.get_file('/DRMStorage/DRMSealed'))
        if bookkey[0] != '\000':
            raise LitError('Unable to decrypt title key!')
        self.bookkey = bookkey[1:9]

    def _calculate_deskey(self):
        hashfiles = ['/meta', '/DRMStorage/DRMSource']
        if self.drmlevel == 3:
            hashfiles.append('/DRMStorage/DRMBookplate')
        prepad = 2
        hash = mssha1.new()
        for name in hashfiles:
            data = self.get_file(name)
            if prepad > 0:
                data = ("\000" * prepad) + data
                prepad = 0
            postpad = 64 - (len(data) % 64)
            if postpad < 64:
                data = data + ("\000" * postpad)
            hash.update(data)
        digest = hash.digest()
        key = [0] * 8
        for i in xrange(0, len(digest)):
            key[i % 8] ^= ord(digest[i])
        return ''.join(chr(x) for x in key)

    def get_markup_file(self, name):
        raw = self.get_file(name)
        decl, map = (OPF_DECL, OPF_MAP) \
            if name == '/meta' else (HTML_DECL, HTML_MAP)
        xml = decl + unicode(UnBinary(raw, self.manifest, map))
        return xml
        
    def get_file(self, name):
        entry = self.entries[name]
        if entry.section == 0:
            return self._read_content(entry.offset, entry.size)
        section = self.get_section(entry.section)
        return section[entry.offset:entry.offset+entry.size]

    def get_section(self, section):
        data = self.section_data[section]
        if not data:
            data = self._get_section(section)
            self.section_data[section] = data
        return data

    def _get_section(self, section):
        name = self.section_names[section]
        path = '::DataSpace/Storage/' + name
        transform = self.get_file(path + '/Transform/List')
        content = self.get_file(path + '/Content')
        control = self.get_file(path + '/ControlData')
        while len(transform) >= 16:
            csize = (int32(control) + 1) * 4
            if csize > len(control) or csize <= 0:
                raise LitError("ControlData is too short")
            guid = msguid(transform)
            if guid == DESENCRYPT_GUID:
                content = self._decrypt(content)
                control = control[csize:]
            elif guid == LZXCOMPRESS_GUID:
                reset_table = self.get_file(
                    '/'.join(('::DataSpace/Storage', name, 'Transform',
                              LZXCOMPRESS_GUID, 'InstanceData/ResetTable')))
                content = self._decompress(content, control, reset_table)
                control = control[csize:]
            else:
                raise LitError("Unrecognized transform: %s." % repr(guid))
            transform = transform[16:]
        return content

    def _decrypt(self, content):
        if self.drmlevel == 5:
            raise LitError('Cannot extract content from a DRM protected ebook')
        return msdes.new(self.bookkey).decrypt(content)

    def _decompress(self, content, control, reset_table):
        if len(control) < 32 or control[CONTROL_TAG:CONTROL_TAG+4] != "LZXC":
            raise LitError("Invalid ControlData tag value")
        if len(reset_table) < (RESET_INTERVAL + 8):
            raise LitError("Reset table is too short")
        if u32(reset_table[RESET_UCLENGTH + 4:]) != 0:
            raise LitError("Reset table has 64bit value for UCLENGTH")
        
        result = []
        
        window_size = 14
        u = u32(control[CONTROL_WINDOW_SIZE:])
        while u > 0:
            u >>= 1
            window_size += 1
        if window_size < 15 or window_size > 21:
            raise LitError("Invalid window in ControlData")
        lzx.init(window_size)

        ofs_entry = int32(reset_table[RESET_HDRLEN:]) + 8
        uclength = int32(reset_table[RESET_UCLENGTH:])
        accum = int32(reset_table[RESET_INTERVAL:])
        bytes_remaining = uclength
        window_bytes = (1 << window_size)
        base = 0

        while ofs_entry < len(reset_table):
            if accum >= window_bytes:
                accum = 0
                size = int32(reset_table[ofs_entry:])
                u = int32(reset_table[ofs_entry + 4:])
                if u != 0:
                    raise LitError("Reset table entry greater than 32 bits")
                if size >= len(content):
                    raise("Reset table entry out of bounds")
                if bytes_remaining >= window_bytes:
                    lzx.reset()
                    result.append(
                        lzx.decompress(content[base:size], window_bytes))
                    bytes_remaining -= window_bytes
                    base = size
            accum += int32(reset_table[RESET_INTERVAL:])
            ofs_entry += 8
        if bytes_remaining < window_bytes and bytes_remaining > 0:
            lzx.reset()
            result.append(lzx.decompress(content[base:], bytes_remaining))
            bytes_remaining = 0
        if bytes_remaining > 0:
            raise LitError("Failed to completely decompress section")
        return ''.join(result)

    def extract_content(self, output_dir=os.getcwdu()):
        output_dir = os.path.abspath(output_dir)
        try:
            opf_path = os.path.splitext(
                os.path.basename(self._stream.name))[0] + '.opf'
        except AttributeError:
            opf_path = 'content.opf'
        opf_path = os.path.join(output_dir, opf_path)
        self._ensure_dir(opf_path)
        with open(opf_path, 'wb') as f:
            f.write(self.meta.encode('utf-8'))
        for entry in self.manifest.values():
            path = os.path.join(output_dir, entry.path)
            self._ensure_dir(path)
            with open(path, 'wb') as f:
                if 'spine' in entry.state:
                    name = '/'.join(('/data', entry.internal, 'content'))
                    f.write(self.get_markup_file(name).encode('utf-8'))
                else:
                    name = '/'.join(('/data', entry.internal))
                    f.write(self.get_file(name))

    def _ensure_dir(self, path):
        dir = os.path.dirname(path)
        if not os.path.isdir(dir):
            os.makedirs(dir)

def option_parser():
    from calibre import OptionParser
    parser = OptionParser(usage=_('%prog [options] LITFILE'))
    parser.add_option(
        '-o', '--output-dir', default='.', 
        help=_('Output directory. Defaults to current directory.'))
    parser.add_option(
        '--verbose', default=False, action='store_true',
        help='Useful for debugging.')
    return parser

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    if len(args) != 2:
        parser.print_help()
        return 1
    lr = LitReader(args[1])
    lr.extract_content(opts.output_dir)
    print _('OEB ebook created in'), opts.output_dir
    return 0

if __name__ == '__main__':
    sys.exit(main())
