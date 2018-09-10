#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from sphinx.builders.latex import LaTeXBuilder


class LaTeXHelpBuilder(LaTeXBuilder):
    name = 'mylatex'

    def finish(self):
        LaTeXBuilder.finish(self)
        self.info('Fixing Cyrillic characters...')
        tex = os.path.join(self.outdir, 'calibre.tex')
        with open(tex, 'r+b') as f:
            raw = f.read().decode('utf-8')
            for x in (u'Михаил Горбачёв', u'Фёдор Миха́йлович Достоевский'):
                raw = raw.replace(x, u'{\\fontencoding{T2A}\\selectfont %s}' % (x.replace(u'а́', u'a')))
            f.seek(0)
            f.write(raw.encode('utf-8'))
