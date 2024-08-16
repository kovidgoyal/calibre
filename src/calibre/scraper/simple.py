#!/usr/bin/env python
# License: GPL v3 Copyright: 2022, Kovid Goyal <kovid at kovidgoyal.net>


import sys
import weakref
from threading import Lock

overseers = []

def cleanup_overseers():
    browsers = tuple(filter(None, (x() for x in overseers)))
    del overseers[:]

    def join_all():
        for br in browsers:
            br.shutdown()
    return join_all


read_url_lock = Lock()


def read_url(storage, url, timeout=60, as_html=True):
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
