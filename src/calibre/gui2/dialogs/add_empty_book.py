#!/usr/bin/env python2
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__license__   = 'GPL v3'


from PyQt5.Qt import (
    QDialog, QGridLayout, QLabel, QDialogButtonBox,  QApplication, QSpinBox,
    QToolButton, QIcon, QLineEdit, QComboBox, QCheckBox)
from calibre.ebooks.metadata import string_to_authors
from calibre.gui2.complete2 import EditWithComplete
from calibre.utils.config import tweaks
from calibre.gui2 import gprefs


class AddEmptyBookDialog(QDialog):

    def __init__(self, parent, db, author, series=None, title=None, dup_title=None):
        QDialog.__init__(self, parent)
        self.db = db

        self.setWindowTitle(_('How many empty books?'))

        self._layout = QGridLayout(self)
        self.setLayout(self._layout)

        self.qty_label = QLabel(_('How many empty books should be added?'))
        self._layout.addWidget(self.qty_label, 0, 0, 1, 2)

        self.qty_spinbox = QSpinBox(self)
        self.qty_spinbox.setRange(1, 10000)
        self.qty_spinbox.setValue(1)
        self._layout.addWidget(self.qty_spinbox, 1, 0, 1, 2)

        self.author_label = QLabel(_('Set the author of the new books to:'))
        self._layout.addWidget(self.author_label, 2, 0, 1, 2)

        self.authors_combo = EditWithComplete(self)
        self.authors_combo.setSizeAdjustPolicy(
                self.authors_combo.AdjustToMinimumContentsLengthWithIcon)
        self.authors_combo.setEditable(True)
        self._layout.addWidget(self.authors_combo, 3, 0, 1, 1)
        self.initialize_authors(db, author)

        self.clear_button = QToolButton(self)
        self.clear_button.setIcon(QIcon(I('trash.png')))
        self.clear_button.setToolTip(_('Reset author to Unknown'))
        self.clear_button.clicked.connect(self.reset_author)
        self._layout.addWidget(self.clear_button, 3, 1, 1, 1)

        self.series_label = QLabel(_('Set the series of the new books to:'))
        self._layout.addWidget(self.series_label, 4, 0, 1, 2)

        self.series_combo = EditWithComplete(self)
        self.series_combo.setSizeAdjustPolicy(
                self.authors_combo.AdjustToMinimumContentsLengthWithIcon)
        self.series_combo.setEditable(True)
        self._layout.addWidget(self.series_combo, 5, 0, 1, 1)
        self.initialize_series(db, series)

        self.sclear_button = QToolButton(self)
        self.sclear_button.setIcon(QIcon(I('trash.png')))
        self.sclear_button.setToolTip(_('Reset series'))
        self.sclear_button.clicked.connect(self.reset_series)
        self._layout.addWidget(self.sclear_button, 5, 1, 1, 1)

        self.title_label = QLabel(_('Set the title of the new books to:'))
        self._layout.addWidget(self.title_label, 6, 0, 1, 2)

        self.title_edit = QLineEdit(self)
        self.title_edit.setText(title or '')
        self._layout.addWidget(self.title_edit, 7, 0, 1, 1)

        self.tclear_button = QToolButton(self)
        self.tclear_button.setIcon(QIcon(I('trash.png')))
        self.tclear_button.setToolTip(_('Reset title'))
        self.tclear_button.clicked.connect(self.title_edit.clear)
        self._layout.addWidget(self.tclear_button, 7, 1, 1, 1)

        self.format_label = QLabel(_('Also create an empty e-book in format:'))
        self._layout.addWidget(self.format_label, 8, 0, 1, 2)
        c = self.format_value = QComboBox(self)
        from calibre.ebooks.oeb.polish.create import valid_empty_formats
        possible_formats = [''] + sorted(x.upper() for x in valid_empty_formats)
        c.addItems(possible_formats)
        c.setToolTip(_('Also create an empty book format file that you can subsequently edit'))
        if gprefs.get('create_empty_epub_file', False):
            # Migration of the check box
            gprefs.set('create_empty_format_file', 'epub')
            del gprefs['create_empty_epub_file']
        use_format = gprefs.get('create_empty_format_file', '').upper()
        try:
            c.setCurrentIndex(possible_formats.index(use_format))
        except Exception:
            pass
        self._layout.addWidget(c, 9, 0, 1, 1)

        self.copy_formats = cf = QCheckBox(_('Also copy book &formats when duplicating a book'), self)
        cf.setToolTip(_(
            'Also copy all e-book files into the newly created duplicate'
            ' books.'))
        cf.setChecked(gprefs.get('create_empty_copy_dup_formats', False))
        self._layout.addWidget(cf, 10, 0, 1, -1)

        button_box = self.bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self._layout.addWidget(button_box, 11, 0, 1, -1)
        if dup_title:
            self.dup_button = b = button_box.addButton(_('&Duplicate current book'), button_box.ActionRole)
            b.clicked.connect(self.do_duplicate_book)
            b.setIcon(QIcon(I('edit-copy.png')))
            b.setToolTip(_(
                'Make the new empty book records exact duplicates\n'
                'of the current book "%s", with all metadata identical'
            ) % dup_title)
        self.resize(self.sizeHint())
        self.duplicate_current_book = False

    def do_duplicate_book(self):
        self.duplicate_current_book = True
        self.accept()

    def accept(self):
        self.save_settings()
        return QDialog.accept(self)

    def save_settings(self):
        gprefs['create_empty_format_file'] = self.format_value.currentText().lower()
        gprefs['create_empty_copy_dup_formats'] = self.copy_formats.isChecked()

    def reject(self):
        self.save_settings()
        return QDialog.reject(self)

    def reset_author(self, *args):
        self.authors_combo.setEditText(_('Unknown'))

    def reset_series(self):
        self.series_combo.setEditText('')

    def initialize_authors(self, db, author):
        au = author
        if not au:
            au = _('Unknown')
        self.authors_combo.show_initial_value(au.replace('|', ','))

        self.authors_combo.set_separator('&')
        self.authors_combo.set_space_before_sep(True)
        self.authors_combo.set_add_separator(tweaks['authors_completer_append_separator'])
        self.authors_combo.update_items_cache(db.all_author_names())

    def initialize_series(self, db, series):
        self.series_combo.show_initial_value(series or '')
        self.series_combo.update_items_cache(db.all_series_names())
        self.series_combo.set_separator(None)

    @property
    def qty_to_add(self):
        return self.qty_spinbox.value()

    @property
    def selected_authors(self):
        return string_to_authors(unicode(self.authors_combo.text()))

    @property
    def selected_series(self):
        return unicode(self.series_combo.text())

    @property
    def selected_title(self):
        return self.title_edit.text().strip()


if __name__ == '__main__':
    from calibre.library import db
    db = db()
    app = QApplication([])
    d = AddEmptyBookDialog(None, db, 'Test Author')
    d.exec_()
