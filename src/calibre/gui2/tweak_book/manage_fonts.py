#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, textwrap
from io import BytesIO

from qt.core import (
    QSplitter, QVBoxLayout, QTableView, QWidget, QLabel, QAbstractTableModel,
    Qt, QTimer, QPushButton, pyqtSignal, QFormLayout, QLineEdit, QIcon, QSize,
    QHBoxLayout, QTextEdit, QApplication, QMessageBox, QAbstractItemView, QDialog, QDialogButtonBox)

from calibre.ebooks.oeb.polish.container import get_container
from calibre.ebooks.oeb.polish.fonts import font_family_data, change_font
from calibre.gui2 import error_dialog, info_dialog
from calibre.gui2.tweak_book import current_container, set_current_container
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.gui2.widgets import BusyCursor
from calibre.utils.icu import primary_sort_key as sort_key
from calibre.utils.fonts.scanner import font_scanner, NoFonts
from calibre.utils.fonts.metadata import FontMetadata, UnsupportedFont
from polyglot.builtins import iteritems


def rule_for_font(font_file, added_name):
    try:
        fm = FontMetadata(font_file).to_dict()
    except UnsupportedFont:
        return
    pp = _('Change this to the relative path to: %s') % added_name
    rule = '''@font-face {{
  src: url({pp});
  font-family: "{ff}";
  font-weight: {w};
  font-style: {sy};
  font-stretch: {st};
  }}'''.format(pp=pp, ff=fm['font-family'], w=fm['font-weight'], sy=fm['font-style'], st=fm['font-stretch'])
    return rule


def show_font_face_rule_for_font_file(file_data, added_name, parent=None):
    rule = rule_for_font(BytesIO(file_data), added_name)
    QApplication.clipboard().setText(rule)
    QMessageBox.information(parent, _('Font file added'), _(
        'The font file <b>{}</b> has been added. The text for the CSS @font-face rule for this file has been copied'
        ' to the clipboard. You should paste it into whichever CSS file you want to add this font to.').format(added_name))


def show_font_face_rule_for_font_files(container, added_names, parent=None):
    rules = []
    for name in sorted(added_names):
        rule = rule_for_font(container.open(name), name)
        if rule:
            rules.append(rule)
    if rules:
        QApplication.clipboard().setText('\n\n'.join(rules))
        QMessageBox.information(parent, _('Font files added'), _(
        'The specified font files have been added. The text for the CSS @font-face rules for these files has been copied'
        ' to the clipboard. You should paste it into whichever CSS file you want to add these fonts to.'))


class EmbeddingData(Dialog):

    def __init__(self, family, faces, parent=None):
        Dialog.__init__(self, _('Font faces for %s') % family, 'editor-embedding-data', parent)
        self.family, self.faces = family, faces
        self.populate_text()

    def sizeHint(self):
        return QSize(600, 500)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.text = t = QTextEdit(self)
        t.setReadOnly(True)
        l.addWidget(t), l.addWidget(self.bb)
        self.bb.clear(), self.bb.setStandardButtons(QDialogButtonBox.StandardButton.Close)

    def populate_text(self):
        text = ['<h2>' + self.windowTitle() + '</h2><ul>']
        for face in self.faces:
            text.append('<li style="margin-bottom:2em">' + '<b>' + face['path'] + '</b>')
            name = face.get('full_name') or face.get('family_name') or face.get('subfamily_name')
            if name:
                text.append('<br>' + _('Name:') + '\xa0<b>' + str(name) + '</b>')
            if 'font-weight' in face:
                text.append('<br>' + 'font-weight:\xa0' + str(face['font-weight']))
            if 'font-style' in face:
                text.append('<br>' + 'font-style:\xa0' + str(face['font-style']))
        self.text.setHtml('\n'.join(text))


class AllFonts(QAbstractTableModel):

    def __init__(self, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self.items = []
        self.font_data = {}
        self.sorted_on = ('name', True)

    def rowCount(self, parent=None):
        return len(self.items)

    def columnCount(self, parent=None):
        return 2

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return _('Font family') if section == 1 else _('Embedded')
        return QAbstractTableModel.headerData(self, section, orientation, role)

    def build(self):
        with BusyCursor():
            self.beginResetModel()
            self.font_data = font_family_data(current_container())
            self.do_sort()
            self.endResetModel()

    def do_sort(self):
        reverse = not self.sorted_on[1]
        self.items = sorted(self.font_data, key=sort_key, reverse=reverse)
        if self.sorted_on[0] != 'name':
            self.items.sort(key=self.font_data.get, reverse=reverse)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            row, col = index.row(), index.column()
            try:
                name = self.items[row]
                embedded = '✓ ' if self.font_data[name] else ''
            except (IndexError, KeyError):
                return
            return name if col == 1 else embedded
        if role == Qt.ItemDataRole.TextAlignmentRole:
            col = index.column()
            if col == 0:
                return int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter)
        if role in (Qt.ItemDataRole.UserRole, Qt.ItemDataRole.UserRole + 1):
            row = index.row()
            try:
                name = self.items[row]
            except (IndexError, KeyError):
                return
            if role == Qt.ItemDataRole.UserRole:
                try:
                    return font_scanner.fonts_for_family(name)
                except NoFonts:
                    return []
            else:
                return name

    def sort(self, col, order=Qt.SortOrder.AscendingOrder):
        sorted_on = (('name' if col == 1 else 'embedded'), order == Qt.SortOrder.AscendingOrder)
        if sorted_on != self.sorted_on:
            self.sorted_on = sorted_on
            self.beginResetModel()
            self.do_sort()
            self.endResetModel()

    def data_for_indices(self, indices):
        ans = {}
        for idx in indices:
            try:
                name = self.items[idx.row()]
                ans[name] = self.font_data[name]
            except (IndexError, KeyError):
                pass
        return ans


class ChangeFontFamily(Dialog):

    def __init__(self, old_family, embedded_families, parent=None):
        self.old_family = old_family
        self.local_families = {icu_lower(f) for f in font_scanner.find_font_families()} | {
            icu_lower(f) for f in embedded_families}
        Dialog.__init__(self, _('Change font'), 'change-font-family', parent=parent)
        self.setMinimumWidth(300)
        self.resize(self.sizeHint())

    def setup_ui(self):
        self.l = l = QFormLayout(self)
        self.setLayout(l)
        self.la = la = QLabel(ngettext(
            'Change the font %s to:', 'Change the fonts %s to:',
            self.old_family.count(',')+1) % self.old_family)
        la.setWordWrap(True)
        l.addRow(la)
        self._family = f = QLineEdit(self)
        l.addRow(_('&New font:'), f)
        f.textChanged.connect(self.updated_family)
        self.embed_status = e = QLabel('\xa0')
        l.addRow(e)
        l.addRow(self.bb)

    @property
    def family(self):
        return str(self._family.text())

    @property
    def normalized_family(self):
        ans = self.family
        try:
            ans = font_scanner.fonts_for_family(ans)[0]['font-family']
        except (NoFonts, IndexError, KeyError):
            pass
        if icu_lower(ans) == 'sansserif':
            ans = 'sans-serif'
        return ans

    def updated_family(self):
        family = self.family
        found = icu_lower(family) in self.local_families
        t = _('The font <i>%s</i> <b>exists</b> on your computer') if found else _(
            'The font <i>%s</i> <b>does not exist</b> on your computer')
        t = (t % family) if family else '\xa0'
        self.embed_status.setText(t)
        self.resize(self.sizeHint())


class ManageFonts(Dialog):

    container_changed = pyqtSignal()
    embed_all_fonts = pyqtSignal()
    subset_all_fonts = pyqtSignal()

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Manage fonts'), 'manage-fonts', parent=parent)

    def setup_ui(self):
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)

        self.bb.clear()
        self.bb.addButton(QDialogButtonBox.StandardButton.Close)
        self.splitter = s = QSplitter(self)
        self.h = h = QHBoxLayout()
        h.setContentsMargins(0, 0, 0, 0)
        self.install_fonts_button = b = QPushButton(_('&Install fonts'), self)
        h.addWidget(b), b.setIcon(QIcon.ic('plus.png'))
        b.setToolTip(textwrap.fill(_('Install fonts from .ttf/.otf files to make them available for embedding')))
        b.clicked.connect(self.install_fonts)
        l.addWidget(s), l.addLayout(h), h.addStretch(10), h.addWidget(self.bb)

        self.fonts_view = fv = QTableView(self)
        fv.doubleClicked.connect(self.show_embedding_data)
        self.model = m = AllFonts(fv)
        fv.horizontalHeader().setStretchLastSection(True)
        fv.setModel(m)
        fv.setSortingEnabled(True)
        fv.setShowGrid(False)
        fv.setAlternatingRowColors(True)
        fv.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        fv.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        fv.horizontalHeader().setSortIndicator(1, Qt.SortOrder.AscendingOrder)
        self.container = c = QWidget()
        l = c.l = QVBoxLayout(c)
        c.setLayout(l)
        s.addWidget(fv), s.addWidget(c)

        self.cb = b = QPushButton(_('&Change selected fonts'))
        b.setIcon(QIcon.ic('wizard.png'))
        b.clicked.connect(self.change_fonts)
        l.addWidget(b)
        self.rb = b = QPushButton(_('&Remove selected fonts'))
        b.clicked.connect(self.remove_fonts)
        b.setIcon(QIcon.ic('trash.png'))
        l.addWidget(b)
        self.eb = b = QPushButton(_('&Embed all fonts'))
        b.setIcon(QIcon.ic('embed-fonts.png'))
        b.clicked.connect(self.embed_fonts)
        l.addWidget(b)
        self.sb = b = QPushButton(_('&Subset all fonts'))
        b.setIcon(QIcon.ic('subset-fonts.png'))
        b.clicked.connect(self.subset_fonts)
        l.addWidget(b)
        self.refresh_button = b = self.bb.addButton(_('&Refresh'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setToolTip(_('Rescan the book for fonts in case you have made changes'))
        b.setIcon(QIcon.ic('view-refresh.png'))
        b.clicked.connect(self.refresh)

        self.la = la = QLabel(
            '<p>' + _(
            ''' All the fonts declared in this book are shown to the left, along with whether they are embedded or not.
            You can remove or replace any selected font and also embed any declared fonts that are not already embedded.''') + '<p>' + _(
            ''' Double click any font family to see if the font is available for embedding on your computer. ''')
        )
        la.setWordWrap(True)
        l.addWidget(la)

        l.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)

    def show_embedding_data(self, index):
        faces = index.data(Qt.ItemDataRole.UserRole)
        family = index.data(Qt.ItemDataRole.UserRole + 1)
        if not faces:
            return error_dialog(self, _('Not found'), _(
                'The font <b>%s</b> was not found on your computer. If you have the font files,'
                ' you can install it using the "Install fonts" button in the lower left corner.'
            ) % family, show=True)
        EmbeddingData(family, faces, self).exec()

    def install_fonts(self):
        from calibre.gui2.font_family_chooser import add_fonts
        families = add_fonts(self)
        if not families:
            return
        font_scanner.do_scan()
        self.refresh()
        info_dialog(self, _('Added fonts'), _('Added font families: %s')%(', '.join(families)), show=True)

    def sizeHint(self):
        return Dialog.sizeHint(self) + QSize(100, 50)

    def display(self):
        if not self.isVisible():
            self.show()
        self.raise_()
        QTimer.singleShot(0, self.model.build)

    def get_selected_data(self):
        ans = self.model.data_for_indices(list(self.fonts_view.selectedIndexes()))
        if not ans:
            error_dialog(self, _('No fonts selected'), _(
                'No fonts selected, you must first select some fonts in the left panel'), show=True)
        return ans

    def change_fonts(self):
        fonts = self.get_selected_data()
        if not fonts:
            return
        d = ChangeFontFamily(', '.join(fonts), {f for f, embedded in iteritems(self.model.font_data) if embedded}, self)
        if d.exec() != QDialog.DialogCode.Accepted:
            return
        changed = False
        new_family = d.normalized_family
        for font in fonts:
            changed |= change_font(current_container(), font, new_family)
        if changed:
            self.model.build()
            self.container_changed.emit()

    def remove_fonts(self):
        fonts = self.get_selected_data()
        if not fonts:
            return
        changed = False
        for font in fonts:
            changed |= change_font(current_container(), font)
        if changed:
            self.model.build()
            self.container_changed.emit()

    def embed_fonts(self):
        self.embed_all_fonts.emit()

    def subset_fonts(self):
        self.subset_all_fonts.emit()

    def refresh(self):
        self.model.build()


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    c = get_container(sys.argv[-1], tweak_mode=True)
    set_current_container(c)
    d = ManageFonts()
    d.exec()
    del app
