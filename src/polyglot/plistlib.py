#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

def unwrap_bytes(x):
    return x

def wrap_bytes(x):
    return x

from plistlib import loads, dumps, Data  # noqa
loads_binary_or_xml = loads
