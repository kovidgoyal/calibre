#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.ebooks.docx.names import XPath, get

class Settings(object):

    def __init__(self):
        self.default_tab_stop = 720 / 20

    def __call__(self, root):
        for dts in XPath('//w:defaultTabStop[@w:val]')(root):
            try:
                self.default_tab_stop = int(get(dts, 'w:val')) / 20
            except (ValueError, TypeError, AttributeError):
                pass

