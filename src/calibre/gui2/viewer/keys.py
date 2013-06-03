#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


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

}
