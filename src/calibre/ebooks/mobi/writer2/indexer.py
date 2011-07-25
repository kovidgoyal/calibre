#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from struct import pack
from cStringIO import StringIO
from collections import OrderedDict

from calibre.ebooks import normalize
from calibre.ebooks.mobi.utils import encint

def utf8_text(text):
    '''
    Convert a possibly null string to utf-8 bytes, guaranteeing to return a non
    empty, normalized bytestring.
    '''
    if text and text.strip():
        text = text.strip()
        if not isinstance(text, unicode):
            text = text.decode('utf-8', 'replace')
        text = normalize(text).encode('utf-8')
    else:
        text = _('Unknown').encode('utf-8')
    return text

def align_block(raw, multiple=4, pad=b'\0'):
    '''
    Return raw with enough pad bytes append to ensure its length is a multiple
    of 4.
    '''
    extra = len(raw) % multiple
    if extra == 0: return raw
    return raw + pad*(multiple - extra)


class CNCX(object): # {{{

    '''
    Create the CNCX records. These are records containing all the strings from
    the NCX. Each record is of the form: <vwi string size><utf-8 encoded
    string>
    '''

    MAX_STRING_LENGTH = 500

    def __init__(self, toc, opts):
        self.strings = OrderedDict()

        for item in toc:
            if item is self.toc: continue
            label = item.title
            klass = item.klass
            if opts.mobi_periodical:
                if item.description:
                    self.strings[item.description] = 0
                if item.author:
                    self.string[item.author] = 0
            self.strings[label] = self.strings[klass] = 0

        self.records = []

        offset = 0
        buf = StringIO()
        for key in tuple(self.strings.iterkeys()):
            utf8 = utf8_text(key[:self.MAX_STRING_LENGTH])
            l = len(utf8)
            sz_bytes = encint(l)
            raw = sz_bytes + utf8
            if 0xfbf8 - buf.tell() < 6 + len(raw):
                # Records in PDB files cannot be larger than 0x10000, so we
                # stop well before that.
                pad = 0xfbf8 - self._ctoc.tell()
                buf.write(b'\0' * pad)
                self.records.append(buf.getvalue())
                buf.truncate(0)
                offset = len(self.records) * 0x10000

            self.strings[key] = offset
            offset += len(raw)

        buf.write(b'\0') # CNCX must end with zero byte
        self.records.append(align_block(buf.getvalue()))

    def __getitem__(self, string):
        return self.strings[string]
# }}}

class Indexer(object):

    def __init__(self, serializer, number_of_text_records, opts, oeb):
        self.serializer = serializer
        self.number_of_text_records = number_of_text_records
        self.oeb = oeb
        self.log = oeb.log
        self.opts = opts

        self.cncx = CNCX(oeb.toc, opts)

        self.records = []

    def create_header(self):
        buf = StringIO()

        # Ident
        buf.write(b'INDX')

        # Header length
        buf.write(pack(b'>I', 192))

        # Index type: 0 - normal, 2 - inflection
        buf.write(pack(b'>I', 2))
