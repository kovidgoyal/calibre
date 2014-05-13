#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.Qt import QTextCharFormat, QFont

from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.container import guess_type

def syntax_from_mime(name, mime):
    if mime in OEB_DOCS:
        return 'html'
    if mime in OEB_STYLES:
        return 'css'
    if mime in {guess_type('a.svg'), guess_type('a.opf'), guess_type('a.ncx'), guess_type('a.xml'), 'application/oebps-page-map+xml'}:
        return 'xml'
    if mime.startswith('text/'):
        return 'text'
    if mime.startswith('image/') and mime.partition('/')[-1].lower() in {
        'jpeg', 'jpg', 'gif', 'png'}:
        return 'raster_image'

def editor_from_syntax(syntax, parent=None):
    if syntax in {'text', 'html', 'css', 'xml'}:
        from calibre.gui2.tweak_book.editor.widget import Editor
        return Editor(syntax, parent=parent)
    elif syntax == 'raster_image':
        from calibre.gui2.tweak_book.editor.image import Editor
        return Editor(syntax, parent=parent)


SYNTAX_PROPERTY = QTextCharFormat.UserProperty
SPELL_PROPERTY = SYNTAX_PROPERTY + 1

class SyntaxTextCharFormat(QTextCharFormat):

    def __init__(self, *args):
        QTextCharFormat.__init__(self, *args)
        self.setProperty(SYNTAX_PROPERTY, True)

    def __repr__(self):
        return 'SyntaxFormat(id=%s, color=%s, italic=%s, bold=%s)' % (
            id(self), self.foreground().color().name(), self.fontItalic(), self.fontWeight() >= QFont.DemiBold)
    __str__ = __repr__


