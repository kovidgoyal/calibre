#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os

from sphinx.builders.latex import LaTeXBuilder
from sphinx.util.logging import getLogger
from sphinx.writers.latex import LaTeXTranslator


def info(*a):
    getLogger(__name__).info(*a)


class FixedLaTeXTranslator(LaTeXTranslator):
    # see https://github.com/sphinx-doc/sphinx/issues/8936

    def visit_substitution_definition(self, node):
        pass

    def depart_substitution_definition(self, node):
        pass


class LaTeXHelpBuilder(LaTeXBuilder):
    name = 'mylatex'
    default_translator_class = FixedLaTeXTranslator

    def finish(self):
        super().finish()
        info('Fixing Cyrillic characters...')
        tex = os.path.join(self.outdir, 'calibre.tex')
        with open(tex, 'r+b') as f:
            raw = f.read().decode('utf-8')
            for x in (u'Михаил Горбачёв', u'Фёдор Миха́йлович Достоевский'):
                raw = raw.replace(x, u'{\\fontencoding{T2A}\\selectfont %s}' % (x.replace(u'а́', u'a')))
            f.seek(0)
            f.write(raw.encode('utf-8'))
