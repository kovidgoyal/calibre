#!/usr/bin/env python
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>

import sys
import weakref
from threading import Lock
from typing import TYPE_CHECKING, Literal, overload

if TYPE_CHECKING:
    from collections.abc import Callable

    from calibre.scraper.qt import WebEngineBrowser

overseers: list[weakref.ref[WebEngineBrowser]] = []


def cleanup_overseers() -> Callable[[], None]:
    browsers = tuple(filter(None, (x() for x in overseers)))
    del overseers[:]

    def join_all() -> None:
        for br in browsers:
            br.shutdown()

    return join_all


read_url_lock = Lock()


@overload
def read_url(storage: list[WebEngineBrowser], url: str, timeout: float = 60, as_html: Literal[True] = True) -> str: ...
@overload
def read_url(storage: list[WebEngineBrowser], url: str, timeout: float = 60, *, as_html: Literal[False]) -> bytes: ...
@overload
def read_url(storage: list[WebEngineBrowser], url: str, timeout: float, as_html: Literal[False]) -> bytes: ...
@overload
def read_url(storage: list[WebEngineBrowser], url: str, timeout: float = 60, as_html: bool = True) -> str | bytes: ...
def read_url(storage: list[WebEngineBrowser], url: str, timeout: float = 60, as_html: bool = True) -> str | bytes:
    with read_url_lock:
        from calibre.scraper.qt import WebEngineBrowser

        if not storage:
            storage.append(WebEngineBrowser())
            overseers.append(weakref.ref(storage[-1]))
        scraper = storage[0]
    raw_bytes = scraper.open_novisit(url, timeout=timeout).read()
    if not as_html:
        return raw_bytes
    from calibre.ebooks.chardet import xml_to_unicode

    return xml_to_unicode(raw_bytes, strip_encoding_pats=True)[0]


if __name__ == '__main__':
    try:
        print(read_url([], sys.argv[-1]))
    finally:
        cleanup_overseers()()
