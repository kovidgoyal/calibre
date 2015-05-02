#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.constants import isosx

SHORTCUTS = {
        'Next Page' : (['PgDown', 'Space'],
            _('Scroll to the next page')),

        'Previous Page' : (['PgUp', 'Backspace', 'Shift+Space'],
            _('Scroll to the previous page')),

        'Next Section' : (['Ctrl+PgDown', 'Ctrl+Down'],
            _('Scroll to the next section')),

        'Previous Section' : (['Ctrl+PgUp', 'Ctrl+Up'],
            _('Scroll to the previous section')),

        'Section Bottom' : (['End'],
            _('Scroll to the bottom of the section')),

        'Section Top' : (['Home'],
            _('Scroll to the top of the section')),

        'Document Bottom' : (['Ctrl+End'],
            _('Scroll to the end of the document')),

        'Document Top' : (['Ctrl+Home'],
            _('Scroll to the start of the document')),

        'Down' : (['J', 'Down'],
            _('Scroll down')),

        'Up' : (['K', 'Up'],
            _('Scroll up')),

        'Left' : (['H', 'Left'],
            _('Scroll left')),

        'Right' : (['L', 'Right'],
            _('Scroll right')),

        'Back': (['Alt+Left'],
            _('Back')),

        'Forward': (['Alt+Right'],
            _('Forward')),

        'Quit': (['Ctrl+Q', 'Ctrl+W', 'Alt+F4'],
            _('Quit')),

        'Focus Search': (['/', 'Ctrl+F'],
            _('Start search')),

        'Show metadata': (['Ctrl+I'],
            _('Show metadata')),

        'Font larger': (['Ctrl+='],
            _('Font size larger')),

        'Font smaller': (['Ctrl+-'],
            _('Font size smaller')),

        'Fullscreen': ((['Ctrl+Meta+F'] if isosx else ['Ctrl+Shift+F', 'F11']),
            _('Fullscreen')),

        'Find next': (['F3'],
            _('Find next')),

        'Find previous': (['Shift+F3'],
            _('Find previous')),

        'Search online': (['Ctrl+E'],
            _('Search online for word')),

        'Table of Contents': (['Ctrl+T'],
            _('Show/hide the Table of Contents')),

        'Lookup word': (['Ctrl+L'],
            _('Lookup word in dictionary')),

        'Next occurrence': (['Ctrl+S'],
            _('Go to next occurrence of selected word')),

        'Bookmark': (['Ctrl+B'],
                     _('Bookmark the current location')),

        'Reload': (['Ctrl+R', 'F5'],
                     _('Reload the current book')),

        'Print': (['Ctrl+P'],
                     _('Print the current book')),
}
