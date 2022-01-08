#!/usr/bin/env python
# License: GPL v3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>


import json
from operator import itemgetter
from qt.core import (
    QAbstractItemView, QAction, QComboBox, QGridLayout, QHBoxLayout, QIcon,
    QInputDialog, QItemSelectionModel, QLabel, QListWidget, QListWidgetItem,
    QPushButton, Qt, QWidget, pyqtSignal
)

from calibre.gui2 import choose_files, choose_save_file
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.gestures import GestureManager
from calibre.gui2.viewer.shortcuts import get_shortcut_for
from calibre.gui2.viewer.web_view import vprefs
from calibre.utils.date import EPOCH, utcnow
from calibre.utils.icu import primary_sort_key


class BookmarksList(QListWidget):

    changed = pyqtSignal()
    bookmark_activated = pyqtSignal(object)

    def __init__(self, parent=None):
        QListWidget.__init__(self, parent)
        self.setAlternatingRowColors(True)
        self.setStyleSheet('QListView::item { padding: 0.5ex }')
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        self.ac_edit = ac = QAction(QIcon.ic('edit_input.png'), _('Rename this bookmark'), self)
        self.addAction(ac)
        self.ac_delete = ac = QAction(QIcon.ic('trash.png'), _('Remove this bookmark'), self)
        self.addAction(ac)
        self.gesture_manager = GestureManager(self)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

    def viewportEvent(self, ev):
        try:
            ret = self.gesture_manager.handle_event(ev)
        except AttributeError:
            ret = None
        if ret is not None:
            return ret
        return super().viewportEvent(ev)

    @property
    def current_non_removed_item(self):
        ans = self.currentItem()
        if ans is not None:
            bm = ans.data(Qt.ItemDataRole.UserRole)
            if not bm.get('removed'):
                return ans

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            i = self.current_non_removed_item
            if i is not None:
                self.bookmark_activated.emit(i)
                ev.accept()
                return
        if ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            i = self.current_non_removed_item
            if i is not None:
                self.ac_delete.trigger()
                ev.accept()
                return
        return QListWidget.keyPressEvent(self, ev)

    def activate_related_bookmark(self, delta=1):
        if not self.count():
            return
        items = [self.item(r) for r in range(self.count())]
        row = self.currentRow()
        current_item = items[row]
        items = [i for i in items if not i.isHidden()]
        count = len(items)
        if not count:
            return
        row = items.index(current_item)
        nrow = (row + delta + count) % count
        self.setCurrentItem(items[nrow])
        self.bookmark_activated.emit(self.currentItem())

    def next_bookmark(self):
        self.activate_related_bookmark()

    def previous_bookmark(self):
        self.activate_related_bookmark(-1)


class BookmarkManager(QWidget):

    edited = pyqtSignal(object)
    activated = pyqtSignal(object)
    create_requested = pyqtSignal()
    toggle_requested = pyqtSignal()

    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.l = l = QGridLayout(self)
        l.setContentsMargins(0, 0, 0, 0)
        self.setLayout(l)
        self.toc = parent.toc

        self.bookmarks_list = bl = BookmarksList(self)
        bl.itemChanged.connect(self.item_changed)
        l.addWidget(bl, 0, 0, 1, -1)
        bl.itemClicked.connect(self.item_activated)
        bl.bookmark_activated.connect(self.item_activated)
        bl.changed.connect(lambda : self.edited.emit(self.get_bookmarks()))
        bl.ac_edit.triggered.connect(self.edit_bookmark)
        bl.ac_delete.triggered.connect(self.delete_bookmark)

        self.la = la = QLabel(_(
            'Double click to edit the bookmarks'))
        la.setWordWrap(True)
        l.addWidget(la, l.rowCount(), 0, 1, -1)

        self.button_new = b = QPushButton(QIcon.ic('bookmarks.png'), _('&New'), self)
        b.clicked.connect(self.create_requested)
        b.setToolTip(_('Create a new bookmark at the current location'))
        l.addWidget(b)

        self.button_delete = b = QPushButton(QIcon.ic('trash.png'), _('&Remove'), self)
        b.setToolTip(_('Remove the currently selected bookmark'))
        b.clicked.connect(self.delete_bookmark)
        l.addWidget(b, l.rowCount() - 1, 1)

        self.button_prev = b = QPushButton(QIcon.ic('back.png'), _('Pre&vious'), self)
        b.clicked.connect(self.bookmarks_list.previous_bookmark)
        l.addWidget(b)

        self.button_next = b = QPushButton(QIcon.ic('forward.png'), _('Nex&t'), self)
        b.clicked.connect(self.bookmarks_list.next_bookmark)
        l.addWidget(b, l.rowCount() - 1, 1)

        la = QLabel(_('&Sort by:'))
        self.sort_by = sb = QComboBox(self)
        la.setBuddy(sb)
        sb.addItem(_('Title'), 'title')
        sb.addItem(_('Position in book'), 'pos')
        sb.addItem(_('Date'), 'timestamp')
        sb.setToolTip(_('Change how the bookmarks are sorted'))
        i = sb.findData(vprefs['bookmarks_sort'])
        if i > -1:
            sb.setCurrentIndex(i)
        h = QHBoxLayout()
        h.addWidget(la), h.addWidget(sb, 10)
        l.addLayout(h, l.rowCount(), 0, 1, 2)
        sb.currentIndexChanged.connect(self.sort_by_changed)

        self.button_export = b = QPushButton(_('E&xport'), self)
        b.clicked.connect(self.export_bookmarks)
        l.addWidget(b, l.rowCount(), 0)

        self.button_import = b = QPushButton(_('&Import'), self)
        b.clicked.connect(self.import_bookmarks)
        l.addWidget(b, l.rowCount() - 1, 1)

    def item_activated(self, item):
        bm = self.item_to_bm(item)
        self.activated.emit(bm['pos'])

    @property
    def current_sort_by(self):
        return self.sort_by.currentData()

    def sort_by_changed(self):
        vprefs['bookmarks_sort'] = self.current_sort_by
        self.set_bookmarks(self.get_bookmarks())

    def set_bookmarks(self, bookmarks=()):
        csb = self.current_sort_by
        if csb in ('name', 'title'):
            sk = lambda x: primary_sort_key(x['title'])
        elif csb == 'timestamp':
            sk = itemgetter('timestamp')
        else:
            from calibre.ebooks.epub.cfi.parse import cfi_sort_key
            defval = cfi_sort_key('/99999999')

            def pos_key(b):
                if b.get('pos_type') == 'epubcfi':
                    return cfi_sort_key(b['pos'], only_path=False)
                return defval
            sk = pos_key

        bookmarks = sorted(bookmarks, key=sk)
        current_bookmark_id = self.current_bookmark_id
        self.bookmarks_list.clear()
        for bm in bookmarks:
            i = QListWidgetItem(bm['title'])
            i.setData(Qt.ItemDataRole.ToolTipRole, bm['title'])
            i.setData(Qt.ItemDataRole.UserRole, self.bm_to_item(bm))
            i.setFlags(i.flags() | Qt.ItemFlag.ItemIsEditable)
            self.bookmarks_list.addItem(i)
            if bm.get('removed'):
                i.setHidden(True)
        for i in range(self.bookmarks_list.count()):
            item = self.bookmarks_list.item(i)
            if not item.isHidden():
                self.bookmarks_list.setCurrentItem(item, QItemSelectionModel.SelectionFlag.ClearAndSelect)
                break
        if current_bookmark_id is not None:
            self.current_bookmark_id = current_bookmark_id

    @property
    def current_bookmark_id(self):
        item = self.bookmarks_list.currentItem()
        if item is not None:
            return item.data(Qt.ItemDataRole.DisplayRole)

    @current_bookmark_id.setter
    def current_bookmark_id(self, val):
        for i, q in enumerate(self):
            if q['title'] == val:
                item = self.bookmarks_list.item(i)
                self.bookmarks_list.setCurrentItem(item, QItemSelectionModel.SelectionFlag.ClearAndSelect)
                self.bookmarks_list.scrollToItem(item)

    def set_current_bookmark(self, bm):
        for i, q in enumerate(self):
            if bm == q:
                l = self.bookmarks_list
                item = l.item(i)
                l.setCurrentItem(item, QItemSelectionModel.SelectionFlag.ClearAndSelect)
                l.scrollToItem(item)

    def __iter__(self):
        for i in range(self.bookmarks_list.count()):
            yield self.item_to_bm(self.bookmarks_list.item(i))

    def uniqify_bookmark_title(self, base):
        remove = []
        for i in range(self.bookmarks_list.count()):
            item = self.bookmarks_list.item(i)
            bm = item.data(Qt.ItemDataRole.UserRole)
            if bm.get('removed') and bm['title'] == base:
                remove.append(i)
        for i in reversed(remove):
            self.bookmarks_list.takeItem(i)
        all_titles = {bm['title'] for bm in self.get_bookmarks()}
        c = 0
        q = base
        while q in all_titles:
            c += 1
            q = f'{base} #{c}'
        return q

    def item_changed(self, item):
        self.bookmarks_list.blockSignals(True)
        title = str(item.data(Qt.ItemDataRole.DisplayRole)) or _('Unknown')
        title = self.uniqify_bookmark_title(title)
        item.setData(Qt.ItemDataRole.DisplayRole, title)
        item.setData(Qt.ItemDataRole.ToolTipRole, title)
        bm = item.data(Qt.ItemDataRole.UserRole)
        bm['title'] = title
        bm['timestamp'] = utcnow().isoformat()
        item.setData(Qt.ItemDataRole.UserRole, bm)
        self.bookmarks_list.blockSignals(False)
        self.edited.emit(self.get_bookmarks())

    def delete_bookmark(self):
        item = self.bookmarks_list.current_non_removed_item
        if item is not None:
            bm = item.data(Qt.ItemDataRole.UserRole)
            if confirm(
                _('Are you sure you want to delete the bookmark: {0}?').format(bm['title']),
                'delete-bookmark-from-viewer', parent=self, config_set=vprefs
            ):
                bm['removed'] = True
                bm['timestamp'] = utcnow().isoformat()
                self.bookmarks_list.blockSignals(True)
                item.setData(Qt.ItemDataRole.UserRole, bm)
                self.bookmarks_list.blockSignals(False)
                item.setHidden(True)
                self.edited.emit(self.get_bookmarks())

    def edit_bookmark(self):
        item = self.bookmarks_list.current_non_removed_item
        if item is not None:
            self.bookmarks_list.editItem(item)

    def bm_to_item(self, bm):
        return bm.copy()

    def item_to_bm(self, item):
        return item.data(Qt.ItemDataRole.UserRole).copy()

    def get_bookmarks(self):
        return list(self)

    def export_bookmarks(self):
        filename = choose_save_file(
            self, 'export-viewer-bookmarks', _('Export bookmarks'),
            filters=[(_('Saved bookmarks'), ['calibre-bookmarks'])], all_files=False, initial_filename='bookmarks.calibre-bookmarks')
        if filename:
            bm = [x for x in self.get_bookmarks() if not x.get('removed')]
            data = json.dumps({'type': 'bookmarks', 'entries': bm}, indent=True)
            if not isinstance(data, bytes):
                data = data.encode('utf-8')
            with lopen(filename, 'wb') as fileobj:
                fileobj.write(data)

    def import_bookmarks(self):
        files = choose_files(self, 'export-viewer-bookmarks', _('Import bookmarks'),
            filters=[(_('Saved bookmarks'), ['calibre-bookmarks'])], all_files=False, select_only_single_file=True)
        if not files:
            return
        filename = files[0]

        imported = None
        with lopen(filename, 'rb') as fileobj:
            imported = json.load(fileobj)

        def import_old_bookmarks(imported):
            try:
                for bm in imported:
                    if 'title' not in bm:
                        return
            except Exception:
                return

            bookmarks = self.get_bookmarks()
            for bm in imported:
                if bm['title'] == 'calibre_current_page_bookmark':
                    continue
                epubcfi = 'epubcfi(/{}/{})'.format((bm['spine'] + 1) * 2, bm['pos'].lstrip('/'))
                q = {'pos_type': 'epubcfi', 'pos': epubcfi, 'timestamp': EPOCH.isoformat(), 'title': bm['title']}
                if q not in bookmarks:
                    bookmarks.append(q)
            self.set_bookmarks(bookmarks)
            self.edited.emit(self.get_bookmarks())

        def import_current_bookmarks(imported):
            if imported.get('type') != 'bookmarks':
                return
            bookmarks = self.get_bookmarks()
            for bm in imported['entries']:
                if bm not in bookmarks:
                    bookmarks.append(bm)
            self.set_bookmarks(bookmarks)
            self.edited.emit(self.get_bookmarks())

        if imported is not None:
            if isinstance(imported, list):
                import_old_bookmarks(imported)
            else:
                import_current_bookmarks(imported)

    def create_new_bookmark(self, pos_data):
        base_default_title = self.toc.model().title_for_current_node or _('Bookmark')
        all_titles = {bm['title'] for bm in self.get_bookmarks()}
        c = 0
        while True:
            c += 1
            default_title = f'{base_default_title} #{c}'
            if default_title not in all_titles:
                break

        title, ok = QInputDialog.getText(self, _('Add bookmark'),
                _('Enter title for bookmark:'), text=pos_data.get('selected_text') or default_title)
        title = str(title).strip()
        if not ok or not title:
            return
        title = self.uniqify_bookmark_title(title)
        cfi = (pos_data.get('selection_bounds') or {}).get('start') or pos_data['cfi']
        bm = {
            'title': title,
            'pos_type': 'epubcfi',
            'pos': cfi,
            'timestamp': utcnow().isoformat(),
        }
        bookmarks = self.get_bookmarks()
        bookmarks.append(bm)
        self.set_bookmarks(bookmarks)
        self.set_current_bookmark(bm)
        self.edited.emit(bookmarks)

    def keyPressEvent(self, ev):
        sc = get_shortcut_for(self, ev)
        if ev.key() == Qt.Key.Key_Escape or sc == 'toggle_bookmarks':
            self.toggle_requested.emit()
            return
        if sc == 'new_bookmark':
            self.create_requested.emit()
            return
        return QWidget.keyPressEvent(self, ev)
