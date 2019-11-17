#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt5.Qt import QTextCharFormat

from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.container import guess_type

_xml_types = {'application/oebps-page-map+xml', 'application/vnd.adobe-page-template+xml', 'application/page-template+xml'} | {
            guess_type('a.'+x) for x in ('ncx', 'opf', 'svg', 'xpgt', 'xml')}
_js_types = {'application/javascript', 'application/x-javascript'}


def syntax_from_mime(name, mime):
    for syntax, types in (('html', OEB_DOCS), ('css', OEB_STYLES), ('xml', _xml_types)):
        if mime in types:
            return syntax
    if mime in _js_types:
        return 'javascript'
    if mime.startswith('text/'):
        return 'text'
    if mime.startswith('image/') and mime.partition('/')[-1].lower() in {
        'jpeg', 'jpg', 'gif', 'png'}:
        return 'raster_image'
    if mime.endswith('+xml'):
        return 'xml'


all_text_syntaxes = frozenset({'text', 'html', 'xml', 'css', 'javascript'})


def editor_from_syntax(syntax, parent=None):
    if syntax in all_text_syntaxes:
        from calibre.gui2.tweak_book.editor.widget import Editor
        return Editor(syntax, parent=parent)
    elif syntax == 'raster_image':
        from calibre.gui2.tweak_book.editor.image import Editor
        return Editor(syntax, parent=parent)


SYNTAX_PROPERTY = QTextCharFormat.UserProperty
SPELL_PROPERTY = SYNTAX_PROPERTY + 1
SPELL_LOCALE_PROPERTY = SPELL_PROPERTY + 1
LINK_PROPERTY = SPELL_LOCALE_PROPERTY + 1
TAG_NAME_PROPERTY = LINK_PROPERTY + 1
CSS_PROPERTY = TAG_NAME_PROPERTY + 1
CLASS_ATTRIBUTE_PROPERTY = CSS_PROPERTY + 1


def syntax_text_char_format(*args):
    ans = QTextCharFormat(*args)
    ans.setProperty(SYNTAX_PROPERTY, True)
    return ans


class StoreLocale(object):

    __slots__ = ('enabled',)

    def __init__(self):
        self.enabled = False

    def __enter__(self):
        self.enabled = True

    def __exit__(self, *args):
        self.enabled = False


store_locale = StoreLocale()
