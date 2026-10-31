#!/usr/bin/env python
# License: GPL v3 Copyright: 2021, Kovid Goyal <kovid at kovidgoyal.net>

import io
import os
import re
from typing import IO, TYPE_CHECKING, Self

from calibre.constants import iswindows

if TYPE_CHECKING:
    from py7zr import SevenZipFile


def open_archive(path_or_stream: str | IO[bytes], mode: str = 'r') -> SevenZipFile:
    from py7zr import SevenZipFile

    return SevenZipFile(path_or_stream, mode=mode)


def names(path_or_stream: str | IO[bytes]) -> tuple[str, ...]:
    with open_archive(path_or_stream) as zf:
        return tuple(zf.getnames())


class DataSavingWriter(io.BytesIO):
    def close(self) -> None:
        return  # make this a no-op as we need to call getvalue() after close


class Writer:
    def __init__(self) -> None:
        self.outputs: dict[str, DataSavingWriter] = {}

    def create(self, filename: str) -> DataSavingWriter:
        b = self.outputs[filename] = DataSavingWriter()
        return b

    def asdatadict(self) -> dict[str, bytes]:
        return {k: v.getvalue() for k, v in self.outputs.items()}

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *a: object) -> None:
        for v in self.outputs.values():
            io.BytesIO.close(v)
        self.outputs.clear()


def read_file(archive: SevenZipFile, name: str) -> bytes:
    with Writer() as w:
        archive.extract(targets=[name], factory=w)  # ty: ignore[invalid-argument-type]
        for v in w.outputs.values():
            return v.getvalue()
    raise KeyError(f'No file named {name} in archive')


def extract_member(path_or_stream: str | IO[bytes], match: re.Pattern[str] | None = None, name: str | None = None) -> tuple[str, bytes] | None:
    if iswindows and name is not None:
        name = name.replace(os.sep, '/')
    if match is None:
        match = re.compile(r'\.(jpg|jpeg|gif|png)\s*$', re.I)

    def is_match(fname: str) -> bool:
        if iswindows:
            fname = fname.replace(os.sep, '/')
        return (name is not None and fname == name) or (match is not None and match.search(fname) is not None)

    with open_archive(path_or_stream) as ar:
        all_names = list(filter(is_match, ar.getnames()))
        if all_names:
            return all_names[0], read_file(ar, all_names[0])


def extract_cover_image(stream: IO[bytes]) -> tuple[str, bytes] | None:
    pos = stream.tell()
    from calibre.libunzip import name_ok, sort_key

    all_names = sorted(names(stream), key=sort_key)
    stream.seek(pos)
    for name in all_names:
        if name_ok(name):
            return extract_member(stream, name=name, match=None)


def extract(path_or_stream: str | IO[bytes], location: str) -> None:
    with open_archive(path_or_stream) as f:
        f.extract(location)


# Test {{{


def test_basic() -> None:
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
        '\u8bf6\u6bd4\u5c41.txt': b'chinese unicode\n',
    }

    def do_test() -> None:
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
            with Writer() as w:
                zf.extractall(factory=w)
                read_data = w.asdatadict()
            if read_data != tdata:
                raise ValueError('data not equal')

        os.mkdir('ex')
        extract('a.7z', 'ex')
        for name, data in tdata.items():
            if name not in '1 2 symlink'.split():
                with open(os.path.join(tdir, 'ex', name), 'rb') as s:
                    if s.read() != data:
                        raise ValueError(f'Did not extract {name} properly')
        if extract_member('a.7z', name='one.txt')[1] != tdata['one.txt']:  # ty: ignore[not-subscriptable]
            raise ValueError('extract_member failed')

    with TemporaryDirectory('test-7z') as tdir, CurrentDir(tdir):
        do_test()


if __name__ == '__main__':
    test_basic()
