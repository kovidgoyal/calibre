# -*- coding: utf-8 -*-

from __future__ import (unicode_literals, division, absolute_import, print_function)

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

from calibre.ebooks.oeb.base import OEB_DOCS, XPath, barename
from calibre.utils.unsmarten import unsmarten_text

class UnsmartenPunctuation(object):
    
    def unsmarten(self, root):
        for x in XPath('//h:*')(root):
            if not barename(x) == 'pre':
                if hasattr(x, 'text') and x.text:
                    x.text = unsmarten_text(x.text)
                if hasattr(x, 'tail') and x.tail:
                    x.tail = unsmarten_text(x.tail)

    def __call__(self, oeb, context):
        for x in oeb.manifest.items:
            if x.media_type in OEB_DOCS:
                self.unsmarten(x.data)
