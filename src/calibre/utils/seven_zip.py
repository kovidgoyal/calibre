#!/usr/bin/env python
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>

import io
import os
import re

from calibre.constants import iswindows


def open_archive(path_or_stream, mode='r'):
    from py7zr import SevenZipFile
    return SevenZipFile(path_or_stream, mode=mode)


def names(path_or_stream):
    with open_archive(path_or_stream) as zf:
        return tuple(zf.getnames())


class Writer:

    def __init__(self):
        self.outputs = {}

    def create(self, filename):
        b = self.outputs[filename] = io.BytesIO()
        return b

    def asdatadict(self):
        return {k: v.getvalue() for k, v in self.outputs.items()}


def read_file(archive, name):
    w = Writer()
    archive.extract(targets=[name], factory=w)
    for v in w.outputs.values():
        return v.getvalue()
    raise KeyError(f'No file named {name} in archive')


def extract_member(path_or_stream, match=None, name=None):
    if iswindows and name is not None:
        name = name.replace(os.sep, '/')
    if match is None:
        match = re.compile(r'\.(jpg|jpeg|gif|png)\s*$', re.I)

    def is_match(fname):
        if iswindows:
            fname = fname.replace(os.sep, '/')
        return (name is not None and fname == name) or \
               (match is not None and match.search(fname) is not None)

    with open_archive(path_or_stream) as ar:
        all_names = list(filter(is_match, ar.getnames()))
        if all_names:
            return all_names[0], read_file(ar, all_names[0])


def extract_cover_image(stream):
    pos = stream.tell()
    from calibre.libunzip import name_ok, sort_key
    all_names = sorted(names(stream), key=sort_key)
    stream.seek(pos)
    for name in all_names:
        if name_ok(name):
            return extract_member(stream, name=name, match=None)


def extract(path_or_stream, location):
    with open_archive(path_or_stream) as f:
        f.extract(location)


# Test {{{

def test_basic():
    from tempfile import TemporaryDirectory

    from calibre import CurrentDir

    tdata = {
        '1/sub-one': b'sub-one\n',
        '2/sub-two.txt': b'sub-two\n',
        'F\xfc\xdfe.txt': b'unicode\n',
        'max-compressed': b'max\n',
        'one.txt': b'one\n',
        'symlink': b'2/sub-two.txt',
        'uncompressed': b'uncompressed\n',
        '\u8bf6\u6bd4\u5c41.txt': b'chinese unicode\n'}

    def do_test():
        for name, data in tdata.items():
            if '/' in name:
                os.makedirs(os.path.dirname(name), exist_ok=True)
            with open(name, 'wb') as f:
                f.write(data)
        with open_archive(os.path.join('a.7z'), mode='w') as zf:
            for name in tdata:
                zf.write(name)
        with open_archive(os.path.join('a.7z')) as zf:
            if set(zf.getnames()) != set(tdata):
                raise ValueError('names not equal')
            w = Writer()
            zf.extractall(factory=w)
            read_data = w.asdatadict()
            if read_data != tdata:
                raise ValueError('data not equal')

        os.mkdir('ex')
        extract('a.7z', 'ex')
        for name in tdata:
            if name not in '1 2 symlink'.split():
                with open(os.path.join(tdir, 'ex', name), 'rb') as s:
                    if s.read() != tdata[name]:
                        raise ValueError(f'Did not extract {name} properly')
        if extract_member('a.7z', name='one.txt')[1] != tdata['one.txt']:
            raise ValueError('extract_member failed')

    with TemporaryDirectory('test-7z') as tdir, CurrentDir(tdir):
        do_test()


if __name__ == '__main__':
    test_basic()
