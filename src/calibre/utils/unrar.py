#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
import shutil
import re
from io import BytesIO

from calibre.constants import filesystem_encoding, iswindows
from calibre.ptempfile import PersistentTemporaryFile, TemporaryDirectory
from polyglot.builtins import string_or_bytes


def as_unicode(x):
    if isinstance(x, bytes):
        x = x.decode(filesystem_encoding)
    return x


class StreamAsPath:

    def __init__(self, stream):
        self.stream = stream

    def __enter__(self):
        self.temppath = None
        if isinstance(self.stream, string_or_bytes):
            return as_unicode(self.stream)
        name = getattr(self.stream, 'name', None)
        if name and os.access(name, os.R_OK):
            return as_unicode(name)
        pos = self.stream.tell()
        with PersistentTemporaryFile('for-unar', 'wb') as f:
            shutil.copyfileobj(self.stream, f)
        self.stream.seek(pos)
        self.temppath = f.name
        return as_unicode(f.name)

    def __exit__(self, *a):
        if self.temppath is not None:
            try:
                os.remove(self.temppath)
            except OSError:
                pass
        self.temppath = None


def extract(path_or_stream, location):
    from unrardll import extract
    with StreamAsPath(path_or_stream) as path:
        return extract(path, location)


def names(path_or_stream):
    from unrardll import names
    with StreamAsPath(path_or_stream) as path:
        yield from names(path, only_useful=True)


def comment(path_or_stream):
    from unrardll import comment
    with StreamAsPath(path_or_stream) as path:
        return comment(path)


def extract_member(
    path_or_stream, match=re.compile(r'\.(jpg|jpeg|gif|png)\s*$', re.I), name=None):
    from unrardll import extract_member
    if iswindows and name is not None:
        name = name.replace(os.sep, '/')

    def is_match(header):
        fname = header['filename']
        if iswindows:
            fname = fname.replace(os.sep, '/')
        return (name is not None and fname == name) or \
               (match is not None and match.search(fname) is not None)

    with StreamAsPath(path_or_stream) as path:
        name, data = extract_member(path, is_match)
        if name is not None:
            return name, data


def extract_first_alphabetically(stream):
    from calibre.libunzip import sort_key
    names_ = sorted((
        x for x in names(stream)
        if os.path.splitext(x)[1][1:].lower() in {
            'png', 'jpg', 'jpeg', 'gif', 'webp'}),
                    key=sort_key)
    return extract_member(stream, name=names_[0], match=None)


def extract_cover_image(stream):
    from calibre.libunzip import sort_key, name_ok
    for name in sorted(names(stream), key=sort_key):
        if name_ok(name):
            return extract_member(stream, name=name, match=None)


# Test normal RAR file {{{


def test_basic():

    stream = BytesIO(  # {{{
        b"Rar!\x1a\x07\x00\xcf\x90s\x00\x00\r\x00\x00\x00\x00\x00\x00\x00\x14\xe7z\x00\x80#\x00\x17\x00\x00\x00\r\x00\x00\x00\x03\xc2\xb3\x96o\x00\x00\x00\x00\x1d3\x03\x00\x00\x00\x00\x00CMT\x0c\x00\x8b\xec\x8e\xef\x14\xf6\xe6h\x04\x17\xff\xcd\x0f\xffk9b\x11]^\x80\xd3dt \x90+\x00\x14\x00\x00\x00\x08\x00\x00\x00\x03\xf1\x84\x93\\\xb9]yA\x1d3\t\x00\xa4\x81\x00\x001\\sub-one\x00\xc0\x0c\x00\x8f\xec\x89\xfe.JM\x86\x82\x0c_\xfd\xfd\xd7\x11\x1a\xef@\x9eHt \x80'\x00\x0e\x00\x00\x00\x04\x00\x00\x00\x03\x9f\xa8\x17\xf8\xaf]yA\x1d3\x07\x00\xa4\x81\x00\x00one.txt\x00\x08\xbf\x08\xae\xf3\xca\x87\xfeo\xfe\xd2n\x80-Ht \x82:\x00\x18\x00\x00\x00\x10\x00\x00\x00\x03\xa86\x81\xdf\xf9fyA\x1d3\x1a\x00\xa4\x81\x00\x00\xe8\xaf\xb6\xe6\xaf\x94\xe5\xb1\x81.txt\x00\x8bh\xf6\xd4kA\\.\x00txt\x0c\x00\x8b\xec\x8e\xef\x14\xf6\xe2l\x91\x189\xff\xdf\xfe\xc2\xd3:g\x9a\x19F=cYt \x928\x00\x11\x00\x00\x00\x08\x00\x00\x00\x03\x7f\xd6\xb6\x7f\xeafyA\x1d3\x16\x00\xa4\x81\x00\x00F\xc3\xbc\xc3\x9fe.txt\x00\x01\x00F\xfc\xdfe\x00.txt\x00\xc0<D\xfe\xc8\xef\xbc\xd1\x04I?\xfd\xff\xdbF)]\xe8\xb9\xe1t \x90/\x00\x13\x00\x00\x00\x08\x00\x00\x00\x03\x1a$\x932\xc2]yA\x1d3\r\x00\xa4\x81\x00\x002\\sub-two.txt\x00\xc0\x10\x00S\xec\xcb\x7f\x8b\xa5(\x0b\x01\xcb\xef\xdf\xf6t\x89\x97z\x0eft \x90)\x00\r\x00\x00\x00\r\x00\x00\x00\x03c\x89K\xd3\xc8fyA\x140\x07\x00\xff\xa1\x00\x00symlink\x00\xc02/sub-two.txt\xeb\x86t\xe0\x90#\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00\x00\xb9]yA\x140\x01\x00\xedA\x00\x001\x00\xc0\xe0Dt\xe0\x90#\x00\x00\x00\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00\x00\xc2]yA\x140\x01\x00\xedA\x00\x002\x00\xc0u\xa1t \x80,\x00\r\x00\x00\x00\r\x00\x00\x00\x03T\xea\x04\xca\xe6\x84yA\x140\x0c\x00\xa4\x81\x00\x00uncompresseduncompressed\n\xda\x10t \x900\x00\x0e\x00\x00\x00\x04\x00\x00\x00\x035K.\xa6\x18\x85yA\x1d5\x0e\x00\xa4\x81\x00\x00max-compressed\x00\xc0\x00\x08\xbf\x08\xae\xf2\xcc\x01s\xf8\xff\xec\x96\xe8\xc4={\x00@\x07\x00")  # noqa }}}

    tdata = {
        '1': b'',
        '1/sub-one': b'sub-one\n',
        '2': b'',
        '2/sub-two.txt': b'sub-two\n',
        'F\xfc\xdfe.txt': b'unicode\n',
        'max-compressed': b'max\n',
        'one.txt': b'one\n',
        'symlink': b'2/sub-two.txt',
        'uncompressed': b'uncompressed\n',
        '\u8bf6\u6bd4\u5c41.txt': b'chinese unicode\n'}

    def do_test(stream):
        c = comment(stream)
        expected = 'some comment\n'
        if c != expected:
            raise ValueError(f'Comment not read: {c!r} != {expected!r}')
        if set(names(stream)) != {
            '1/sub-one', 'one.txt', '2/sub-two.txt', '诶比屁.txt', 'Füße.txt',
            'uncompressed', 'max-compressed'}:
            raise ValueError('Name list does not match')
        with TemporaryDirectory('test-unrar') as tdir:
            extract(stream, tdir)
            for name in tdata:
                if name not in '1 2 symlink'.split():
                    with open(os.path.join(tdir, name), 'rb') as s:
                        if s.read() != tdata[name]:
                            raise ValueError('Did not extract %s properly' % name)
        for name in tdata:
            if name not in '1 2 symlink'.split():
                d = extract_member(stream, name=name)
                if d is None or d[1] != tdata[name]:
                    raise ValueError(
                        f'Failed to extract {name} {d!r} != {tdata[name]!r}')

    do_test(stream)
    with PersistentTemporaryFile('test-unrar') as f:
        shutil.copyfileobj(stream, f)
    with open(f.name, 'rb') as stream:
        do_test(stream)
    os.remove(f.name)


if __name__ == '__main__':
    test_basic()
