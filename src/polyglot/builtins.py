#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

import sys

is_py3 = sys.version_info.major >= 3
native_string_type = str


def iterkeys(d):
    return iter(d)


def as_bytes(x, encoding='utf-8'):
    if isinstance(x, unicode_type):
        return x.encode(encoding)
    if isinstance(x, bytes):
        return x
    if isinstance(x, bytearray):
        return bytes(x)
    if isinstance(x, memoryview):
        return x.tobytes()
    ans = unicode_type(x)
    if isinstance(ans, unicode_type):
        ans = ans.encode(encoding)
    return ans


def as_unicode(x, encoding='utf-8', errors='strict'):
    if isinstance(x, bytes):
        return x.decode(encoding, errors)
    return unicode_type(x)


if is_py3:
    def reraise(tp, value, tb=None):
        try:
            if value is None:
                value = tp()
            if value.__traceback__ is not tb:
                raise value.with_traceback(tb)
            raise value
        finally:
            value = None
            tb = None

    import builtins

    zip = builtins.zip
    map = builtins.map
    filter = builtins.filter
    range = builtins.range

    codepoint_to_chr = chr
    unicode_type = str
    string_or_bytes = str, bytes
    long_type = int
    raw_input = input

    def error_message(exc):
        args = getattr(exc, 'args', None)
        if args and isinstance(args[0], unicode_type):
            return args[0]
        return unicode_type(exc)

    def iteritems(d):
        return iter(d.items())

    def itervalues(d):
        return iter(d.values())

    def environ_item(x):
        if isinstance(x, bytes):
            x = x.decode('utf-8')
        return x

    def exec_path(path, ctx=None):
        ctx = ctx or {}
        with open(path, 'rb') as f:
            code = f.read()
        code = compile(code, f.name, 'exec')
        exec(code, ctx)

    def cmp(a, b):
        return (a > b) - (a < b)

    def int_to_byte(x):
        return bytes((x,))

    def reload(module):
        import importlib
        return importlib.reload(module)

else:
    exec("""def reraise(tp, value, tb=None):
    try:
        raise tp, value, tb
    finally:
        tb = None
""")

    from future_builtins import zip, map, filter  # noqa
    range = xrange
    import __builtin__ as builtins

    codepoint_to_chr = unichr
    unicode_type = unicode
    string_or_bytes = unicode, bytes
    long_type = long
    exec_path = execfile
    raw_input = builtins.raw_input
    cmp = builtins.cmp
    int_to_byte = chr

    def error_message(exc):
        ans = exc.message
        if isinstance(ans, bytes):
            ans = ans.decode('utf-8', 'replace')
        return ans

    def iteritems(d):
        return d.iteritems()

    def itervalues(d):
        return d.itervalues()

    def environ_item(x):
        if isinstance(x, unicode_type):
            x = x.encode('utf-8')
        return x

    def reload(module):
        return builtins.reload(module)
