'''
Created on 10 Jun 2010

@author: charles
'''

from PyQt4.Qt import Qt

class SearchRestrictionMixin(object):

    def __init__(self):
        self.search_restriction.initialize(help_text=_('Restrict to'))
        self.search_restriction.activated[int].connect(self.apply_search_restriction)
        self.library_view.model().count_changed_signal.connect(self.restriction_count_changed)
        self.search_restriction.setSizeAdjustPolicy(self.search_restriction.AdjustToMinimumContentsLengthWithIcon)
        self.search_restriction.setMinimumContentsLength(10)
        self.search_restriction.setStatusTip(self.search_restriction.toolTip())
        self.search_count.setText(_("(all books)"))

    '''
    Adding and deleting books while restricted creates a complexity. When added,
    they are displayed regardless of whether they match a search restriction.
    However, if they do not, they are removed at the next search. The counts
    must take this behavior into effect.
    '''

    def restriction_count_changed(self, c):
        self.restriction_count_of_books_in_view += \
                                c - self.restriction_count_of_books_in_library
        self.restriction_count_of_books_in_library = c
        if self.restriction_in_effect:
            self.set_number_of_books_shown()

    def apply_named_search_restriction(self, name):
        if not name:
            r = 0
        else:
            r = self.search_restriction.findText(name)
            if r < 0:
                r = 0
        self.search_restriction.setCurrentIndex(r)
        self.apply_search_restriction(r)

    def apply_search_restriction(self, i):
        r = unicode(self.search_restriction.currentText())
        if r is not None and r != '':
            self.restriction_in_effect = True
            restriction = 'search:"%s"'%(r)
        else:
            self.restriction_in_effect = False
            restriction = ''
        self.restriction_count_of_books_in_view = \
                    self.library_view.model().set_search_restriction(restriction)
        self.search.clear()
        self.saved_search.clear()
        self.tags_view.set_search_restriction(restriction)
        self.set_number_of_books_shown()
        self.current_view().setFocus(Qt.OtherFocusReason)

    def set_number_of_books_shown(self):
        if self.current_view() == self.library_view and self.restriction_in_effect:
            t = _("({0} of {1})").format(self.current_view().row_count(),
                                         self.restriction_count_of_books_in_view)
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
