#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from polyglot.builtins import is_py3

if is_py3:
    from plistlib import loads, dumps  # noqa

    def unwrap_bytes(x):
        return x

    def wrap_bytes(x):
        return x
else:
    from plistlib import readPlistFromString as loads, writePlistToString as dumps, Data  # noqa

    def unwrap_bytes(x):
        if isinstance(x, Data):
            x = x.data
        return x

    def wrap_bytes(x):
        return Data(x)
