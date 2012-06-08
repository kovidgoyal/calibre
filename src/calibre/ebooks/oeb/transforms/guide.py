#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


class Clean(object):
    '''Clean up guide, leaving only known values '''

    def __call__(self, oeb, opts):
        self.oeb, self.log, self.opts = oeb, oeb.log, opts

        if 'cover' not in self.oeb.guide:
            covers = []
            for x in ('other.ms-coverimage-standard', 'coverimagestandard',
                    'other.ms-titleimage-standard', 'other.ms-titleimage',
                    'other.ms-coverimage', 'other.ms-thumbimage-standard',
                    'other.ms-thumbimage', 'thumbimagestandard'):
                if x in self.oeb.guide:
                    href = self.oeb.guide[x].href
                    item = self.oeb.manifest.hrefs[href]
                    covers.append([self.oeb.guide[x], len(item.data)])
            covers.sort(cmp=lambda x,y:cmp(x[1], y[1]), reverse=True)
            if covers:
                ref = covers[0][0]
                if len(covers) > 1:
                    self.log('Choosing %s:%s as the cover'%(ref.type, ref.href))
                ref.type = 'cover'
                self.oeb.guide.refs['cover'] = ref

        if ('start' in self.oeb.guide and 'text' not in self.oeb.guide):
            # Prefer text to start as per the OPF 2.0 spec
            x = self.oeb.guide['start']
            self.oeb.guide.add('text', x.title, x.href)
            self.oeb.guide.remove('start')

        for x in list(self.oeb.guide):
            if x.lower() not in {'cover', 'titlepage', 'masthead', 'toc',
                    'title-page', 'copyright-page', 'text'}:
                item = self.oeb.guide[x]
                if item.title and item.title.lower() == 'start':
                    continue
                self.oeb.guide.remove(x)

