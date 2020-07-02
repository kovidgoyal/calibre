#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from polyglot.builtins import is_py3

if is_py3:
    from plistlib import loads, dumps  # noqa
else:
    from plistlib import readPlistFromString as loads, writePlistToString as dumps  # noqa
