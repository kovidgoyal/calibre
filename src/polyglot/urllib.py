#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPL v3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import absolute_import, division, print_function, unicode_literals


from polyglot.builtins import is_py3

if is_py3:
    from urllib.request import urlopen, Request  # noqa
    from urllib.parse import urlencode  # noqa
else:
    from urllib import urlencode  # noqa
    from urllib2 import urlopen, Request  # noqa
