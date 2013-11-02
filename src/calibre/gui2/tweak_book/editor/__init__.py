#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.container import guess_type

def syntax_from_mime(mime):
    if mime in OEB_DOCS:
        return 'html'
    if mime in OEB_STYLES:
        return 'css'
    if mime in {guess_type('a.opf'), guess_type('a.ncx'), guess_type('a.xml')}:
        return 'xml'
    if mime.startswith('text/'):
        return 'text'

def editor_from_syntax(syntax, parent=None):
    if syntax not in {'text', 'html', 'css', 'xml'}:
        return None
    from calibre.gui2.tweak_book.editor.widget import Editor
    return Editor(syntax, parent=parent)

