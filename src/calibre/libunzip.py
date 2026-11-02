#!/usr/bin/env python
# License: GPLv3 Copyright: 2008, Kovid Goyal kovid@kovidgoyal.net

import re
from typing import TYPE_CHECKING

from calibre.utils import zipfile
from calibre.utils.icu import numeric_sort_key

if TYPE_CHECKING:
    from collections.abc import Sequence

    from calibre.utils.zipfile import ZipStream


def update(
    pathtozip: str | ZipStream,
    patterns: Sequence[re.Pattern[str]],
    filepaths: Sequence[str],
    names: Sequence[str | None],
    compression: int = zipfile.ZIP_DEFLATED,
    verbose: bool = True,
) -> None:
    """
    Update files in the zip file at `pathtozip` matching the given
    `patterns` with the given `filepaths`. If more than
    one file matches, all of the files are replaced.

    :param patterns:    A list of compiled regular expressions
    :param filepaths:   A list of paths to the replacement files. Must have the
                        same length as `patterns`.
    :param names:       A list of archive names for each file in filepaths.
                        A name can be `None` in which case the name of the existing
                        file in the archive is used.
    :param compression: The compression to use when replacing files. Can be
                        either `zipfile.ZIP_DEFLATED` or `zipfile.ZIP_STORED`.
    """
    assert len(patterns) == len(filepaths) == len(names)
    z = zipfile.ZipFile(pathtozip, mode='a')
    for name in z.namelist():
        for pat, fname, new_name in zip(patterns, filepaths, names):
            if pat.search(name):
                if verbose:
                    print(f'Updating {name} with {fname}')
                if new_name is None:
                    z.replace(fname, arcname=name, compress_type=compression)
                else:
                    z.delete(name)
                    z.write(fname, new_name, compress_type=compression)
                break
    z.close()


def extract(filename: str | ZipStream, dir: str) -> None:
    """
    Extract archive C{filename} into directory C{dir}
    """
    zf = zipfile.ZipFile(filename)
    zf.extractall(dir)


def sort_key(filename: str) -> tuple[bytes, bytes]:
    bn, ext = filename.rpartition('.')[::2]
    if not bn and ext:
        bn, ext = ext, bn
    return (numeric_sort_key(bn), numeric_sort_key(ext))


def extract_member(
    filename: str | ZipStream, match: re.Pattern[str] = re.compile(r'\.(jpg|jpeg|gif|png)\s*$', re.I), sort_alphabetically: bool = False
) -> tuple[str, bytes] | None:
    zf = zipfile.ZipFile(filename)
    names = list(zf.namelist())
    if sort_alphabetically:
        names.sort(key=sort_key)
    for name in names:
        if match.search(name):
            return name, zf.read(name)


comic_exts = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'avif', 'jxl'}


def name_ok(name: str) -> bool:
    return bool(name and not name.startswith('__MACOSX/') and name.rpartition('.')[-1].lower() in comic_exts)


def extract_cover_image(filename: str | ZipStream) -> tuple[str, bytes] | None:
    with zipfile.ZipFile(filename) as zf:
        for name in sorted(zf.namelist(), key=sort_key):
            if name_ok(name):
                return name, zf.read(name)
