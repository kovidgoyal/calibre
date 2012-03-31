#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, imghdr

from calibre.ebooks.mobi.debug.headers import TextRecord
from calibre.ebooks.mobi.utils import read_font_record

class MOBIFile(object):

    def __init__(self, mf):
        self.mf = mf
        h, h8 = mf.mobi_header, mf.mobi8_header
        first_text_record = 1
        offset = 0
        res_end = len(mf.records)
        if mf.kf8_type == 'joint':
            offset = h.exth.kf8_header_index
            res_end = offset - 1

        self.resource_records = mf.records[h.first_non_book_record:res_end]
        self.text_records = [TextRecord(i, r, h8.extra_data_flags,
            mf.decompress8) for i, r in
            enumerate(mf.records[first_text_record+offset:
                first_text_record+offset+h8.number_of_text_records])]

        self.raw_text = b''.join(r.raw for r in self.text_records)
        self.extract_resources()

    def print_header(self, f=sys.stdout):
        print (str(self.mf.palmdb).encode('utf-8'), file=f)
        print (file=f)
        print ('Record headers:', file=f)
        for i, r in enumerate(self.mf.records):
            print ('%6d. %s'%(i, r.header), file=f)

        print (file=f)
        print (str(self.mf.mobi8_header).encode('utf-8'), file=f)

    def extract_resources(self):
        self.resource_map = []
        known_types = {b'FLIS', b'FCIS', b'SRCS',
                    b'\xe9\x8e\r\n', b'RESC', b'BOUN', b'FDST', b'DATP',
                    b'AUDI', b'VIDE'}

        for i, rec in enumerate(self.resource_records):
            sig = rec.raw[:4]
            payload = rec.raw
            ext = 'dat'
            prefix = 'binary'
            suffix = ''
            if sig in {b'HUFF', b'CDIC', b'INDX'}: continue
            # TODO: Ignore CNCX records as well
            if sig == b'FONT':
                font = read_font_record(rec.raw)
                if font['err']:
                    raise ValueError('Failed to read font record: %s Headers: %s'%(
                        font['err'], font['headers']))
                payload = (font['font_data'] if font['font_data'] else
                        font['raw_data'])
                prefix, ext = 'fonts', font['ext']
            elif sig not in known_types:
                q = imghdr.what(None, rec.raw)
                if q:
                    prefix, ext = 'images', q

            if prefix == 'binary':
                if sig == b'\xe9\x8e\r\n':
                    suffix = '-EOF'
                elif sig in known_types:
                    suffix = '-' + sig.decode('ascii')

            self.resource_map.append(('%s/%06d%s.%s'%(prefix, i, suffix, ext),
                payload))


def inspect_mobi(mobi_file, ddir):
    f = MOBIFile(mobi_file)
    with open(os.path.join(ddir, 'header.txt'), 'wb') as out:
        f.print_header(f=out)

    alltext = os.path.join(ddir, 'raw_text.html')
    with open(alltext, 'wb') as of:
        of.write(f.raw_text)

    for x in ('text_records', 'images', 'fonts', 'binary'):
        os.mkdir(os.path.join(ddir, x))

    for rec in f.text_records:
        rec.dump(os.path.join(ddir, 'text_records'))

    for href, payload in f.resource_map:
        with open(os.path.join(ddir, href), 'wb') as f:
            f.write(payload)


