#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

from threading import Thread
from future_builtins import map
from operator import itemgetter
from functools import partial
from collections import defaultdict

import regex
from PyQt5.Qt import (
    QSize, QStackedLayout, QLabel, QVBoxLayout, Qt, QWidget, pyqtSignal,
    QAbstractTableModel, QTableView, QSortFilterProxyModel, QIcon, QListWidget,
    QListWidgetItem, QLineEdit, QStackedWidget, QSplitter, QByteArray, QPixmap,
    QStyledItemDelegate, QModelIndex, QRect, QStyle, QPalette, QTimer, QMenu)

from calibre import human_readable, fit_image
from calibre.ebooks.oeb.polish.report import gather_data
from calibre.gui2 import error_dialog, question_dialog
from calibre.gui2.tweak_book import current_container, tprefs, dictionaries
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.utils.icu import primary_contains, numeric_sort_key, character_name_from_code
from calibre.utils.localization import calibre_langcode_to_name, canonicalize_lang

# Utils {{{

def read_state(name, default=None):
    data = tprefs.get('reports-ui-state')
    if data is None:
        tprefs['reports-ui-state'] = data = {}
    return data.get(name, default)

def save_state(name, val):
    data = tprefs.get('reports-ui-state')
    if isinstance(val, QByteArray):
        val = bytearray(val)
    if data is None:
        tprefs['reports-ui-state'] = data = {}
    data[name] = val

class ProxyModel(QSortFilterProxyModel):

    def __init__(self, parent=None):
        QSortFilterProxyModel.__init__(self, parent)
        self._filter_text = None

    def filter_text(self, text):
        self._filter_text = text
        self.setFilterFixedString(text)

    def filterAcceptsRow(self, row, parent):
        if not self._filter_text:
            return True
        sm = self.sourceModel()
        for item in (sm.data(sm.index(row, c, parent)) or '' for c in xrange(sm.columnCount())):
            if item and primary_contains(self._filter_text, item):
                return True
        return False

    def lessThan(self, left, right):
        sm = self.sourceModel()
        return sm.sort_key(left.row(), left.column()) < sm.sort_key(right.row(), right.column())

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Vertical and role == Qt.DisplayRole:
            return section + 1
        return QSortFilterProxyModel.headerData(self, section, orientation, role)

class FileCollection(QAbstractTableModel):

    COLUMN_HEADERS = ()

    def __init__(self, parent=None):
        self.files = self.sort_keys = ()
        self.total_size = 0
        QAbstractTableModel.__init__(self, parent)

    def columnCount(self, parent=None):
        return len(self.COLUMN_HEADERS)

    def rowCount(self, parent=None):
        return len(self.files)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            try:
                return self.COLUMN_HEADERS[section]
            except IndexError:
                pass
        return QAbstractTableModel.headerData(self, section, orientation, role)

    def sort_key(self, row, col):
        try:
            return self.sort_keys[row][col]
        except IndexError:
            pass

    def location(self, index):
        try:
            return self.files[index.row()].name
        except IndexError:
            pass

class FilesView(QTableView):

    double_clicked = pyqtSignal(object)
    delete_requested = pyqtSignal(object, object)
    DELETE_POSSIBLE = True

    def __init__(self, model, parent=None):
        QTableView.__init__(self, parent)
        self.setSelectionBehavior(self.SelectRows), self.setSelectionMode(self.ExtendedSelection)
        self.setSortingEnabled(True)
        self.proxy = p = ProxyModel(self)
        p.setSourceModel(model)
        self.setModel(p)
        self.doubleClicked.connect(self._double_clicked)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def customize_context_menu(self, menu, selected_locations, current_location):
        pass

    def _double_clicked(self, index):
        index = self.proxy.mapToSource(index)
        if index.isValid():
            self.double_clicked.emit(index)

    def keyPressEvent(self, ev):
        if self.DELETE_POSSIBLE and ev.key() == Qt.Key_Delete:
            self.delete_selected()
            ev.accept()
            return
        return QTableView.keyPressEvent(self, ev)

    @property
    def selected_locations(self):
        return filter(None, (self.proxy.sourceModel().location(self.proxy.mapToSource(index)) for index in self.selectionModel().selectedIndexes()))

    @property
    def current_location(self):
        index = self.selectionModel().currentIndex()
        return self.proxy.sourceModel().location(self.proxy.mapToSource(index))

    def delete_selected(self):
        if self.DELETE_POSSIBLE:
            locations = self.selected_locations
            if locations:
                names = frozenset(locations)
                spine_names = {n for n, l in current_container().spine_names}
                other_items = names - spine_names
                spine_items = [(name, name in names) for name, is_linear in current_container().spine_names]
                self.delete_requested.emit(spine_items, other_items)

    def show_context_menu(self, pos):
        pos = self.viewport().mapToGlobal(pos)
        locations = self.selected_locations
        m = QMenu(self)
        if locations:
            m.addAction(_('Delete selected files'), self.delete_selected)
        self.customize_context_menu(m, locations, self.current_location)
        if len(m.actions()) > 0:
            m.exec_(pos)
# }}}

# Files {{{

class FilesModel(FileCollection):

    COLUMN_HEADERS = (_('Folder'), _('Name'), _('Size (KB)'), _('Type'))
    CATEGORY_NAMES = {
        'image':_('Image'),
        'text': _('Text'),
        'font': _('Font'),
        'style': _('Style'),
        'opf': _('Metadata'),
        'toc': _('Table of Contents'),
    }

    def __init__(self, parent=None):
        FileCollection.__init__(self, parent)
        self.images_size = self.fonts_size = 0

    def __call__(self, data):
        self.beginResetModel()
        self.files = data['files']
        self.total_size = sum(map(itemgetter(3), self.files))
        self.images_size = sum(map(itemgetter(3), (f for f in self.files if f.category == 'image')))
        self.fonts_size = sum(map(itemgetter(3), (f for f in self.files if f.category == 'font')))
        psk = numeric_sort_key
        self.sort_keys = tuple((psk(entry.dir), psk(entry.basename), entry.size, psk(self.CATEGORY_NAMES.get(entry.category, '')))
                               for entry in self.files)
        self.endResetModel()

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            col = index.column()
            try:
                entry = self.files[index.row()]
            except IndexError:
                return None
            if col == 0:
                return entry.dir
            if col == 1:
                return entry.basename
            if col == 2:
                sz = entry.size / 1024.
                return ('%.2f' % sz if int(sz) != sz else type('')(sz))
            if col == 3:
                return self.CATEGORY_NAMES.get(entry.category)

class FilesWidget(QWidget):

    edit_requested = pyqtSignal(object)
    delete_requested = pyqtSignal(object, object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)

        self.filter_edit = e = QLineEdit(self)
        l.addWidget(e)
        e.setPlaceholderText(_('Filter'))
        self.model = m = FilesModel(self)
        self.files = f = FilesView(m, self)
        f.delete_requested.connect(self.delete_requested)
        f.double_clicked.connect(self.double_clicked)
        e.textChanged.connect(f.proxy.filter_text)
        l.addWidget(f)

        self.summary = s = QLabel(self)
        l.addWidget(s)
        s.setText('\xa0')
        try:
            self.files.horizontalHeader().restoreState(read_state('all-files-table'))
        except TypeError:
            self.files.sortByColumn(1, Qt.AscendingOrder)

    def __call__(self, data):
        self.model(data)
        self.filter_edit.clear()
        m = self.model
        self.summary.setText(_('Total uncompressed size of all files: {0} :: Images: {1} :: Fonts: {2}').format(*map(
            human_readable, (m.total_size, m.images_size, m.fonts_size))))

    def double_clicked(self, index):
        location = self.model.location(index)
        if location is not None:
            self.edit_requested.emit(location)

    def save(self):
        save_state('all-files-table', bytearray(self.files.horizontalHeader().saveState()))

# }}}

class Jump(object):  # {{{

    def __init__(self):
        self.pos_map = defaultdict(lambda : -1)

    def clear(self):
        self.pos_map.clear()

    def __call__(self, key, locations):
        self.pos_map[key] = (self.pos_map[key] + 1) % len(locations)
        loc = locations[self.pos_map[key]]
        from calibre.gui2.tweak_book.boss import get_boss
        boss = get_boss()
        if boss is None:
            return
        name = loc.name
        editor = boss.edit_file_requested(name)
        if editor is None:
            return
        editor = editor.editor
        if loc.line_number is not None:
            block = editor.document().findBlockByNumber(loc.line_number - 1)  # blockNumber() is zero based
            if not block.isValid():
                return
            c = editor.textCursor()
            c.setPosition(block.position(), c.MoveAnchor)
            editor.setTextCursor(c)
            if loc.text_on_line is not None:
                editor.find(regex.compile(regex.escape(loc.text_on_line)))

jump = Jump()  # }}}

# Images {{{

class ImagesDelegate(QStyledItemDelegate):

    MARGIN = 5

    def __init__(self, *args):
        QStyledItemDelegate.__init__(self, *args)
        self.cache = {}

    def sizeHint(self, option, index):
        ans = QStyledItemDelegate.sizeHint(self, option, index)
        entry = index.data(Qt.UserRole)
        if entry is None:
            return ans
        th = self.parent().thumbnail_height
        width, height = min(th, entry.width), min(th, entry.height)
        m = self.MARGIN * 2
        return QSize(max(width + m, ans.width()), height + m + self.MARGIN + ans.height())

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, QModelIndex())
        entry = index.data(Qt.UserRole)
        if entry is None:
            return
        painter.save()
        th = self.parent().thumbnail_height
        k = (th, entry.name)
        pmap = self.cache.get(k)
        if pmap is None:
            pmap = self.cache[k] = self.pixmap(th, entry)
        if pmap.isNull():
            bottom = option.rect.top()
        else:
            m = 2 * self.MARGIN
            x = option.rect.left() + (option.rect.width() - m - pmap.width()) // 2
            painter.drawPixmap(x, option.rect.top() + self.MARGIN, pmap)
            bottom = m + pmap.height() + option.rect.top()
        rect = QRect(option.rect.left(), bottom, option.rect.width(), option.rect.bottom() - bottom)
        if option.state & QStyle.State_Selected:
            painter.setPen(self.parent().palette().color(QPalette.HighlightedText))
        painter.drawText(rect, Qt.AlignHCenter | Qt.AlignVCenter, entry.basename)
        painter.restore()

    def pixmap(self, thumbnail_height, entry):
        pmap = QPixmap(current_container().name_to_abspath(entry.name)) if entry.width > 0 and entry.height > 0 else QPixmap()
        scaled, width, height = fit_image(entry.width, entry.height, thumbnail_height, thumbnail_height)
        if scaled and not pmap.isNull():
            pmap = pmap.scaled(width, height, transformMode=Qt.SmoothTransformation)
        return pmap


class ImagesModel(FileCollection):

    COLUMN_HEADERS = [_('Image'), _('Size (KB)'), _('Times used'), _('Resolution')]

    def __init__(self, parent=None):
        FileCollection.__init__(self, parent)

    def __call__(self, data):
        self.beginResetModel()
        self.files = data['images']
        self.total_size = sum(map(itemgetter(3), self.files))
        psk = numeric_sort_key
        self.sort_keys = tuple((psk(entry.basename), entry.size, len(entry.usage), (entry.width, entry.height))
                               for entry in self.files)
        self.endResetModel()

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            col = index.column()
            try:
                entry = self.files[index.row()]
            except IndexError:
                return None
            if col == 0:
                return entry.basename
            if col == 1:
                sz = entry.size / 1024.
                return ('%.2f' % sz if int(sz) != sz else type('')(sz))
            if col == 2:
                return type('')(len(entry.usage))
            if col == 3:
                return '%d x %d' % (entry.width, entry.height)
        if role == Qt.UserRole:
            try:
                return self.files[index.row()]
            except IndexError:
                pass


class ImagesWidget(QWidget):

    edit_requested = pyqtSignal(object)
    delete_requested = pyqtSignal(object, object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.thumbnail_height = 64

        self.filter_edit = e = QLineEdit(self)
        l.addWidget(e)
        e.setPlaceholderText(_('Filter'))
        self.model = m = ImagesModel(self)
        self.files = f = FilesView(m, self)
        f.customize_context_menu = self.customize_context_menu
        f.delete_requested.connect(self.delete_requested)
        f.horizontalHeader().sortIndicatorChanged.connect(self.resize_to_contents)
        self.delegate = ImagesDelegate(self)
        f.setItemDelegateForColumn(0, self.delegate)
        f.double_clicked.connect(self.double_clicked)
        e.textChanged.connect(f.proxy.filter_text)
        l.addWidget(f)

        try:
            self.files.horizontalHeader().restoreState(read_state('image-files-table'))
        except TypeError:
            self.files.sortByColumn(0, Qt.AscendingOrder)

    def __call__(self, data):
        self.model(data)
        self.filter_edit.clear()
        self.delegate.cache.clear()
        self.files.resizeRowsToContents()

    def resize_to_contents(self, *args):
        QTimer.singleShot(0, self.files.resizeRowsToContents)

    def double_clicked(self, index):
        entry = index.data(Qt.UserRole)
        if entry is not None:
            jump((id(self), entry.id), entry.usage)

    def customize_context_menu(self, menu, selected_locations, current_location):
        if current_location is not None:
            menu.addAction(_('Edit the image: %s') % current_location, partial(self.edit_requested.emit, current_location))

    def save(self):
        save_state('image-files-table', bytearray(self.files.horizontalHeader().saveState()))
# }}}

# Words {{{

class WordsModel(FileCollection):

    COLUMN_HEADERS = (_('Word'), _('Language'), _('Times used'))
    total_words = 0

    def __call__(self, data):
        self.beginResetModel()
        self.total_words, self.files = data['words']
        self.total_size = len({entry.locale for entry in self.files})
        psk = numeric_sort_key
        lsk_cache = {}
        def locale_sort_key(loc):
            try:
                return lsk_cache[loc]
            except KeyError:
                lsk_cache[loc] = (psk(calibre_langcode_to_name(canonicalize_lang(loc[0]))), psk(loc[1] or ''))
            return lsk_cache[loc]

        self.sort_keys = tuple((psk(entry.word), locale_sort_key(entry.locale), len(entry.usage)) for entry in self.files)
        self.endResetModel()

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            col = index.column()
            try:
                entry = self.files[index.row()]
            except IndexError:
                return None
            if col == 0:
                return entry.word
            if col == 1:
                ans = calibre_langcode_to_name(canonicalize_lang(entry.locale.langcode)) or ''
                if entry.locale.countrycode:
                    ans += ' (%s)' % entry.locale.countrycode
                return ans
            if col == 2:
                return type('')(len(entry.usage))
        if role == Qt.UserRole:
            try:
                return self.files[index.row()]
            except IndexError:
                pass

    def location(self, index):
        return None

class WordsWidget(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)

        self.filter_edit = e = QLineEdit(self)
        l.addWidget(e)
        e.setPlaceholderText(_('Filter'))
        self.model = m = WordsModel(self)
        self.words = f = FilesView(m, self)
        f.DELETE_POSSIBLE = False
        f.double_clicked.connect(self.double_clicked)
        e.textChanged.connect(f.proxy.filter_text)
        l.addWidget(f)

        self.summary = la = QLabel('\xa0')
        l.addWidget(la)

        try:
            self.words.horizontalHeader().restoreState(read_state('words-table'))
        except TypeError:
            self.words.sortByColumn(0, Qt.AscendingOrder)

    def __call__(self, data):
        self.model(data)
        self.filter_edit.clear()
        self.summary.setText(_('Words: {2} :: Unique Words: :: {0} Languages: {1}').format(
            self.model.rowCount(), self.model.total_size, self.model.total_words))

    def double_clicked(self, index):
        entry = index.data(Qt.UserRole)
        if entry is not None:
            from calibre.gui2.tweak_book.boss import get_boss
            boss = get_boss()
            if boss is not None:
                boss.find_word((entry.word, entry.locale), entry.usage)

    def save(self):
        save_state('words-table', bytearray(self.words.horizontalHeader().saveState()))
# }}}

# Characters {{{

class CharsModel(FileCollection):

    COLUMN_HEADERS = (_('Character'), _('Name'), _('Codepoint'), _('Times used'))
    total_words = 0

    def __call__(self, data):
        self.beginResetModel()
        self.files = data['chars']
        psk = numeric_sort_key
        self.sort_keys = tuple((psk(entry.char), None, entry.codepoint, len(entry.usage)) for entry in self.files)
        self.endResetModel()

    def data(self, index, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            col = index.column()
            try:
                entry = self.files[index.row()]
            except IndexError:
                return None
            if col == 0:
                return entry.char
            if col == 1:
                return {0xa:'LINE FEED', 0xd:'CARRIAGE RETURN'}.get(entry.codepoint, character_name_from_code(entry.codepoint))
            if col == 2:
                return ('U+%04X' if entry.codepoint < 0x10000 else 'U+%06X') % entry.codepoint
            if col == 3:
                return type('')(entry.count)
        if role == Qt.UserRole:
            try:
                return self.files[index.row()]
            except IndexError:
                pass

    def location(self, index):
        return None

class CharsWidget(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)

        self.filter_edit = e = QLineEdit(self)
        l.addWidget(e)
        e.setPlaceholderText(_('Filter'))
        self.model = m = CharsModel(self)
        self.chars = f = FilesView(m, self)
        f.DELETE_POSSIBLE = False
        f.double_clicked.connect(self.double_clicked)
        e.textChanged.connect(f.proxy.filter_text)
        l.addWidget(f)

        try:
            self.chars.horizontalHeader().restoreState(read_state('chars-table'))
        except TypeError:
            self.chars.sortByColumn(0, Qt.AscendingOrder)

    def __call__(self, data):
        self.model(data)
        self.filter_edit.clear()

    def double_clicked(self, index):
        entry = index.data(Qt.UserRole)
        if entry is not None:
            self.find_next_location(entry)

    def save(self):
        save_state('chars-table', bytearray(self.chars.horizontalHeader().saveState()))

    def find_next_location(self, entry):
        from calibre.gui2.tweak_book.boss import get_boss
        boss = get_boss()
        if boss is None:
            return
        files = entry.usage
        current_editor_name = boss.currently_editing
        if current_editor_name not in files:
            current_editor_name = None
        else:
            idx = files.index(current_editor_name)
            before, after = files[:idx], files[idx+1:]
            files = [current_editor_name] + after + before + [current_editor_name]

        pat = regex.compile(regex.escape(entry.char))
        for file_name in files:
            from_cursor = False
            if file_name == current_editor_name:
                from_cursor = True
                current_editor_name = None
            ed = boss.edit_file_requested(file_name)
            if ed.editor.find(pat, complete=not from_cursor):
                boss.show_editor(file_name)
                return True
        return False

# }}}

# Wrapper UI {{{
class ReportsWidget(QWidget):

    edit_requested = pyqtSignal(object)
    delete_requested = pyqtSignal(object, object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = QVBoxLayout(self)
        self.splitter = l = QSplitter(self)
        l.setChildrenCollapsible(False)
        self.layout().addWidget(l)
        self.reports = r = QListWidget(self)
        l.addWidget(r)
        self.stack = s = QStackedWidget(self)
        l.addWidget(s)
        r.currentRowChanged.connect(s.setCurrentIndex)

        self.files = f = FilesWidget(self)
        f.edit_requested.connect(self.edit_requested)
        f.delete_requested.connect(self.delete_requested)
        s.addWidget(f)
        QListWidgetItem(_('Files'), r)

        self.words = w = WordsWidget(self)
        s.addWidget(w)
        QListWidgetItem(_('Words'), r)

        self.images = i = ImagesWidget(self)
        i.edit_requested.connect(self.edit_requested)
        i.delete_requested.connect(self.delete_requested)
        s.addWidget(i)
        QListWidgetItem(_('Images'), r)

        self.chars = c = CharsWidget(self)
        s.addWidget(c)
        QListWidgetItem(_('Characters'), r)

        self.splitter.setStretchFactor(1, 500)
        try:
            self.splitter.restoreState(read_state('splitter-state'))
        except TypeError:
            pass
        current_page = read_state('report-page')
        if current_page is not None:
            self.reports.setCurrentRow(current_page)

    def __call__(self, data):
        jump.clear()
        for i in xrange(self.stack.count()):
            self.stack.widget(i)(data)

    def save(self):
        save_state('splitter-state', bytearray(self.splitter.saveState()))
        save_state('report-page', self.reports.currentRow())
        for i in xrange(self.stack.count()):
            self.stack.widget(i).save()

class Reports(Dialog):

    data_gathered = pyqtSignal(object, object)
    edit_requested = pyqtSignal(object)
    refresh_starting = pyqtSignal()
    delete_requested = pyqtSignal(object, object)

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Reports'), 'reports-dialog', parent=parent)
        self.data_gathered.connect(self.display_data, type=Qt.QueuedConnection)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.wait_stack = s = QStackedLayout()
        l.addLayout(s)
        l.addWidget(self.bb)
        self.reports = r = ReportsWidget(self)
        r.edit_requested.connect(self.edit_requested)
        r.delete_requested.connect(self.confirm_delete)

        self.pw = pw = QWidget(self)
        s.addWidget(pw), s.addWidget(r)
        pw.l = l = QVBoxLayout(pw)
        self.pi = pi = ProgressIndicator(self, 256)
        l.addStretch(1), l.addWidget(pi, alignment=Qt.AlignHCenter), l.addSpacing(10)
        pw.la = la = QLabel(_('Gathering data, please wait...'))
        la.setStyleSheet('QLabel { font-size: 30pt; font-weight: bold }')
        l.addWidget(la, alignment=Qt.AlignHCenter), l.addStretch(1)

        self.bb.setStandardButtons(self.bb.Close)
        self.refresh_button = b = self.bb.addButton(_('&Refresh'), self.bb.ActionRole)
        b.clicked.connect(self.refresh)
        b.setIcon(QIcon(I('view-refresh')))

    def sizeHint(self):
        return QSize(950, 600)

    def confirm_delete(self, spine_items, other_names):
        spine_names = {name for name, remove in spine_items if remove}
        if not question_dialog(self, _('Are you sure?'), _(
                'Are you sure you want to delete the selected files?'), det_msg='\n'.join(spine_names | other_names)):
            return
        self.delete_requested.emit(spine_items, other_names)
        QTimer.singleShot(10, self.refresh)

    def refresh(self):
        self.wait_stack.setCurrentIndex(0)
        self.setCursor(Qt.BusyCursor)
        self.pi.startAnimation()
        self.refresh_starting.emit()
        t = Thread(name='GatherReportData', target=self.gather_data)
        t.daemon = True
        t.start()

    def gather_data(self):
        try:
            ok, data = True, gather_data(current_container(), dictionaries.default_locale)
        except Exception:
            import traceback
            traceback.print_exc()
            ok, data = False, traceback.format_exc()
        self.data_gathered.emit(ok, data)

    def display_data(self, ok, data):
        self.wait_stack.setCurrentIndex(1)
        self.unsetCursor()
        self.pi.stopAnimation()
        if not ok:
            return error_dialog(self, _('Failed to gather data'), _(
                'Failed to gather data for the report. Click "Show details" for more'
                ' information.'), det_msg=data, show=True)
        self.reports(data)

    def accept(self):
        with tprefs:
            self.reports.save()
        Dialog.accept(self)

    def reject(self):
        self.reports.save()
        Dialog.reject(self)
# }}}

if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    from calibre.gui2.tweak_book import set_current_container
    from calibre.gui2.tweak_book.boss import get_container
    set_current_container(get_container('/t/demo.epub'))
    d = Reports()
    d.refresh()
    d.exec_()
    del d, app
