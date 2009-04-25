'''
Retrieve and modify in-place Mobipocket book metadata.
'''

from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal kovid@kovidgoyal.net and ' \
    'Marshall T. Vandegrift <llasram@gmail.com>'
__docformat__ = 'restructuredtext en'

import sys
import os
from struct import pack, unpack
from cStringIO import StringIO
from calibre.ebooks.mobi import MobiError
from calibre.ebooks.mobi.reader import get_metadata
from calibre.ebooks.mobi.writer import rescale_image, MAX_THUMB_DIMEN
from calibre.ebooks.mobi.langcodes import iana2mobi

class StreamSlicer(object):
    def __init__(self, stream, start=0, stop=None):
        self._stream = stream
        self.start = start
        if stop is None:
            stream.seek(0, 2)
            stop = stream.tell()
        self.stop = stop
        self._len = stop - start

    def __len__(self):
        return self._len

    def __getitem__(self, key):
        stream = self._stream
        base = self.start
        if isinstance(key, (int, long)):
            stream.seek(base + key)
            return stream.read(1)
        if isinstance(key, slice):
            start, stop, stride = key.indices(self._len)
            if stride < 0:
                start, stop = stop, start
            size = stop - start
            if size <= 0:
                return ""
            stream.seek(base + start)
            data = stream.read(size)
            if stride != 1:
                data = data[::stride]
            return data
        raise TypeError("stream indices must be integers")

    def __setitem__(self, key, value):
        stream = self._stream
        base = self.start
        if isinstance(key, (int, long)):
            if len(value) != 1:
                raise ValueError("key and value lengths must match")
            stream.seek(base + key)
            return stream.write(value)
        if isinstance(key, slice):
            start, stop, stride = key.indices(self._len)
            if stride < 0:
                start, stop = stop, start
            size = stop - start
            if stride != 1:
                value = value[::stride]
            if len(value) != size:
                raise ValueError("key and value lengths must match")
            stream.seek(base + start)
            return stream.write(value)
        raise TypeError("stream indices must be integers")


class MetadataUpdater(object):
    def __init__(self, stream):
        self.stream = stream
        data = self.data = StreamSlicer(stream)
        type = self.type = data[60:68]
        self.nrecs, = unpack('>H', data[76:78])
        record0 = self.record0 = self.record(0)
        self.encryption_type, = unpack('>H', record0[12:14])
        codepage, = unpack('>I', record0[28:32])
        self.codec = 'utf-8' if codepage == 65001 else 'cp1252'
        image_base, = unpack('>I', record0[108:112])
        flags, = unpack('>I', record0[128:132])
        have_exth = self.have_exth = (flags & 0x40) != 0
        self.cover_record = self.thumbnail_record = None
        if not have_exth:
            return
        exth_off = unpack('>I', record0[20:24])[0] + 16 + record0.start
        exth = self.exth = StreamSlicer(stream, exth_off, record0.stop)
        nitems, = unpack('>I', exth[8:12])
        pos = 12
        for i in xrange(nitems):
            id, size = unpack('>II', exth[pos:pos + 8])
            content = exth[pos + 8: pos + size]
            pos += size
            if id == 201:
                rindex, = self.cover_rindex, = unpack('>I', content)
                self.cover_record = self.record(rindex + image_base)
            elif id == 202:
                rindex, = self.thumbnail_rindex, = unpack('>I', content)
                self.thumbnail_record = self.record(rindex + image_base)

    def record(self, n):
        if n >= self.nrecs:
            raise ValueError('non-existent record %r' % n)
        offoff = 78 + (8 * n)
        start, = unpack('>I', self.data[offoff + 0:offoff + 4])
        stop = None
        if n < (self.nrecs - 1):
            stop, = unpack('>I', self.data[offoff + 8:offoff + 12])
        return StreamSlicer(self.stream, start, stop)

    def update(self, mi):
        recs = []
        from calibre.ebooks.mobi.from_any import config
        if mi.author_sort and config().parse().prefer_author_sort:
            authors = mi.author_sort
            recs.append((100, authors.encode(self.codec, 'replace')))
        elif mi.authors:
            authors = '; '.join(mi.authors)
            recs.append((100, authors.encode(self.codec, 'replace')))
        if mi.publisher:
            recs.append((101, mi.publisher.encode(self.codec, 'replace')))
        if mi.comments:
            recs.append((103, mi.comments.encode(self.codec, 'replace')))
        if mi.isbn:
            recs.append((104, mi.isbn.encode(self.codec, 'replace')))
        if mi.tags:
            subjects = '; '.join(mi.tags)
            recs.append((105, subjects.encode(self.codec, 'replace')))
        if self.cover_record is not None:
            recs.append((201, pack('>I', self.cover_rindex)))
            recs.append((203, pack('>I', 0)))
        if self.thumbnail_record is not None:
            recs.append((202, pack('>I', self.thumbnail_rindex)))
        exth = StringIO()
        if getattr(self, 'encryption_type', -1) != 0:
            raise MobiError('Setting metadata in DRMed MOBI files is not supported.')
        for code, data in recs:
            exth.write(pack('>II', code, len(data) + 8))
            exth.write(data)
        exth = exth.getvalue()
        trail = len(exth) % 4
        pad = '\0' * (4 - trail) # Always pad w/ at least 1 byte
        exth = ['EXTH', pack('>II', len(exth) + 12, len(recs)), exth, pad]
        exth = ''.join(exth)
        title = (mi.title or _('Unknown')).encode(self.codec, 'replace')
        if getattr(self, 'exth', None) is None:
            raise MobiError('No existing EXTH record. Cannot update metadata.')
        title_off = (self.exth.start - self.record0.start) + len(exth)
        title_len = len(title)
        trail = len(self.exth) - len(exth) - len(title)
        if trail < 0:
            raise MobiError("Insufficient space to update metadata")
        self.exth[:] = ''.join([exth, title, '\0' * trail])
        self.record0[84:92] = pack('>II', title_off, title_len)
        self.record0[92:96] = iana2mobi(mi.language)
        if mi.cover_data[1] or mi.cover:
            try:
                data =  mi.cover_data[1] if mi.cover_data[1] else open(mi.cover, 'rb').read()
            except:
                pass
            else:
                if self.cover_record is not None:
                    size = len(self.cover_record)
                    cover = rescale_image(data, size)
                    cover += '\0' * (size - len(cover))
                    self.cover_record[:] = cover
                if self.thumbnail_record is not None:
                    size = len(self.thumbnail_record)
                    thumbnail = rescale_image(data, size, dimen=MAX_THUMB_DIMEN)
                    thumbnail += '\0' * (size - len(thumbnail))
                    self.thumbnail_record[:] = thumbnail
        return

def set_metadata(stream, mi):
    mu = MetadataUpdater(stream)
    mu.update(mi)
    return
