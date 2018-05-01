#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2018, Kovid Goyal <kovid at kovidgoyal.net>

from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

from calibre.constants import plugins


def character_name_from_code(code):
    return plugins['unicode_names'][0].name_for_codepoint(code) or 'U+{:X}'.format(code)
