#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os

from calibre.ebooks.mobi.debug.headers import TextRecord

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

    def print_header(self, f=sys.stdout):
        print (str(self.mf.palmdb).encode('utf-8'), file=f)
        print (file=f)
        print ('Record headers:', file=f)
        for i, r in enumerate(self.mf.records):
            print ('%6d. %s'%(i, r.header), file=f)

        print (file=f)
        print (str(self.mf.mobi8_header).encode('utf-8'), file=f)


def inspect_mobi(mobi_file, ddir):
    f = MOBIFile(mobi_file)
    with open(os.path.join(ddir, 'header.txt'), 'wb') as out:
        f.print_header(f=out)

    alltext = os.path.join(ddir, 'raw_text.html')
    with open(alltext, 'wb') as of:
        of.write(f.raw_text)

    for tdir, attr in [('text_records', 'text_records'), ('images',
        'image_records'), ('binary', 'binary_records'), ('font',
            'font_records')]:
        tdir = os.path.join(ddir, tdir)
        os.mkdir(tdir)
        for rec in getattr(f, attr, []):
            rec.dump(tdir)


