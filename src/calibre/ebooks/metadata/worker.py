#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid at kovidgoyal.net>

import os
import shutil
from typing import TYPE_CHECKING

from calibre.customize.ui import run_plugins_on_import
from calibre.ebooks.metadata.meta import metadata_from_formats
from calibre.ebooks.metadata.opf2 import metadata_to_opf
from calibre.utils.filenames import samefile
from calibre.utils.icu import lower as icu_lower

if TYPE_CHECKING:
    from collections.abc import Container, Iterable

    from calibre.ebooks.metadata.book.base import Metadata


def serialize_metadata_for(paths: list[str], tdir: str, group_id: int) -> tuple[Metadata, bytes, bool]:
    mi = metadata_from_formats(paths)
    mi.cover = None
    cdata = mi.cover_data[-1]
    mi.cover_data = (None, None)
    if not mi.application_id:
        mi.application_id = '__calibre_dummy__'
    opf = metadata_to_opf(mi, default_lang='und')
    has_cover = False
    if cdata:
        with open(os.path.join(tdir, f'{group_id}.cdata'), 'wb') as f:
            f.write(cdata)
            has_cover = True
    return mi, opf, has_cover


def read_metadata_bulk(get_opf: bool, get_cover: bool, paths: list[str]) -> dict[str, bytes | None]:
    mi = metadata_from_formats(paths)
    mi.cover = None
    cdata = mi.cover_data[-1]
    mi.cover_data = (None, None)
    if not mi.application_id:
        mi.application_id = '__calibre_dummy__'
    ans: dict[str, bytes | None] = {'opf': None, 'cdata': None}
    if get_opf:
        ans['opf'] = metadata_to_opf(mi, default_lang='und')
    if get_cover:
        ans['cdata'] = cdata
    return ans


def run_import_plugins(paths: Iterable[str], group_id: int, tdir: str) -> list[str]:
    final_paths = []
    for path in paths:
        if not os.access(path, os.R_OK):
            continue
        try:
            nfp = run_plugins_on_import(path)
        except Exception:
            nfp = None
            import traceback

            traceback.print_exc()
        if nfp and os.access(nfp, os.R_OK) and not samefile(nfp, path):
            # Ensure that the filename is preserved so that
            # reading metadata from filename is not broken
            name = os.path.splitext(os.path.basename(path))[0]
            ext = os.path.splitext(nfp)[1]
            path = os.path.join(tdir, str(group_id), name + ext)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                os.replace(nfp, path)
            except OSError:
                shutil.copyfile(nfp, path)
        final_paths.append(path)
    return final_paths


def has_book(mi: Metadata, data_for_has_book: Container[str]) -> bool | str | None:
    return mi.title and icu_lower(mi.title.strip()) in data_for_has_book


def read_metadata(
    paths: Iterable[str], group_id: int, tdir: str, common_data: set[str] | frozenset[str] | None = None
) -> tuple[list[str], bytes, bool, bool | str | None]:
    paths = run_import_plugins(paths, group_id, tdir)
    mi, opf, has_cover = serialize_metadata_for(paths, tdir, group_id)
    duplicate_info = None
    if isinstance(common_data, (set, frozenset)):
        duplicate_info = has_book(mi, common_data)
    return paths, opf, has_cover, duplicate_info
