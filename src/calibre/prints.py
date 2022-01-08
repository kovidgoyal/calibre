#!/usr/bin/env python
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

import io
import sys

from polyglot.builtins import as_bytes, as_unicode


def is_binary(stream):
    mode = getattr(stream, 'mode', None)
    if mode:
        return 'b' in mode
    return not isinstance(stream, io.TextIOBase)


def prints(*a, **kw):
    ' Print either unicode or bytes to either binary or text mode streams '
    stream = kw.get('file', sys.stdout)
    if stream is None:
        return
    sep, end = kw.get('sep'), kw.get('end')
    if sep is None:
        sep = ' '
    if end is None:
        end = '\n'
    if is_binary(stream):
        encoding = getattr(stream, 'encoding', None) or 'utf-8'
        a = (as_bytes(x, encoding=encoding) for x in a)
        sep = as_bytes(sep)
        end = as_bytes(end)
    else:
        a = (as_unicode(x, errors='replace') for x in a)
        sep = as_unicode(sep)
        end = as_unicode(end)
    for i, x in enumerate(a):
        if sep and i != 0:
            stream.write(sep)
        stream.write(x)
    if end:
        stream.write(end)
    if kw.get('flush'):
        try:
            stream.flush()
        except Exception:
            pass
