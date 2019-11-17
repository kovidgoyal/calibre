#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals

from polyglot.builtins import is_py3
if is_py3:
    from functools import lru_cache
else:
    from backports.functools_lru_cache import lru_cache

lru_cache
