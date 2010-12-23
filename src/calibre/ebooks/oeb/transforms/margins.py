#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


class RemoveFakeMargins(object):
    '''
    Try to detect and remove fake margins inserted by asinine ebook creation
    software on each paragraph/wrapper div. Can be used only after CSS
    flattening.
    '''

    def __call__(self, oeb, opts, log):
        self.oeb, self.opts, self.log = oeb, opts, log

        from calibre.ebooks.oeb.base import XPath, OEB_STYLES

        stylesheet = None
        for item in self.oeb.manifest:
            if item.media_type.lower() in OEB_STYLES:
                stylesheet = item.data
                break

        if stylesheet is None:
            return


        top_level_elements = {}
        second_level_elements = {}

        for x in self.oeb.spine:
            root = x.data
            body = XPath('//h:body')(root)
            if body:
                body = body[0]

            if not hasattr(body, 'xpath'):
                continue

            # Check for margins on top level elements
            for lb in XPath('./h:div|./h:p|./*/h:div|./*/h:p')(body):
                cls = lb.get('class', '')
                level = top_level_elements if lb.getparent() is body else \
                        second_level_elements
                if cls not in level:
                    level[cls] = []
                    top_level_elements[cls] = []
                level[cls].append(lb)


    def get_margins(self, stylesheet, cls):
        pass

