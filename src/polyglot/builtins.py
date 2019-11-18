#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

import os
import sys

is_py3 = sys.version_info.major >= 3
native_string_type = str
iterkeys = iter


def hasenv(x):
    return getenv(x) is not None


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


def only_unicode_recursive(x, encoding='utf-8', errors='strict'):
    # Convert any bytestrings in sets/lists/tuples/dicts to unicode
    if isinstance(x, bytes):
        return x.decode(encoding, errors)
    if isinstance(x, unicode_type):
        return x
    if isinstance(x, (set, list, tuple, frozenset)):
        return type(x)(only_unicode_recursive(i, encoding, errors) for i in x)
    if isinstance(x, dict):
        return {
            only_unicode_recursive(k, encoding, errors):
            only_unicode_recursive(v, encoding, errors)
            for k, v in iteritems(x)
        }
    return x


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
string_or_unicode = str
long_type = int
raw_input = input
getcwd = os.getcwd
getenv = os.getenv


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
    return bytes((x, ))


def reload(module):
    import importlib
    return importlib.reload(module)


def print_to_binary_file(fileobj, encoding='utf-8'):

    def print(*a, **kw):
        f = kw.get('file', fileobj)
        if a:
            sep = as_bytes(kw.get('sep', ' '), encoding)
            for x in a:
                x = as_bytes(x, encoding)
                f.write(x)
                if x is not a[-1]:
                    f.write(sep)
        f.write(as_bytes(kw.get('end', '\n')))

    return print
