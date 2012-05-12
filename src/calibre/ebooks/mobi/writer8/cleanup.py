#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.oeb.base import XPath

class CSSCleanup(object):

    def __init__(self, log, opts):
        self.log, self.opts = log, opts

    def __call__(self, item, stylizer):
        if not hasattr(item.data, 'xpath'): return

        # The Kindle touch displays all black pages if the height is set on
        # body
        for body in XPath('//h:body')(item.data):
            style = stylizer.style(body)
            style.drop('height')

