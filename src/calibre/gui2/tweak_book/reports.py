#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import os
import regex
import textwrap
import time
from collections import defaultdict
from contextlib import suppress
from csv import writer as csv_writer
from functools import lru_cache, partial
from io import StringIO
from operator import itemgetter
from qt.core import (
    QAbstractItemModel, QAbstractItemView, QAbstractTableModel, QApplication,
    QByteArray, QComboBox, QDialogButtonBox, QFont, QFontDatabase, QHBoxLayout,
    QIcon, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QModelIndex,
    QPalette, QPixmap, QRadioButton, QRect, QSize, QSortFilterProxyModel, QSplitter,
    QStackedLayout, QStackedWidget, QStyle, QStyledItemDelegate, Qt, QTableView,
    QTextCursor, QTimer, QTreeView, QUrl, QVBoxLayout, QWidget, pyqtSignal
)
from threading import Thread

from calibre import fit_image, human_readable
from calibre.constants import DEBUG
from calibre.ebooks.oeb.polish.report import (
    ClassElement, ClassEntry, ClassFileMatch, CSSEntry, CSSFileMatch, CSSRule,
    LinkLocation, MatchLocation, gather_data
)
from calibre.gui2 import choose_save_file, error_dialog, open_url, question_dialog
from calibre.gui2.progress_indicator import ProgressIndicator
from calibre.gui2.tweak_book import current_container, dictionaries, tprefs
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.gui2.webengine import RestartingWebEngineView
from calibre.utils.icu import numeric_sort_key, primary_contains
from calibre.utils.localization import calibre_langcode_to_name, canonicalize_lang
from calibre.utils.unicode_names import character_name_from_code
from calibre.utils.webengine import secure_webengine
from polyglot.builtins import as_bytes, iteritems

# Utils {{{

ROOT = QModelIndex()


def psk(x):
    return QByteArray(numeric_sort_key(x))


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


SORT_ROLE = Qt.ItemDataRole.UserRole + 1


class ProxyModel(QSortFilterProxyModel):

    def __init__(self, parent=None):
        QSortFilterProxyModel.__init__(self, parent)
        self._filter_text = None
        self.setSortRole(SORT_ROLE)

    def filter_text(self, text):
        self._filter_text = text
        self.setFilterFixedString(text)

    def filterAcceptsRow(self, row, parent):
        if not self._filter_text:
            return True
        sm = self.sourceModel()
        for item in (sm.data(sm.index(row, c, parent)) or '' for c in range(sm.columnCount())):
            if item and primary_contains(self._filter_text, item):
                return True
        return False

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Vertical and role == Qt.ItemDataRole.DisplayRole:
            return section + 1
        return QSortFilterProxyModel.headerData(self, section, orientation, role)


class FileCollection(QAbstractTableModel):

    COLUMN_HEADERS = ()
    alignments = ()

    def __init__(self, parent=None):
        self.files = self.sort_keys = ()
        self.total_size = 0
        QAbstractTableModel.__init__(self, parent)

    def columnCount(self, parent=None):
        return len(self.COLUMN_HEADERS)

    def rowCount(self, parent=None):
        return len(self.files)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal:
            if role == Qt.ItemDataRole.DisplayRole:
                with suppress(IndexError):
                    return self.COLUMN_HEADERS[section]
            elif role == Qt.ItemDataRole.TextAlignmentRole:
                with suppress(IndexError):
                    return int(self.alignments[section])  # https://bugreports.qt.io/browse/PYSIDE-1974
        return QAbstractTableModel.headerData(self, section, orientation, role)

    def location(self, index):
        try:
            return self.files[index.row()].name
        except (IndexError, AttributeError):
            pass


class FilesView(QTableView):

    double_clicked = pyqtSignal(object)
    delete_requested = pyqtSignal(object, object)
    current_changed = pyqtSignal(object, object)
    DELETE_POSSIBLE = True

    def __init__(self, model, parent=None):
        QTableView.__init__(self, parent)
        self.setProperty('highlight_current_item', 150)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setAlternatingRowColors(True)
        self.setSortingEnabled(True)
        self.proxy = p = ProxyModel(self)
        p.setSourceModel(model)
        self.setModel(p)
        self.doubleClicked.connect(self._double_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def currentChanged(self, current, previous):
        QTableView.currentChanged(self, current, previous)
        self.current_changed.emit(*map(self.proxy.mapToSource, (current, previous)))

    def customize_context_menu(self, menu, selected_locations, current_location):
        pass

    def resize_rows(self):
        if self.model().rowCount() > 0:
            num = min(5, self.model().rowCount())
            h = 1000000
            for i in range(num):
                self.resizeRowToContents(i)
                h = min(h, self.rowHeight(i))
            self.verticalHeader().setDefaultSectionSize(h)

    def _double_clicked(self, index):
        index = self.proxy.mapToSource(index)
        if index.isValid():
            self.double_clicked.emit(index)

    def keyPressEvent(self, ev):
        if self.DELETE_POSSIBLE and ev.key() == Qt.Key.Key_Delete:
            self.delete_selected()
            ev.accept()
            return
        return QTableView.keyPressEvent(self, ev)

    @property
    def selected_locations(self):
        return list(filter(None, (self.proxy.sourceModel().location(self.proxy.mapToSource(index)) for index in self.selectionModel().selectedIndexes())))

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
            m.exec(pos)

    def to_csv(self):
        buf = StringIO(newline='')
        w = csv_writer(buf)
        w.writerow(self.proxy.sourceModel().COLUMN_HEADERS)
        cols = self.proxy.columnCount()
        for r in range(self.proxy.rowCount()):
            items = [self.proxy.index(r, c).data(Qt.ItemDataRole.DisplayRole) for c in range(cols)]
            w.writerow(items)
        return buf.getvalue()

    def save_table(self, name):
        save_state(name, bytearray(self.horizontalHeader().saveState()))

    def restore_table(self, name, sort_column=0, sort_order=Qt.SortOrder.AscendingOrder):
        h = self.horizontalHeader()
        try:
            h.restoreState(read_state(name))
        except TypeError:
            self.sortByColumn(sort_column, sort_order)
        h.setSectionsMovable(True), h.setSectionsClickable(True)
        h.setDragEnabled(True), h.setAcceptDrops(True)
        h.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)

# }}}

# Files {{{


class FilesModel(FileCollection):

    COLUMN_HEADERS = (_('Folder'), _('Name'), _('Size (KB)'), _('Type'), _('Word count'))
    alignments = Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignRight, Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignRight
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
        self.sort_keys = tuple((psk(entry.dir), psk(entry.basename), entry.size, psk(self.CATEGORY_NAMES.get(entry.category, '')), entry.word_count)
                               for entry in self.files)
        self.endResetModel()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == SORT_ROLE:
            try:
                return self.sort_keys[index.row()][index.column()]
            except IndexError:
                pass
        elif role == Qt.ItemDataRole.DisplayRole:
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
                return '%.2f ' % sz
            if col == 3:
                return self.CATEGORY_NAMES.get(entry.category)
            if col == 4:
                ans = entry.word_count
                if ans > -1:
                    return str(ans)
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            return int(Qt.AlignVCenter | self.alignments[index.column()])  # https://bugreports.qt.io/browse/PYSIDE-1974


class FilesWidget(QWidget):

    edit_requested = pyqtSignal(object)
    delete_requested = pyqtSignal(object, object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)

        self.filter_edit = e = QLineEdit(self)
        l.addWidget(e)
        e.setPlaceholderText(_('Filter'))
        e.setClearButtonEnabled(True)
        self.model = m = FilesModel(self)
        self.files = f = FilesView(m, self)
        self.to_csv = f.to_csv
        f.delete_requested.connect(self.delete_requested)
        f.double_clicked.connect(self.double_clicked)
        e.textChanged.connect(f.proxy.filter_text)
        l.addWidget(f)

        self.summary = s = QLabel(self)
        l.addWidget(s)
        s.setText('\xa0')
        self.files.restore_table('all-files-table', 1, Qt.SortOrder.AscendingOrder)

    def __call__(self, data):
        self.model(data)
        self.files.resize_rows()
        self.filter_edit.clear()
        m = self.model
        self.summary.setText(_('Total uncompressed size of all files: {0} :: Images: {1} :: Fonts: {2}').format(*map(
            human_readable, (m.total_size, m.images_size, m.fonts_size))))

    def double_clicked(self, index):
        location = self.model.location(index)
        if location is not None:
            self.edit_requested.emit(location)

    def save(self):
        self.files.save_table('all-files-table')

# }}}

# Jump {{{


def jump_to_location(loc):
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
        c.setPosition(block.position(), QTextCursor.MoveMode.MoveAnchor)
        editor.setTextCursor(c)
        if loc.text_on_line is not None:
            editor.find(regex.compile(regex.escape(loc.text_on_line)))


class Jump:

    def __init__(self):
        self.pos_map = defaultdict(lambda : -1)

    def clear(self):
        self.pos_map.clear()

    def __call__(self, key, locations):
        if len(locations):
            self.pos_map[key] = (self.pos_map[key] + 1) % len(locations)
            loc = locations[self.pos_map[key]]
            jump_to_location(loc)


jump = Jump()  # }}}

# Images {{{


class ImagesDelegate(QStyledItemDelegate):

    MARGIN = 5

    def __init__(self, *args):
        QStyledItemDelegate.__init__(self, *args)

    def sizeHint(self, option, index):
        style = (option.styleObject or self.parent() or QApplication.instance()).style()
        self.initStyleOption(option, index)
        ans = style.sizeFromContents(QStyle.ContentsType.CT_ItemViewItem, option, QSize(), option.styleObject or self.parent())
        entry = index.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return ans
        th = int(self.parent().thumbnail_height * self.parent().devicePixelRatio())
        pmap = self.pixmap(th, entry._replace(usage=()), self.parent().devicePixelRatioF())
        if pmap.isNull():
            width = height = 0
        else:
            width, height = int(pmap.width() / pmap.devicePixelRatio()), int(pmap.height() / pmap.devicePixelRatio())
        m = self.MARGIN * 2
        return QSize(max(width + m, ans.width()), height + m + self.MARGIN + ans.height())

    def paint(self, painter, option, index):
        style = (option.styleObject or self.parent() or QApplication.instance()).style()
        self.initStyleOption(option, index)
        option.text = ''
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, option, painter, option.styleObject or self.parent())
        entry = index.data(Qt.ItemDataRole.UserRole)
        if entry is None:
            return
        painter.save()
        th = int(self.parent().thumbnail_height * self.parent().devicePixelRatio())
        pmap = self.pixmap(th, entry._replace(usage=()), painter.device().devicePixelRatioF())
        if pmap.isNull():
            bottom = option.rect.top()
        else:
            m = 2 * self.MARGIN
            x = option.rect.left() + (option.rect.width() - m - int(pmap.width()/pmap.devicePixelRatio())) // 2
            painter.drawPixmap(x, option.rect.top() + self.MARGIN, pmap)
            bottom = m + int(pmap.height() / pmap.devicePixelRatio()) + option.rect.top()
        rect = QRect(option.rect.left(), bottom, option.rect.width(), option.rect.bottom() - bottom)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(self.parent().palette().color(QPalette.ColorRole.HighlightedText))
        painter.drawText(rect, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter, entry.basename)
        painter.restore()

    @lru_cache(maxsize=1024)
    def pixmap(self, thumbnail_height, entry, dpr):
        entry_ok = entry.width > 0 and entry.height > 0
        entry_ok |= entry.mime_type == 'image/svg+xml'
        pmap = QPixmap(current_container().name_to_abspath(entry.name)) if entry_ok > 0 else QPixmap()
        if not pmap.isNull():
            pmap.setDevicePixelRatio(dpr)
            scaled, width, height = fit_image(pmap.width(), pmap.height(), thumbnail_height, thumbnail_height)
            if scaled:
                pmap = pmap.scaled(width, height, transformMode=Qt.TransformationMode.SmoothTransformation)
        return pmap


class ImagesModel(FileCollection):

    COLUMN_HEADERS = [_('Image'), _('Size (KB)'), _('Times used'), _('Resolution')]
    alignments = Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignRight, Qt.AlignmentFlag.AlignRight, Qt.AlignmentFlag.AlignRight

    def __init__(self, parent=None):
        FileCollection.__init__(self, parent)

    def __call__(self, data):
        self.beginResetModel()
        self.files = data['images']
        self.total_size = sum(map(itemgetter(3), self.files))
        self.sort_keys = tuple((psk(entry.basename), entry.size, len(entry.usage), (entry.width, entry.height))
                               for entry in self.files)
        self.endResetModel()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == SORT_ROLE:
            try:
                return self.sort_keys[index.row()][index.column()]
            except IndexError:
                pass
        elif role == Qt.ItemDataRole.DisplayRole:
            col = index.column()
            try:
                entry = self.files[index.row()]
            except IndexError:
                return None
            if col == 0:
                return entry.basename
            if col == 1:
                sz = entry.size / 1024.
                return ('%.2f' % sz if int(sz) != sz else str(sz))
            if col == 2:
                return str(len(entry.usage))
            if col == 3:
                return '%d x %d' % (entry.width, entry.height)
        elif role == Qt.ItemDataRole.UserRole:
            try:
                return self.files[index.row()]
            except IndexError:
                pass
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            with suppress(IndexError):
                return int(self.alignments[index.column()])  # https://bugreports.qt.io/browse/PYSIDE-1974


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
        e.setClearButtonEnabled(True)
        self.model = m = ImagesModel(self)
        self.files = f = FilesView(m, self)
        self.to_csv = f.to_csv
        f.customize_context_menu = self.customize_context_menu
        f.delete_requested.connect(self.delete_requested)
        f.horizontalHeader().sortIndicatorChanged.connect(self.resize_to_contents)
        self.delegate = ImagesDelegate(self)
        f.setItemDelegateForColumn(0, self.delegate)
        f.double_clicked.connect(self.double_clicked)
        e.textChanged.connect(f.proxy.filter_text)
        l.addWidget(f)
        self.files.restore_table('image-files-table')

    def __call__(self, data):
        self.model(data)
        self.filter_edit.clear()
        self.delegate.pixmap.cache_clear()
        self.files.resizeRowsToContents()

    def resize_to_contents(self, *args):
        QTimer.singleShot(0, self.files.resizeRowsToContents)

    def double_clicked(self, index):
        entry = index.data(Qt.ItemDataRole.UserRole)
        if entry is not None:
            jump((id(self), entry.id), entry.usage)

    def customize_context_menu(self, menu, selected_locations, current_location):
        if current_location is not None:
            menu.addAction(_('Edit the image: %s') % current_location, partial(self.edit_requested.emit, current_location))

    def save(self):
        self.files.save_table('image-files-table')
# }}}

# Links {{{


class LinksModel(FileCollection):

    COLUMN_HEADERS = ['✓', _('Source'), _('Source text'), _('Target'), _('Anchor'), _('Target text')]

    def __init__(self, parent=None):
        FileCollection.__init__(self, parent)
        self.num_bad = 0

    def __call__(self, data):
        self.beginResetModel()
        self.links = self.files = data['links']
        self.total_size = len(self.links)
        self.num_bad = sum(1 for link in self.links if link.ok is False)
        self.sort_keys = tuple((
            link.ok, psk(link.location.name), psk(link.text or ''), psk(link.href or ''), psk(link.anchor.id or ''), psk(link.anchor.text or ''))
                               for link in self.links)
        self.endResetModel()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == SORT_ROLE:
            try:
                return self.sort_keys[index.row()][index.column()]
            except IndexError:
                pass
        elif role == Qt.ItemDataRole.DisplayRole:
            col = index.column()
            try:
                link = self.links[index.row()]
            except IndexError:
                return None
            if col == 0:
                return {True:'✓', False:'✗'}.get(link.ok)
            if col == 1:
                return link.location.name
            if col == 2:
                return link.text
            if col == 3:
                return link.href
            if col == 4:
                return link.anchor.id
            if col == 5:
                return link.anchor.text
        elif role == Qt.ItemDataRole.ToolTipRole:
            col = index.column()
            try:
                link = self.links[index.row()]
            except IndexError:
                return None
            if col == 0:
                return {True:_('The link destination exists'), False:_('The link destination does not exist')}.get(
                    link.ok, _('The link destination could not be verified'))
            if col == 2:
                if link.text:
                    return textwrap.fill(link.text)
            if col == 5:
                if link.anchor.text:
                    return textwrap.fill(link.anchor.text)
        elif role == Qt.ItemDataRole.UserRole:
            try:
                return self.links[index.row()]
            except IndexError:
                pass


class WebView(RestartingWebEngineView):

    def sizeHint(self):
        return QSize(600, 200)


class LinksWidget(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)

        self.filter_edit = e = QLineEdit(self)
        l.addWidget(e)
        self.splitter = s = QSplitter(Qt.Orientation.Vertical, self)
        l.addWidget(s)
        e.setPlaceholderText(_('Filter'))
        e.setClearButtonEnabled(True)
        self.model = m = LinksModel(self)
        self.links = f = FilesView(m, self)
        f.DELETE_POSSIBLE = False
        self.to_csv = f.to_csv
        f.double_clicked.connect(self.double_clicked)
        e.textChanged.connect(f.proxy.filter_text)
        s.addWidget(f)
        self.links.restore_table('links-table', sort_column=1)
        self.view = None
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
        self.ignore_current_change = False
        self.current_url = None
        f.current_changed.connect(self.current_changed)
        try:
            s.restoreState(read_state('links-view-splitter'))
        except TypeError:
            pass
        s.setCollapsible(0, False)
        s.setStretchFactor(0, 10)

    def __call__(self, data):
        if self.view is None:
            self.view = WebView(self)
            secure_webengine(self.view)
            self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.NoContextMenu)
            self.splitter.addWidget(self.view)
            self.splitter.setCollapsible(1, True)
        self.ignore_current_change = True
        self.model(data)
        self.filter_edit.clear()
        self.links.resize_rows()
        self.view.setHtml('<p>'+_(
            'Click entries above to see their destination here'))
        self.ignore_current_change = False

    def current_changed(self, current, previous):
        link = current.data(Qt.ItemDataRole.UserRole)
        if link is None:
            return
        url = None
        if link.is_external:
            if link.href:
                frag = ('#' + link.anchor.id) if link.anchor.id else ''
                url = QUrl(link.href + frag)
        elif link.anchor.location:
            path = current_container().name_to_abspath(link.anchor.location.name)
            if path and os.path.exists(path):
                url = QUrl.fromLocalFile(path)
                if link.anchor.id:
                    url.setFragment(link.anchor.id)
        if url is None:
            if self.view:
                self.view.setHtml('<p>' + _('No destination found for this link'))
            self.current_url = url
        elif url != self.current_url:
            self.current_url = url
            if self.view:
                self.view.setUrl(url)

    def double_clicked(self, index):
        link = index.data(Qt.ItemDataRole.UserRole)
        if link is None:
            return
        if index.column() < 3:
            # Jump to source
            jump_to_location(link.location)
        else:
            # Jump to destination
            if link.is_external:
                if link.href:
                    open_url(link.href)
            elif link.anchor.location:
                jump_to_location(link.anchor.location)

    def save(self):
        self.links.save_table('links-table')
        save_state('links-view-splitter', bytearray(self.splitter.saveState()))
# }}}

# Words {{{


class WordsModel(FileCollection):

    COLUMN_HEADERS = (_('Word'), _('Language'), _('Times used'))
    alignments = Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignRight
    total_words = 0

    def __call__(self, data):
        self.beginResetModel()
        self.total_words, self.files = data['words']
        self.total_size = len({entry.locale for entry in self.files})
        lsk_cache = {}

        def locale_sort_key(loc):
            try:
                return lsk_cache[loc]
            except KeyError:
                lsk_cache[loc] = psk(calibre_langcode_to_name(canonicalize_lang(loc[0])) + (loc[1] or ''))
            return lsk_cache[loc]

        self.sort_keys = tuple((psk(entry.word), locale_sort_key(entry.locale), len(entry.usage)) for entry in self.files)
        self.endResetModel()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == SORT_ROLE:
            try:
                return self.sort_keys[index.row()][index.column()]
            except IndexError:
                pass
        elif role == Qt.ItemDataRole.DisplayRole:
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
                return str(len(entry.usage))
        elif role == Qt.ItemDataRole.UserRole:
            try:
                return self.files[index.row()]
            except IndexError:
                pass
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            with suppress(IndexError):
                return int(self.alignments[index.column()])  # https://bugreports.qt.io/browse/PYSIDE-1974

    def location(self, index):
        return None


class WordsWidget(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)

        self.filter_edit = e = QLineEdit(self)
        l.addWidget(e)
        e.setPlaceholderText(_('Filter'))
        e.setClearButtonEnabled(True)
        self.model = m = WordsModel(self)
        self.words = f = FilesView(m, self)
        self.to_csv = f.to_csv
        f.DELETE_POSSIBLE = False
        f.double_clicked.connect(self.double_clicked)
        e.textChanged.connect(f.proxy.filter_text)
        l.addWidget(f)

        self.summary = la = QLabel('\xa0')
        l.addWidget(la)
        self.words.restore_table('words-table')

    def __call__(self, data):
        self.model(data)
        self.words.resize_rows()
        self.filter_edit.clear()
        self.summary.setText(_('Words: {2} :: Unique Words: :: {0} :: Languages: {1}').format(
            self.model.rowCount(), self.model.total_size, self.model.total_words))

    def double_clicked(self, index):
        entry = index.data(Qt.ItemDataRole.UserRole)
        if entry is not None:
            from calibre.gui2.tweak_book.boss import get_boss
            boss = get_boss()
            if boss is not None:
                boss.find_word((entry.word, entry.locale), entry.usage)

    def save(self):
        self.words.save_table('words-table')
# }}}

# Characters {{{


class CharsModel(FileCollection):

    COLUMN_HEADERS = (_('Character'), _('Name'), _('Codepoint'), _('Times used'))
    alignments = Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignLeft, Qt.AlignmentFlag.AlignRight
    all_chars = ()

    def __call__(self, data):
        self.beginResetModel()
        self.files = data['chars']
        self.all_chars = tuple(entry.char for entry in self.files)
        self.sort_keys = tuple((psk(entry.char), None, entry.codepoint, entry.count) for entry in self.files)
        self.endResetModel()

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == SORT_ROLE:
            if index.column() == 1:
                return self.data(index)
            try:
                return self.sort_keys[index.row()][index.column()]
            except IndexError:
                pass
        elif role == Qt.ItemDataRole.DisplayRole:
            col = index.column()
            try:
                entry = self.files[index.row()]
            except IndexError:
                return None
            if col == 0:
                return entry.char
            if col == 1:
                return {0xa:'LINE FEED', 0xd:'CARRIAGE RETURN', 0x9:'TAB'}.get(entry.codepoint, character_name_from_code(entry.codepoint))
            if col == 2:
                return ('U+%04X' if entry.codepoint < 0x10000 else 'U+%06X') % entry.codepoint
            if col == 3:
                return str(entry.count)
        elif role == Qt.ItemDataRole.UserRole:
            try:
                return self.files[index.row()]
            except IndexError:
                pass
        elif role == Qt.ItemDataRole.TextAlignmentRole:
            with suppress(IndexError):
                return int(self.alignments[index.column()])  # https://bugreports.qt.io/browse/PYSIDE-1974

    def location(self, index):
        return None


class CharsWidget(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)

        self.filter_edit = e = QLineEdit(self)
        l.addWidget(e)
        e.setPlaceholderText(_('Filter'))
        e.setClearButtonEnabled(True)
        self.model = m = CharsModel(self)
        self.chars = f = FilesView(m, self)
        self.to_csv = f.to_csv
        f.DELETE_POSSIBLE = False
        f.double_clicked.connect(self.double_clicked)
        e.textChanged.connect(f.proxy.filter_text)
        l.addWidget(f)

        self.summary = la = QLineEdit(self)
        la.setReadOnly(True)
        la.setToolTip(_('All the characters in the book'))
        l.addWidget(la)
        self.chars.restore_table('chars-table')

    def __call__(self, data):
        self.model(data)
        self.chars.resize_rows()
        self.summary.setText(''.join(self.model.all_chars))
        self.filter_edit.clear()

    def double_clicked(self, index):
        entry = index.data(Qt.ItemDataRole.UserRole)
        if entry is not None:
            self.find_next_location(entry)

    def save(self):
        self.chars.save_table('chars-table')

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
            if ed is None:
                return
            if ed.editor.find_text(pat, complete=not from_cursor):
                boss.show_editor(file_name)
                return True
        return False

# }}}

# CSS {{{


class CSSRulesModel(QAbstractItemModel):

    def __init__(self, parent):
        QAbstractItemModel.__init__(self, parent)
        self.rules = ()
        self.sort_on_count = True
        self.num_size = 1
        self.num_unused = 0
        self.build_maps()
        self.main_font = f = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        f.setBold(True), f.setPointSize(parent.font().pointSize() + 2)
        self.italic_font = f = QFont(parent.font())
        f.setItalic(True)

    def build_maps(self):
        self.parent_map = pm = {}
        for i, entry in enumerate(self.rules):
            container = entry.matched_files
            pm[container] = (i, self.rules)
            for i, child in enumerate(container):
                gcontainer = child.locations
                pm[gcontainer] = (i, container)
                for i, gc in enumerate(gcontainer):
                    pm[gc] = (i, gcontainer)

    def index(self, row, column, parent=ROOT):
        container = self.to_container(self.index_to_entry(parent) or self.rules)
        return self.createIndex(row, column, container) if -1 < row < len(container) else ROOT

    def to_container(self, entry):
        if isinstance(entry, CSSEntry):
            return entry.matched_files
        elif isinstance(entry, CSSFileMatch):
            return entry.locations
        return entry

    def index_to_entry(self, index):
        if index.isValid():
            try:
                return index.internalPointer()[index.row()]
            except IndexError:
                pass

    def parent(self, index):
        if not index.isValid():
            return ROOT
        parent = index.internalPointer()
        if parent is self.rules or parent is None:
            return ROOT
        try:
            pidx, grand_parent = self.parent_map[parent]
        except KeyError:
            return ROOT
        return self.createIndex(pidx, 0, grand_parent)

    def rowCount(self, parent=ROOT):
        if not parent.isValid():
            return len(self.rules)
        entry = self.index_to_entry(parent)
        c = self.to_container(entry)
        return 0 if c is entry else len(c)

    def columnCount(self, parent=ROOT):
        return 1

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == SORT_ROLE:
            entry = self.index_to_entry(index)
            if isinstance(entry, CSSEntry):
                return entry.count if self.sort_on_count else entry.sort_key
            if isinstance(entry, CSSFileMatch):
                return len(entry.locations) if self.sort_on_count else entry.sort_key
            if isinstance(entry, MatchLocation):
                return entry.sourceline
        elif role == Qt.ItemDataRole.DisplayRole:
            entry = self.index_to_entry(index)
            if isinstance(entry, CSSEntry):
                return f'[%{self.num_size}d] %s' % (entry.count, entry.rule.selector)
            elif isinstance(entry, CSSFileMatch):
                return _('{0} [{1} elements]').format(entry.file_name, len(entry.locations))
            elif isinstance(entry, MatchLocation):
                return f'{entry.tag} @ {entry.sourceline}'
        elif role == Qt.ItemDataRole.UserRole:
            return self.index_to_entry(index)
        elif role == Qt.ItemDataRole.FontRole:
            entry = self.index_to_entry(index)
            if isinstance(entry, CSSEntry):
                return self.main_font
            elif isinstance(entry, CSSFileMatch):
                return self.italic_font

    def __call__(self, data):
        self.beginResetModel()
        self.rules = data['css']
        self.num_unused = sum(1 for r in self.rules if r.count == 0)
        try:
            self.num_size = len(str(max(r.count for r in self.rules)))
        except ValueError:
            self.num_size = 1
        self.build_maps()
        self.endResetModel()


class CSSProxyModel(QSortFilterProxyModel):

    def __init__(self, parent=None):
        QSortFilterProxyModel.__init__(self, parent)
        self._filter_text = None
        self.setSortRole(SORT_ROLE)

    def filter_text(self, text):
        self._filter_text = text
        self.setFilterFixedString(text)

    def filterAcceptsRow(self, row, parent):
        if not self._filter_text:
            return True
        sm = self.sourceModel()
        entry = sm.index_to_entry(sm.index(row, 0, parent))
        if not isinstance(entry, CSSEntry):
            return True
        return primary_contains(self._filter_text, entry.rule.selector)


class CSSWidget(QWidget):

    SETTING_PREFIX = 'css-'
    MODEL = CSSRulesModel
    PROXY = CSSProxyModel

    def read_state(self, name, default=None):
        return read_state(self.SETTING_PREFIX+name, default)

    def save_state(self, name, val):
        return save_state(self.SETTING_PREFIX + name, val)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QVBoxLayout(self)
        self.h = h = QHBoxLayout()

        self.filter_edit = e = QLineEdit(self)
        l.addWidget(e)
        e.setPlaceholderText(_('Filter'))
        e.setClearButtonEnabled(True)
        self.model = m = self.MODEL(self)
        self.proxy = p = self.PROXY(self)
        p.setSourceModel(m)
        self.view = f = QTreeView(self)
        f.setAlternatingRowColors(True)
        f.setHeaderHidden(True), f.setExpandsOnDoubleClick(False)
        f.setModel(p)
        l.addWidget(f)
        f.doubleClicked.connect(self.double_clicked)
        e.textChanged.connect(p.filter_text)

        l.addLayout(h)
        h.addWidget(QLabel(_('Sort by:')))
        self.counts_button = b = QRadioButton(_('&Counts'), self)
        b.setChecked(self.read_state('sort-on-counts', True))
        h.addWidget(b)
        self.name_button = b = QRadioButton(_('&Name'), self)
        b.setChecked(not self.read_state('sort-on-counts', True))
        h.addWidget(b)
        b.toggled.connect(self.resort)
        h.addStrut(20)
        self._sort_order = o = QComboBox(self)
        o.addItems([_('Ascending'), _('Descending')])
        o.setCurrentIndex(0 if self.read_state('sort-ascending', True) else 1)
        o.setEditable(False)
        o.currentIndexChanged.connect(self.resort)
        h.addWidget(o)
        h.addStretch(10)
        self.summary = la = QLabel('\xa0')
        h.addWidget(la)

    @property
    def sort_order(self):
        return [Qt.SortOrder.AscendingOrder, Qt.SortOrder.DescendingOrder][self._sort_order.currentIndex()]

    @sort_order.setter
    def sort_order(self, val):
        self._sort_order.setCurrentIndex({Qt.SortOrder.AscendingOrder:0}.get(val, 1))

    def update_summary(self):
        self.summary.setText(_('{0} rules, {1} unused').format(self.model.rowCount(), self.model.num_unused))

    def __call__(self, data):
        self.model(data)
        self.update_summary()
        self.filter_edit.clear()
        self.resort()

    def save(self):
        self.save_state('sort-on-counts', self.counts_button.isChecked())
        self.save_state('sort-ascending', self.sort_order == Qt.SortOrder.AscendingOrder)

    def resort(self, *args):
        self.model.sort_on_count = self.counts_button.isChecked()
        self.proxy.sort(-1, self.sort_order)  # for some reason the proxy model does not resort without this
        self.proxy.sort(0, self.sort_order)

    def to_csv(self):
        buf = StringIO(newline='')
        w = csv_writer(buf)
        w.writerow([_('Style Rule'), _('Number of matches')])
        for r in range(self.proxy.rowCount()):
            entry = self.proxy.mapToSource(self.proxy.index(r, 0)).data(Qt.ItemDataRole.UserRole)
            w.writerow([entry.rule.selector, entry.count])
        return buf.getvalue()

    def double_clicked(self, index):
        from calibre.gui2.tweak_book.boss import get_boss
        boss = get_boss()
        if boss is None:
            return
        index = self.proxy.mapToSource(index)
        entry = self.model.index_to_entry(index)
        if entry is None:
            return
        self.handle_double_click(entry, index, boss)

    def handle_double_click(self, entry, index, boss):
        if isinstance(entry, CSSEntry):
            loc = entry.rule.location
            name, sourceline, col = loc
        elif isinstance(entry, CSSFileMatch):
            name, sourceline = entry.file_name, 0
        else:
            name = self.model.index_to_entry(index.parent()).file_name
            sourceline = entry.sourceline
        self.show_line(name, sourceline, boss)

    def show_line(self, name, sourceline, boss):
        editor = boss.edit_file_requested(name)
        if editor is None:
            return
        editor = editor.editor
        block = editor.document().findBlockByNumber(max(0, sourceline - 1))  # blockNumber() is zero based
        c = editor.textCursor()
        c.setPosition(block.position() if block.isValid() else 0)
        editor.setTextCursor(c)
        boss.show_editor(name)

# }}}

# Classes {{{


class ClassesModel(CSSRulesModel):

    def __init__(self, parent):
        self.classes = self.rules = ()
        CSSRulesModel.__init__(self, parent)
        self.sort_on_count = True
        self.num_size = 1
        self.num_unused = 0
        self.build_maps()

    def build_maps(self):
        self.parent_map = pm = {}
        for i, entry in enumerate(self.classes):
            container = entry.matched_files
            pm[container] = (i, self.classes)

            for i, child in enumerate(container):
                gcontainer = child.class_elements
                pm[gcontainer] = (i, container)

                for i, gc in enumerate(gcontainer):
                    ggcontainer = gc.matched_rules
                    pm[gc] = (i, gcontainer)

                    for i, ggc in enumerate(ggcontainer):
                        pm[ggc] = (i, ggcontainer)

    def to_container(self, entry):
        if isinstance(entry, ClassEntry):
            return entry.matched_files
        elif isinstance(entry, ClassFileMatch):
            return entry.class_elements
        elif isinstance(entry, ClassElement):
            return entry.matched_rules
        return entry

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if role == SORT_ROLE:
            entry = self.index_to_entry(index)
            if isinstance(entry, ClassEntry):
                return entry.num_of_matches if self.sort_on_count else entry.sort_key
            if isinstance(entry, ClassFileMatch):
                return len(entry.class_elements) if self.sort_on_count else entry.sort_key
            if isinstance(entry, ClassElement):
                return entry.line_number
            if isinstance(entry, CSSRule):
                return entry.location.file_name
        elif role == Qt.ItemDataRole.DisplayRole:
            entry = self.index_to_entry(index)
            if isinstance(entry, ClassEntry):
                return f'[%{self.num_size}d] %s' % (entry.num_of_matches, entry.cls)
            elif isinstance(entry, ClassFileMatch):
                return _('{0} [{1} elements]').format(entry.file_name, len(entry.class_elements))
            elif isinstance(entry, ClassElement):
                return f'{entry.tag} @ {entry.line_number}'
            elif isinstance(entry, CSSRule):
                return f'{entry.selector} @ {entry.location.file_name}:{entry.location.line}'
        elif role == Qt.ItemDataRole.UserRole:
            return self.index_to_entry(index)
        elif role == Qt.ItemDataRole.FontRole:
            entry = self.index_to_entry(index)
            if isinstance(entry, ClassEntry):
                return self.main_font
            elif isinstance(entry, ClassFileMatch):
                return self.italic_font

    def __call__(self, data):
        self.beginResetModel()
        self.rules = self.classes = tuple(data['classes'])
        self.num_unused = sum(1 for ce in self.classes if ce.num_of_matches == 0)
        try:
            self.num_size = len(str(max(r.num_of_matches for r in self.classes)))
        except ValueError:
            self.num_size = 1
        self.build_maps()
        self.endResetModel()


class ClassProxyModel(CSSProxyModel):

    def filterAcceptsRow(self, row, parent):
        if not self._filter_text:
            return True
        sm = self.sourceModel()
        entry = sm.index_to_entry(sm.index(row, 0, parent))
        if not isinstance(entry, ClassEntry):
            return True
        return primary_contains(self._filter_text, entry.cls)


class ClassesWidget(CSSWidget):

    SETTING_PREFIX = 'classes-'
    MODEL = ClassesModel
    PROXY = ClassProxyModel

    def update_summary(self):
        self.summary.setText(_('{0} classes, {1} unused').format(self.model.rowCount(), self.model.num_unused))

    def to_csv(self):
        buf = StringIO(newline='')
        w = csv_writer(buf)
        w.writerow([_('Class'), _('Number of matches')])
        for r in range(self.proxy.rowCount()):
            entry = self.proxy.mapToSource(self.proxy.index(r, 0)).data(Qt.ItemDataRole.UserRole)
            w.writerow([entry.cls, entry.num_of_matches])
        return buf.getvalue()

    def handle_double_click(self, entry, index, boss):
        if isinstance(entry, ClassEntry):
            def uniq(vals):
                vals = vals or ()
                seen = set()
                seen_add = seen.add
                return tuple(x for x in vals if x not in seen and not seen_add(x))

            rules = tuple(uniq([LinkLocation(rule.location.file_name, rule.location.line, None)
                                for cfm in entry.matched_files for ce in cfm.class_elements for rule in ce.matched_rules]))
            if rules:
                jump((id(self), id(entry)), rules)
            return
        elif isinstance(entry, ClassFileMatch):
            name, sourceline = entry.file_name, 0
        elif isinstance(entry, ClassElement):
            return jump_to_location(entry)
        else:
            loc = entry.location
            name, sourceline, col = loc
        self.show_line(name, sourceline, boss)

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

        self.css = c = CSSWidget(self)
        s.addWidget(c)
        QListWidgetItem(_('Style rules'), r)

        self.css = c = ClassesWidget(self)
        s.addWidget(c)
        QListWidgetItem(_('Style classes'), r)

        self.chars = c = CharsWidget(self)
        s.addWidget(c)
        QListWidgetItem(_('Characters'), r)

        self.links = li = LinksWidget(self)
        s.addWidget(li)
        QListWidgetItem(_('Links'), r)

        self.splitter.setStretchFactor(1, 500)
        try:
            self.splitter.restoreState(read_state('splitter-state'))
        except TypeError:
            pass
        current_page = read_state('report-page')
        if current_page is not None:
            self.reports.setCurrentRow(current_page)
        self.layout().setContentsMargins(0, 0, 0, 0)
        for i in range(self.stack.count()):
            self.stack.widget(i).layout().setContentsMargins(0, 0, 0, 0)

    def __call__(self, data):
        jump.clear()
        for i in range(self.stack.count()):
            st = time.time()
            self.stack.widget(i)(data)
            if DEBUG:
                category = self.reports.item(i).data(Qt.ItemDataRole.DisplayRole)
                print('Widget time for %12s: %.2fs seconds' % (category, time.time() - st))

    def save(self):
        save_state('splitter-state', bytearray(self.splitter.saveState()))
        save_state('report-page', self.reports.currentRow())
        for i in range(self.stack.count()):
            self.stack.widget(i).save()

    def to_csv(self):
        w = self.stack.currentWidget()
        category = self.reports.currentItem().data(Qt.ItemDataRole.DisplayRole)
        if not hasattr(w, 'to_csv'):
            return error_dialog(self, _('Not supported'), _(
                'Export of %s data is not supported') % category, show=True)
        data = w.to_csv()
        fname = choose_save_file(self, 'report-csv-export', _('Choose a filename for the data'), filters=[
            (_('CSV files'), ['csv'])], all_files=False, initial_filename='%s.csv' % category)
        if fname:
            with open(fname, 'wb') as f:
                f.write(as_bytes(data))


class Reports(Dialog):

    data_gathered = pyqtSignal(object, object)
    edit_requested = pyqtSignal(object)
    refresh_starting = pyqtSignal()
    delete_requested = pyqtSignal(object, object)

    def __init__(self, parent=None):
        Dialog.__init__(self, _('Reports'), 'reports-dialog', parent=parent)
        self.data_gathered.connect(self.display_data, type=Qt.ConnectionType.QueuedConnection)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setWindowIcon(QIcon.ic('reports.png'))

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
        l.addStretch(1), l.addWidget(pi, alignment=Qt.AlignmentFlag.AlignHCenter), l.addSpacing(10)
        pw.la = la = QLabel(_('Gathering data, please wait...'))
        la.setStyleSheet('QLabel { font-size: 30pt; font-weight: bold }')
        l.addWidget(la, alignment=Qt.AlignmentFlag.AlignHCenter), l.addStretch(1)

        self.bb.setStandardButtons(QDialogButtonBox.StandardButton.Close)
        self.refresh_button = b = self.bb.addButton(_('&Refresh'), QDialogButtonBox.ButtonRole.ActionRole)
        b.clicked.connect(self.refresh)
        b.setIcon(QIcon.ic('view-refresh.png'))
        self.save_button = b = self.bb.addButton(_('&Save'), QDialogButtonBox.ButtonRole.ActionRole)
        b.clicked.connect(self.reports.to_csv)
        b.setIcon(QIcon.ic('save.png'))
        b.setToolTip(_('Export the currently shown report as a CSV file'))

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
        self.setCursor(Qt.CursorShape.BusyCursor)
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
        data, timing = data
        if DEBUG:
            for x, t in sorted(iteritems(timing), key=itemgetter(1)):
                print('Time for %6s data: %.3f seconds' % (x, t))
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
    import sys

    from calibre.gui2 import Application
    app = Application([])
    from calibre.gui2.tweak_book import set_current_container
    from calibre.gui2.tweak_book.boss import get_container
    set_current_container(get_container(sys.argv[-1]))
    d = Reports()
    d.refresh()
    d.exec()
    del d, app
