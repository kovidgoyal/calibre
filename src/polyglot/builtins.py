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
        return {only_unicode_recursive(k, encoding, errors): only_unicode_recursive(v, encoding, errors) for k, v in iteritems(x)}
    return x


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
    string_or_unicode = str, unicode
    long_type = long
    exec_path = execfile
    raw_input = builtins.raw_input
    cmp = builtins.cmp
    int_to_byte = chr
    getcwd = os.getcwdu

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

    if hasattr(sys, 'getwindowsversion'):
        def getenv(x, default=None):
            if isinstance(x, bytes):
                x = x.decode('mbcs', 'replace')

            if getenv.buf is None:
                import ctypes
                import ctypes.wintypes as w
                getenv.cub = ctypes.create_unicode_buffer
                getenv.buf = getenv.cub(1024)
                getenv.gev = ctypes.windll.kernel32.GetEnvironmentVariableW
                getenv.gev.restype = w.DWORD
                getenv.gev.argtypes = [w.LPCWSTR, w.LPWSTR, w.DWORD]
            res = getenv.gev(x, getenv.buf, len(getenv.buf))
            if res == 0:
                return default
            if res > len(getenv.buf) - 4:
                getenv.buf = getenv.cub(res + 8)
                res = getenv.gev(x, getenv.buf, len(getenv.buf))
                if res == 0:
                    return default
            return getenv.buf.value
        getenv.buf = None
    else:
        def getenv(x, default=None):
            ans = os.getenv(x, default)
            if isinstance(ans, bytes):
                ans = ans.decode('utf-8', 'replace')
            return ans

    def reload(module):
        return builtins.reload(module)


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
