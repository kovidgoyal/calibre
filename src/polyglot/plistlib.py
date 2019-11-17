#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>



from polyglot.builtins import is_py3

if is_py3:
    from plistlib import loads, dumps, Data  # noqa
else:
    from plistlib import readPlistFromString as loads, writePlistToString as dumps, Data  # noqa
