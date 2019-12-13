#!/usr/bin/env python
# vim:fileencoding=utf-8
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
    if is_binary(stream):
        encoding = getattr(stream, 'encoding', None) or 'utf-8'
        a = tuple(as_bytes(x, encoding=encoding) for x in a)
        kw['sep'] = as_bytes(kw.get('sep', b' '))
        kw['end'] = as_bytes(kw.get('end', b'\n'))
    else:
        a = tuple(as_unicode(x, errors='replace') for x in a)
        kw['sep'] = as_unicode(kw.get('sep', ' '))
        kw['end'] = as_unicode(kw.get('end', '\n'))

    return print(*a, **kw)
