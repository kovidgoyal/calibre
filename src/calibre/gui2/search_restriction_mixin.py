'''
Created on 10 Jun 2010

@author: charles
'''

from PyQt4.Qt import Qt

class SearchRestrictionMixin(object):

    def __init__(self):
        self.search_restriction.initialize(help_text=_('Restrict to'))
        self.search_restriction.activated[int].connect(self.apply_search_restriction)
        self.library_view.model().count_changed_signal.connect(self.set_number_of_books_shown)
        self.search_restriction.setSizeAdjustPolicy(
                    self.search_restriction.AdjustToMinimumContentsLengthWithIcon)
        self.search_restriction.setMinimumContentsLength(10)
        self.search_restriction.setStatusTip(self.search_restriction.toolTip())
        self.search_count.setText(_("(all books)"))
        self.search_restriction_tooltip = \
            _('Books display will be restricted to those matching a '
              'selected saved search')
        self.search_restriction.setToolTip(self.search_restriction_tooltip)

    def apply_named_search_restriction(self, name):
        if not name:
            r = 0
        else:
            r = self.search_restriction.findText(name)
            if r < 0:
                r = 0
        if r != self.search_restriction.currentIndex():
            self.search_restriction.setCurrentIndex(r)
            self.apply_search_restriction(r)

    def apply_text_search_restriction(self, search):
        search = unicode(search)
        if not search:
            self.search_restriction.setCurrentIndex(0)
        else:
            s = '*' + search
            if self.search_restriction.count() > 1:
                txt = unicode(self.search_restriction.itemText(2))
                if txt.startswith('*'):
                    self.search_restriction.setItemText(2, s)
                else:
                    self.search_restriction.insertItem(2, s)
            else:
                self.search_restriction.insertItem(2, s)
            self.search_restriction.setCurrentIndex(2)
            self.search_restriction.setToolTip('<p>' +
                    self.search_restriction_tooltip +
                     _(' or the search ') + "'" + search + "'</p>")
            self._apply_search_restriction(search)

    def apply_search_restriction(self, i):
        if i == 1:
            self.apply_text_search_restriction(unicode(self.search.currentText()))
        elif i == 2 and unicode(self.search_restriction.currentText()).startswith('*'):
            self.apply_text_search_restriction(
                                unicode(self.search_restriction.currentText())[1:])
        else:
            r = unicode(self.search_restriction.currentText())
            if r is not None and r != '':
                restriction = 'search:"%s"'%(r)
            else:
                restriction = ''
            self._apply_search_restriction(restriction)

    def _apply_search_restriction(self, restriction):
        self.saved_search.clear()
        # The order below is important. Set the restriction, force a '' search
        # to apply it, reset the tag browser to take it into account, then set
        # the book count.
        self.library_view.model().db.data.set_search_restriction(restriction)
        self.search.clear(emit_search=True)
        self.tags_view.set_search_restriction(restriction)
        self.set_number_of_books_shown()
        self.current_view().setFocus(Qt.OtherFocusReason)

    def set_number_of_books_shown(self):
        db = self.library_view.model().db
        if self.current_view() == self.library_view and db is not None and \
                                            db.data.search_restriction_applied():
            rows = self.current_view().row_count()
            rbc = max(rows, db.data.get_search_restriction_book_count())
            t = _("({0} of {1})").format(rows, rbc)
            self.search_count.setStyleSheet \
                   ('QLabel { border-radius: 8px; background-color: yellow; }')
        else: # No restriction or not library view
            if not self.search.in_a_search():
                t = _("(all books)")
            else:
                t = _("({0} of all)").format(self.current_view().row_count())
            self.search_count.setStyleSheet(
                    'QLabel { background-color: transparent; }')
        self.search_count.setText(t)
