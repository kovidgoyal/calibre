#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from struct import pack
from io import BytesIO

from calibre.constants import iswindows, ismacos
from calibre.ebooks.mobi.utils import (utf8_text, to_base)
from calibre.utils.localization import lang_as_iso639_1
from calibre.ebooks.metadata import authors_to_sort_string
from polyglot.builtins import iteritems, unicode_type

EXTH_CODES = {
    'creator': 100,
    'publisher': 101,
    'description': 103,
    'identifier': 104,
    'subject': 105,
    'pubdate': 106,
    'review': 107,
    'contributor': 108,
    'rights': 109,
    'type': 111,
    'source': 112,
    'versionnumber': 114,
    'startreading': 116,
    'kf8_header_index': 121,
    'num_of_resources': 125,
    'kf8_thumbnail_uri': 129,
    'kf8_unknown_count': 131,
    'coveroffset': 201,
    'thumboffset': 202,
    'hasfakecover': 203,
    'lastupdatetime': 502,
    'title': 503,
    'language': 524,
    'primary_writing_mode': 525,
    'page_progression_direction': 527,
}

COLLAPSE_RE = re.compile(r'[ \t\r\n\v]+')


def build_exth(metadata, prefer_author_sort=False, is_periodical=False,
        share_not_sync=True, cover_offset=None, thumbnail_offset=None,
        start_offset=None, mobi_doctype=2, num_of_resources=None,
        kf8_unknown_count=0, be_kindlegen2=False, kf8_header_index=None,
        page_progression_direction=None, primary_writing_mode=None):
    exth = BytesIO()
    nrecs = 0

    for term in metadata:
        if term not in EXTH_CODES:
            continue
        code = EXTH_CODES[term]
        items = metadata[term]
        if term == 'creator':
            if prefer_author_sort:
                creators = [authors_to_sort_string([unicode_type(c)]) for c in
                            items]
            else:
                creators = [unicode_type(c) for c in items]
            items = creators
        elif term == 'rights':
            try:
                rights = utf8_text(unicode_type(metadata.rights[0]))
            except:
                rights = b'Unknown'
            exth.write(pack(b'>II', EXTH_CODES['rights'], len(rights) + 8))
            exth.write(rights)
            nrecs += 1
            continue

        for item in items:
            data = unicode_type(item)
            if term != 'description':
                data = COLLAPSE_RE.sub(' ', data)
            if term == 'identifier':
                if data.lower().startswith('urn:isbn:'):
                    data = data[9:]
                elif item.scheme.lower() == 'isbn':
                    pass
                else:
                    continue
            if term == 'language':
                d2 = lang_as_iso639_1(data)
                if d2:
                    data = d2
            data = utf8_text(data)
            exth.write(pack(b'>II', code, len(data) + 8))
            exth.write(data)
            nrecs += 1

    # Write UUID as ASIN
    uuid = None
    from calibre.ebooks.oeb.base import OPF
    for x in metadata['identifier']:
        if (x.get(OPF('scheme'), None).lower() == 'uuid' or
                unicode_type(x).startswith('urn:uuid:')):
            uuid = unicode_type(x).split(':')[-1]
            break
    if uuid is None:
        from uuid import uuid4
        uuid = unicode_type(uuid4())

    if isinstance(uuid, unicode_type):
        uuid = uuid.encode('utf-8')
    if not share_not_sync:
        exth.write(pack(b'>II', 113, len(uuid) + 8))
        exth.write(uuid)
        nrecs += 1

    # Write UUID as SOURCE
    c_uuid = b'calibre:%s' % uuid
    exth.write(pack(b'>II', 112, len(c_uuid) + 8))
    exth.write(c_uuid)
    nrecs += 1

    # Write cdetype
    if not is_periodical:
        if not share_not_sync:
            exth.write(pack(b'>II', 501, 12))
            exth.write(b'EBOK')
            nrecs += 1
    else:
        ids = {0x101:b'NWPR', 0x103:b'MAGZ'}.get(mobi_doctype, None)
        if ids:
            exth.write(pack(b'>II', 501, 12))
            exth.write(ids)
            nrecs += 1

    # Add a publication date entry
    if metadata['date']:
        datestr = unicode_type(metadata['date'][0])
    elif metadata['timestamp']:
        datestr = unicode_type(metadata['timestamp'][0])

    if datestr is None:
        raise ValueError("missing date or timestamp")

    datestr = datestr.encode('utf-8')
    exth.write(pack(b'>II', EXTH_CODES['pubdate'], len(datestr) + 8))
    exth.write(datestr)
    nrecs += 1
    if is_periodical:
        exth.write(pack(b'>II', EXTH_CODES['lastupdatetime'], len(datestr) + 8))
        exth.write(datestr)
        nrecs += 1

    if be_kindlegen2:
        mv = 200 if iswindows else 202 if ismacos else 201
        vals = {204:mv, 205:2, 206:9, 207:0}
    elif is_periodical:
        # Pretend to be amazon's super secret periodical generator
        vals = {204:201, 205:2, 206:0, 207:101}
    else:
        # Pretend to be kindlegen 1.2
        vals = {204:201, 205:1, 206:2, 207:33307}
    for code, val in iteritems(vals):
        exth.write(pack(b'>III', code, 12, val))
        nrecs += 1
    if be_kindlegen2:
        revnum = b'0730-890adc2'
        exth.write(pack(b'>II', 535, 8 + len(revnum)) + revnum)
        nrecs += 1

    if cover_offset is not None:
        exth.write(pack(b'>III', EXTH_CODES['coveroffset'], 12,
            cover_offset))
        exth.write(pack(b'>III', EXTH_CODES['hasfakecover'], 12, 0))
        nrecs += 2
    if thumbnail_offset is not None:
        exth.write(pack(b'>III', EXTH_CODES['thumboffset'], 12,
            thumbnail_offset))
        thumbnail_uri_str = ('kindle:embed:%s' %(to_base(thumbnail_offset, base=32, min_num_digits=4))).encode('utf-8')
        exth.write(pack(b'>II', EXTH_CODES['kf8_thumbnail_uri'], len(thumbnail_uri_str) + 8))
        exth.write(thumbnail_uri_str)
        nrecs += 2

    if start_offset is not None:
        try:
            len(start_offset)
        except TypeError:
            start_offset = [start_offset]
        for so in start_offset:
            if so is not None:
                exth.write(pack(b'>III', EXTH_CODES['startreading'], 12,
                    so))
                nrecs += 1

    if kf8_header_index is not None:
        exth.write(pack(b'>III', EXTH_CODES['kf8_header_index'], 12,
            kf8_header_index))
        nrecs += 1

    if num_of_resources is not None:
        exth.write(pack(b'>III', EXTH_CODES['num_of_resources'], 12,
            num_of_resources))
        nrecs += 1

    if kf8_unknown_count is not None:
        exth.write(pack(b'>III', EXTH_CODES['kf8_unknown_count'], 12,
            kf8_unknown_count))
        nrecs += 1

    if primary_writing_mode:
        pwm = primary_writing_mode.encode('utf-8')
        exth.write(pack(b'>II', EXTH_CODES['primary_writing_mode'], len(pwm) + 8))
        exth.write(pwm)
        nrecs += 1

    if page_progression_direction in {'rtl', 'ltr', 'default'}:
        ppd = page_progression_direction.encode('ascii')
        exth.write(pack(b'>II', EXTH_CODES['page_progression_direction'], len(ppd) + 8))
        exth.write(ppd)
        nrecs += 1

    exth = exth.getvalue()
    trail = len(exth) % 4
    pad = b'\0' * (4 - trail)  # Always pad w/ at least 1 byte
    exth = [b'EXTH', pack(b'>II', len(exth) + 12, nrecs), exth, pad]
    return b''.join(exth)
