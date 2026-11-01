#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid@kovidgoyal.net>

import os
import re
import sys
from typing import TYPE_CHECKING

from calibre.customize.ui import available_input_formats
from calibre.utils.localization import _

if TYPE_CHECKING:
    from calibre.ebooks.oeb.iterator import book


def is_supported(path: str) -> bool:
    ext = os.path.splitext(path)[1].replace('.', '').lower()
    ext = re.sub(r'(x{0,1})htm(l{0,1})', 'html', ext)
    return ext in available_input_formats() or ext == 'kepub'


class UnsupportedFormatError(Exception):
    def __init__(self, fmt: str) -> None:
        Exception.__init__(self, _('%s format books are not supported') % fmt.upper())


def EbookIterator(*args: object, **kwargs: object) -> book.EbookIterator:
    "For backwards compatibility"
    from calibre.ebooks.oeb.iterator.book import EbookIterator

    return EbookIterator(*args, **kwargs)  # ty: ignore[invalid-argument-type] arguments are passed through


def get_preprocess_html(path_to_ebook: str, output: str | None = None) -> None:

    from calibre.ebooks.conversion.plumber import Plumber, set_regex_wizard_callback
    from calibre.ptempfile import TemporaryDirectory
    from calibre.utils.logging import DevNull

    raw = {}
    set_regex_wizard_callback(raw.__setitem__)
    with TemporaryDirectory('_regex_wiz') as tdir:
        pl = Plumber(path_to_ebook, os.path.join(tdir, 'a.epub'), DevNull(), for_regex_wizard=True)
        pl.run()
        items = [raw[item.href] for item in pl.oeb.spine if item.href in raw]

    with sys.stdout.buffer if output is None else open(output, 'wb') as out:
        for html in items:
            out.write(html.encode('utf-8'))
            out.write(b'\n\n' + b'-' * 80 + b'\n\n')
