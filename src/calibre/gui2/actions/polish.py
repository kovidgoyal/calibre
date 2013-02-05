#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import (QDialog)

from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceAction

SUPPORTED = {'EPUB', 'AZW3'}

class Polish(QDialog):

    def __init__(self, db, book_id_map, parent=None):
        QDialog.__init__(self, parent)

class PolishAction(InterfaceAction):

    name = 'Polish Books'
    action_spec = (_('Polish books'), 'polish.png', None, None)
    dont_add_to = frozenset(['context-menu-device'])
    action_type = 'current'

    def genesis(self):
        self.qaction.triggered.connect(self.polish_books)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)

    def get_books_for_polishing(self):
        rows = [r.row() for r in
                self.gui.library_view.selectionModel().selectedRows()]
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot polish'),
                    _('No books selected'))
            d.exec_()
            return None
        db = self.gui.library_view.model().db
        ans = (db.id(r) for r in rows)
        supported = set(SUPPORTED)
        for x in SUPPORTED:
            supported.add('ORIGINAL_'+x)
        ans = {x:set( (db.formats(x, index_is_id=True) or '').split(',') )
               .intersection(supported) for x in ans}
        ans = {x:fmts for x, fmts in ans.iteritems() if fmts}
        if not ans:
            error_dialog(self.gui, _('Cannot polish'),
                _('Polishing is only supported for books in the %s'
                  ' formats. Convert to one of those formats before polishing.')
                         %_(' or ').join(sorted(SUPPORTED)), show=True)
        for fmts in ans.itervalues():
            for x in SUPPORTED:
                if ('ORIGINAL_'+x) in fmts:
                    fmts.discard(x)
        return ans

    def polish_books(self):
        book_id_map = self.get_books_for_polishing()
        if not book_id_map:
            return
        d = Polish(self.gui.library_view.model().db, book_id_map, parent=self.gui)
        if d.exec_() == d.Accepted:
            pass

