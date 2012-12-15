#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import codecs, zlib, hashlib
from io import BytesIO
from future_builtins import map

from calibre.constants import (__appname__, __version__)

PDFVER = b'%PDF-1.6'
EOL = b'\n'

# Sizes {{{
inch = 72.0
cm = inch / 2.54
mm = cm * 0.1
pica = 12.0

_W, _H = (21*cm, 29.7*cm)

A6 = (_W*.5, _H*.5)
A5 = (_H*.5, _W)
A4 = (_W, _H)
A3 = (_H, _W*2)
A2 = (_W*2, _H*2)
A1 = (_H*2, _W*4)
A0 = (_W*4, _H*4)

LETTER = (8.5*inch, 11*inch)
LEGAL = (8.5*inch, 14*inch)
ELEVENSEVENTEEN = (11*inch, 17*inch)

_BW, _BH = (25*cm, 35.3*cm)
B6 = (_BW*.5, _BH*.5)
B5 = (_BH*.5, _BW)
B4 = (_BW, _BH)
B3 = (_BH*2, _BW)
B2 = (_BW*2, _BH*2)
B1 = (_BH*4, _BW*2)
B0 = (_BW*4, _BH*4)
# }}}

def serialize(o, stream):
    if hasattr(o, 'pdf_serialize'):
        o.pdf_serialize(stream)
    elif isinstance(o, bool):
        stream.write(b'true' if o else b'false')
    elif isinstance(o, (int, float)):
        stream.write(type(u'')(o).encode('ascii'))
    elif o is None:
        stream.write(b'null')
    else:
        raise ValueError('Unknown object: %r'%o)

class Name(unicode):

    def pdf_serialize(self, stream):
        raw = self.encode('ascii')
        if len(raw) > 126:
            raise ValueError('Name too long: %r'%self)
        buf = [x if 33 < ord(x) < 126 and x != b'#' else b'#'+hex(ord(x)) for x
               in raw]
        stream.write(b'/'+b''.join(buf))

class String(unicode):

    def pdf_serialize(self, stream):
        s = self.replace('\\', '\\\\').replace('(', r'\(').replace(')', r'\)')
        try:
            raw = s.encode('latin1')
            if raw.startswith(codecs.BOM_UTF16_BE):
                raise UnicodeEncodeError('')
        except UnicodeEncodeError:
            raw = codecs.BOM_UTF16_BE + s.encode('utf-16-be')
        stream.write(b'('+raw+b')')

class Dictionary(dict):

    def pdf_serialize(self, stream):
        stream.write(b'<<' + EOL)
        for k, v in self.iteritems():
            serialize(Name(k), stream)
            stream.write(b' ')
            serialize(v, stream)
            stream.write(EOL)
        stream.write(b'>>' + EOL)

class InlineDictionary(Dictionary):

    def pdf_serialize(self, stream):
        stream.write(b'<< ')
        for k, v in self.iteritems():
            serialize(Name(k), stream)
            stream.write(b' ')
            serialize(v, stream)
            stream.write(b' ')
        stream.write(b'>>')

class Array(list):

    def pdf_serialize(self, stream):
        stream.write(b'[')
        for i, o in enumerate(self):
            if i != 0:
                stream.write(b' ')
            serialize(o, stream)
        stream.write(b']')

class Stream(BytesIO):

    def __init__(self, compress=False):
        BytesIO.__init__(self)
        self.compress = compress

    def pdf_serialize(self, stream):
        raw = self.getvalue()
        dl = len(raw)
        filters = Array()
        if self.compress:
            filters.append(Name('FlateDecode'))
            raw = zlib.compress(raw)

        d = InlineDictionary({'Length':len(raw), 'DL':dl})
        if filters:
            d['Filters'] = filters
        serialize(d, stream)
        stream.write(EOL+b'stream'+EOL)
        stream.write(raw)
        stream.write(EOL+b'endstream'+EOL)

    def write_line(self, raw=b''):
        self.write(raw if isinstance(raw, bytes) else raw.encode('ascii'))
        self.write(EOL)

    def write(self, raw):
        super(Stream, self).write(raw if isinstance(raw, bytes) else
                                  raw.encode('ascii'))

class Reference(object):

    def __init__(self, num, obj):
        self.num, self.obj = num, obj

    def pdf_serialize(self, stream):
        raw = '%d 0 R'%self.num
        stream.write(raw.encode('ascii'))

class IndirectObjects(object):

    def __init__(self):
        self._list = []
        self._map = {}
        self._offsets = []

    def __len__(self):
        return len(self._list)

    def add(self, o):
        self._list.append(o)
        ref = Reference(len(self._list), o)
        self._map[id(o)] = ref
        self._offsets.append(None)
        return ref

    def commit(self, ref, stream):
        self.write_obj(stream, ref.num, ref.obj)

    def write_obj(self, stream, num, obj):
        stream.write(EOL)
        self._offsets[num-1] = stream.tell()
        stream.write('%d 0 obj'%num)
        stream.write(EOL)
        serialize(obj, stream)
        if stream.last_char != EOL:
            stream.write(EOL)
        stream.write('endobj')
        stream.write(EOL)

    def __getitem__(self, o):
        try:
            return self._map[id(self._list[o] if isinstance(o, int) else o)]
        except (KeyError, IndexError):
            raise KeyError('The object %r was not found'%o)

    def pdf_serialize(self, stream):
        for i, obj in enumerate(self._list):
            offset = self._offsets[i]
            if offset is None:
                self.write_obj(stream, i+1, obj)

    def write_xref(self, stream):
        self.xref_offset = stream.tell()
        stream.write(b'xref'+EOL)
        stream.write('0 %d'%(1+len(self._offsets)))
        stream.write(EOL)
        stream.write('%010d 65535 f '%0)
        stream.write(EOL)

        for offset in self._offsets:
            line = '%010d 00000 n '%offset
            stream.write(line.encode('ascii') + EOL)
        return self.xref_offset

class Page(Stream):

    def __init__(self, parentref, *args, **kwargs):
        super(Page, self).__init__(*args, **kwargs)
        self.page_dict = Dictionary({
            'Type': Name('Page'),
            'Parent': parentref,
        })

    def end(self, objects, stream):
        contents = objects.add(self)
        objects.commit(contents, stream)
        self.page_dict['Contents'] = contents
        ret = objects.add(self.page_dict)
        objects.commit(ret, stream)
        return ret

class Path(object):

    def __init__(self):
        self.ops = []

    def move_to(self, x, y):
        self.ops.append((x, y, 'm'))

    def line_to(self, x, y):
        self.ops.append((x, y, 'l'))

    def curve_to(self, x1, y1, x2, y2, x, y):
        self.ops.append((x1, y1, x2, y2, x, y, 'c'))

class Catalog(Dictionary):

    def __init__(self, pagetree):
        super(Catalog, self).__init__({'Type':Name('Catalog'),
            'Pages': pagetree})

class PageTree(Dictionary):

    def __init__(self, page_size):
        super(PageTree, self).__init__({'Type':Name('Pages'),
            'MediaBox':Array([0, 0, page_size[0], page_size[1]]),
            'Kids':Array(), 'Count':0,
        })

    def add_page(self, pageref):
        self['Kids'].append(pageref)
        self['Count'] += 1

class HashingStream(object):

    def __init__(self, f):
        self.f = f
        self.tell = f.tell
        self.hashobj = hashlib.sha256()
        self.last_char = b''

    def write(self, raw):
        raw = raw if isinstance(raw, bytes) else raw.encode('ascii')
        self.f.write(raw)
        self.hashobj.update(raw)
        if raw:
            self.last_char = raw[-1]

class PDFStream(object):

    PATH_OPS = {
        # stroke fill   fill-rule
        ( False, False, 'winding')  : 'n',
        ( False, False, 'evenodd')  : 'n',
        ( False, True,  'winding')  : 'f',
        ( False, True,  'evenodd')  : 'f*',
        ( True,  False, 'winding')  : 'S',
        ( True,  False, 'evenodd')  : 'S',
        ( True,  True,  'winding')  : 'B',
        ( True,  True,  'evenodd')  : 'B*',
    }

    def __init__(self, stream, page_size, compress=False):
        self.stream = HashingStream(stream)
        self.compress = compress
        self.write_line(PDFVER)
        self.write_line(b'%íì¦"')
        creator = ('%s %s [http://calibre-ebook.com]'%(__appname__,
                                    __version__))
        self.write_line('%% Created by %s'%creator)
        self.objects = IndirectObjects()
        self.objects.add(PageTree(page_size))
        self.objects.add(Catalog(self.page_tree))
        self.current_page = Page(self.page_tree, compress=self.compress)
        self.info = Dictionary({'Creator':String(creator),
                                'Producer':String(creator)})

    @property
    def page_tree(self):
        return self.objects[0]

    @property
    def catalog(self):
        return self.objects[1]

    def write_line(self, byts=b''):
        byts = byts if isinstance(byts, bytes) else byts.encode('ascii')
        self.stream.write(byts + EOL)

    def transform(self, *args):
        if len(args) == 1:
            m = args[0]
            vals = [m.m11(), m.m12(), m.m21(), m.m22(), m.dx(), m.dy()]
        else:
            vals = args
        cm = ' '.join(map(type(u''), vals))
        self.current_page.write_line(cm + ' cm')

    def set_rgb_colorspace(self):
        self.current_page.write_line('/DeviceRGB CS /DeviceRGB cs')

    def save_stack(self):
        self.current_page.write_line('q')

    def restore_stack(self):
        self.current_page.write_line('Q')

    def reset_stack(self):
        self.current_page.write_line('Q q')

    def draw_rect(self, x, y, width, height, stroke=True, fill=False):
        self.current_page.write('%g %g %g %g re '%(x, y, width, height))
        self.current_page.write_line(self.PATH_OPS[(stroke, fill, 'winding')])

    def write_path(self, path):
        for i, op in enumerate(path.ops):
            if i != 0:
                self.current_page.write_line()
            for x in op:
                self.current_page.write(type(u'')(x) + ' ')

    def draw_path(self, path, stroke=True, fill=False, fill_rule='winding'):
        if not path.ops: return
        self.write_path(path)
        self.current_page.write_line(self.PATH_OPS[(stroke, fill, fill_rule)])

    def add_clip(self, path, fill_rule='winding'):
        if not path.ops: return
        op = 'W' if fill_rule == 'winding' else 'W*'
        self.current_page.write(op + ' ' + 'n')

    def set_dash(self, array, phase=0):
        array = Array(array)
        serialize(array, self.current_page)
        self.current_page.write(b' ')
        serialize(phase, self.current_page)
        self.current_page.write_line(' d')

    def set_line_width(self, width):
        serialize(width, self.current_page)
        self.current_page.write_line(' w')

    def set_line_cap(self, style):
        serialize({'flat':0, 'round':1, 'square':2}.get(style),
                  self.current_page)
        self.current_page.write_line(' J')

    def set_line_join(self, style):
        serialize({'miter':0, 'round':1, 'bevel':2}[style], self.current_page)
        self.current_page.write_line(' j')

    def end_page(self):
        pageref = self.current_page.end(self.objects, self.stream)
        self.page_tree.obj.add_page(pageref)
        self.current_page = Page(self.page_tree, compress=self.compress)

    def end(self):
        if self.current_page.getvalue():
            self.end_page()
        inforef = self.objects.add(self.info)
        self.objects.pdf_serialize(self.stream)
        self.write_line()
        startxref = self.objects.write_xref(self.stream)
        file_id = String(self.stream.hashobj.hexdigest().decode('ascii'))
        self.write_line('trailer')
        trailer = Dictionary({'Root':self.catalog, 'Size':len(self.objects)+1,
                              'ID':Array([file_id, file_id]), 'Info':inforef})
        serialize(trailer, self.stream)
        self.write_line('startxref')
        self.write_line('%d'%startxref)
        self.stream.write('%%EOF')

