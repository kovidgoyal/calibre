#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, softwaregames1

from qt.core import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialogButtonBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QRadioButton,
    QSize,
    Qt,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from calibre.db.duplicates import find_duplicates, identifier_types
from calibre.gui2 import gprefs
from calibre.gui2.widgets2 import Dialog
from calibre.utils.date import format_date
from calibre.utils.localization import _, ngettext

TITLE, AUTHORS, FORMATS, DATE = range(4)


class FindDuplicates(Dialog):
    """
    Find groups of duplicate books in the library. ``shown_ids`` are the books
    currently shown in the book list, used to optionally restrict the search.
    """

    def __init__(self, db, shown_ids=(), parent=None):
        self.db = db
        self.shown_ids = frozenset(shown_ids)
        self.all_ids = db.all_book_ids()
        self.identifier_types = identifier_types(db)
        self.groups = []
        Dialog.__init__(
            self,
            _('Find duplicate books'),
            'find-duplicate-books',
            parent=parent,
            default_buttons=QDialogButtonBox.StandardButton.Close,
        )

    def sizeHint(self):
        return QSize(900, 600)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        la = QLabel(
            _(
                'Find books that are in the library more than once. The duplicates are then shown in the book list,'
                ' marked by group, so that they can be compared and merged with the <i>Merge book records</i> action'
                ' or deleted. Showing them replaces any books that are currently marked.'
            )
        )
        la.setWordWrap(True)
        l.addWidget(la)

        g = QGroupBox(_('Books are duplicates when they have'), self)
        gl = QGridLayout(g)
        self.match_group = bg = QButtonGroup(self)
        self.by_title = r = QRadioButton(_('The same &title and authors'), g)
        r.setToolTip(_('Titles are compared ignoring case, punctuation and leading articles such as "The", as when adding books'))
        bg.addButton(r)
        gl.addWidget(r, 0, 0, 1, 2)
        self.different_languages = cb = QCheckBox(_('Books in different &languages are not duplicates'), g)
        cb.setChecked(gprefs.get('find_duplicates_different_languages', True))
        gl.addWidget(cb, 1, 0, 1, 2)
        gl.setColumnMinimumWidth(0, 0)
        self.by_identifier = r = QRadioButton(_('The same &identifier:'), g)
        bg.addButton(r)
        gl.addWidget(r, 2, 0)
        self.identifier = c = QComboBox(g)
        c.addItems(self.identifier_types)
        saved = gprefs.get('find_duplicates_identifier', 'isbn')
        if saved in self.identifier_types:
            c.setCurrentText(saved)
        gl.addWidget(c, 2, 1)
        gl.setColumnStretch(2, 10)
        if self.identifier_types and gprefs.get('find_duplicates_by_identifier', False):
            self.by_identifier.setChecked(True)
        else:
            self.by_title.setChecked(True)
        if not self.identifier_types:
            self.by_identifier.setEnabled(False)
            self.by_identifier.setToolTip(_('No books in the library have identifiers'))
        self.only_shown = cb = QCheckBox(_('Only look at the books currently shown in the book list'), g)
        cb.setVisible(0 < len(self.shown_ids) < len(self.all_ids))
        gl.addWidget(cb, 3, 0, 1, 3)
        l.addWidget(g)

        self.summary = QLabel(self)
        l.addWidget(self.summary)
        self.results = t = QTreeWidget(self)
        t.setHeaderLabels([_('Title'), _('Authors'), _('Formats'), _('Date')])
        t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        t.setRootIsDecorated(True)
        t.setAlternatingRowColors(True)
        t.itemDoubleClicked.connect(self.accept)
        l.addWidget(t, stretch=10)

        b = self.bb.addButton(_('&Show in book list'), QDialogButtonBox.ButtonRole.AcceptRole)
        assert b is not None
        self.show_button = b
        b.setToolTip(_('Show the duplicate books in the book list, with the selected group selected'))
        b.setDefault(True)
        l.addWidget(self.bb)

        for w in (self.by_title, self.by_identifier, self.different_languages, self.only_shown):
            w.toggled.connect(self.refresh)
        self.identifier.currentIndexChanged.connect(self.refresh)
        self.refresh()

    def refresh(self):
        by_identifier = self.by_identifier.isChecked()
        self.different_languages.setEnabled(not by_identifier)
        self.identifier.setEnabled(by_identifier)
        book_ids = self.shown_ids if self.only_shown.isVisible() and self.only_shown.isChecked() else None
        self.groups = find_duplicates(
            self.db,
            book_ids=book_ids,
            identifier=self.identifier.currentText() if by_identifier else None,
            different_languages_are_different=self.different_languages.isChecked(),
        )
        self.populate()

    def populate(self):
        t = self.results
        t.clear()
        db = self.db
        num_books = sum(map(len, self.groups))
        if self.groups:
            self.summary.setText(
                ngettext('One group of duplicates', '{} groups of duplicates', len(self.groups)).format(len(self.groups))
                + ', '
                + ngettext('one book', '{} books', num_books).format(num_books)
            )
        else:
            self.summary.setText(_('No duplicate books found'))
        for group in self.groups:
            first = group[0]
            gi = QTreeWidgetItem(t, [db.field_for('title', first), ' & '.join(db.field_for('authors', first)), '', ''])
            gi.setData(TITLE, Qt.ItemDataRole.UserRole, group)
            f = gi.font(TITLE)
            f.setBold(True)
            for col in range(4):
                gi.setFont(col, f)
            gi.setText(FORMATS, ngettext('One book', '{} books', len(group)).format(len(group)))
            for book_id in group:
                bi = QTreeWidgetItem(
                    gi,
                    [
                        db.field_for('title', book_id),
                        ' & '.join(db.field_for('authors', book_id)),
                        ', '.join(sorted(db.formats(book_id))),
                        format_date(db.field_for('timestamp', book_id), 'dd MMM yyyy'),
                    ],
                )
                bi.setData(TITLE, Qt.ItemDataRole.UserRole, (book_id,))
            gi.setExpanded(True)
        for col in range(4):
            t.resizeColumnToContents(col)
        t.setColumnWidth(TITLE, min(t.columnWidth(TITLE), 350))
        t.setColumnWidth(AUTHORS, min(t.columnWidth(AUTHORS), 250))
        if self.groups:
            t.setCurrentItem(t.topLevelItem(0))
        self.show_button.setEnabled(bool(self.groups))

    @property
    def selected_book_ids(self):
        # All the books in the group of the current item
        item = self.results.currentItem()
        if item is None:
            return ()
        if (parent := item.parent()) is not None:
            item = parent
        return item.data(TITLE, Qt.ItemDataRole.UserRole) or ()

    def accept(self):
        gprefs.set('find_duplicates_by_identifier', self.by_identifier.isChecked())
        gprefs.set('find_duplicates_different_languages', self.different_languages.isChecked())
        if self.identifier.currentText():
            gprefs.set('find_duplicates_identifier', self.identifier.currentText())
        Dialog.accept(self)
