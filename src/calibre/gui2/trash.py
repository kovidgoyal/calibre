#!/usr/bin/env python
# License: GPLv3 Copyright: 2023, Kovid Goyal <kovid at kovidgoyal.net>

import time
import traceback
from operator import attrgetter
from typing import Iterator, List

from qt.core import (
    QAbstractItemView,
    QDialogButtonBox,
    QHBoxLayout,
    QIcon,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPainter,
    QPalette,
    QPixmap,
    QRectF,
    QSize,
    QSpinBox,
    QStyle,
    QStyledItemDelegate,
    Qt,
    QTabWidget,
    QVBoxLayout,
    pyqtSignal,
)

from calibre import fit_image
from calibre.db.constants import DEFAULT_TRASH_EXPIRY_TIME_SECONDS, TrashEntry
from calibre.gui2 import choose_dir, choose_save_file, error_dialog
from calibre.gui2.dialogs.confirm_delete import confirm
from calibre.gui2.widgets import BusyCursor
from calibre.gui2.widgets2 import Dialog

THUMBNAIL_SIZE = 60, 80
MARGIN_SIZE = 8


def time_spec(mtime: float) -> str:
    delta = time.time() - mtime
    if delta <= 86400:
        if delta <= 3600:
            return _('less than an hour ago')
        return _('{} hours ago').format(int(delta) // 3600)
    else:
        return _('{} days ago').format(int(delta) // 86400)


class TrashItemDelegate(QStyledItemDelegate):

    def __init__(self, parent):
        super().__init__(parent)
        self.pixmap_cache = {}

    def sizeHint(self, option, index):
        return QSize(THUMBNAIL_SIZE[0] + MARGIN_SIZE + 256, THUMBNAIL_SIZE[1] + MARGIN_SIZE)

    def paint(self, painter: QPainter, option, index):
        super().paint(painter, option, index)
        painter.save()
        entry: TrashEntry = index.data(Qt.ItemDataRole.UserRole)
        if option is not None and option.state & QStyle.StateFlag.State_Selected:
            p = option.palette
            group = (QPalette.ColorGroup.Active if option.state & QStyle.StateFlag.State_Active else
                    QPalette.ColorGroup.Inactive)
            c = p.color(group, QPalette.ColorRole.HighlightedText)
            painter.setPen(c)

        text = entry.title + '\n' + entry.author + '\n' + _('Deleted: {when}').format(when=time_spec(entry.mtime))
        if entry.formats:
            text += '\n' + ', '.join(sorted(entry.formats))
        r = QRectF(option.rect)
        if entry.cover_path:
            dp = self.parent().devicePixelRatioF()
            p = self.pixmap_cache.get(entry.cover_path)
            if p is None:
                p = QPixmap()
                p.load(entry.cover_path)
                scaled, w, h = fit_image(p.width(), p.height(), int(THUMBNAIL_SIZE[0] * dp), int(THUMBNAIL_SIZE[1] * dp))
                if scaled:
                    p = p.scaled(w, h, transformMode=Qt.TransformationMode.SmoothTransformation)
                p.setDevicePixelRatio(self.parent().devicePixelRatioF())
                self.pixmap_cache[entry.cover_path] = p
            w, h = p.width() / dp, p.height() / dp
            width, height = THUMBNAIL_SIZE[0] + MARGIN_SIZE, THUMBNAIL_SIZE[1] + MARGIN_SIZE
            pos = r.topLeft()
            if width > w:
                pos.setX(pos.x() + (width - w) / 2)
            if height > h:
                pos.setY(pos.y() + (height - h) / 2)
            painter.drawPixmap(pos, p)
        r.adjust(THUMBNAIL_SIZE[0] + MARGIN_SIZE, 0, 0, 0)
        painter.drawText(r, Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop, text)
        painter.restore()


class TrashList(QListWidget):

    restore_item = pyqtSignal(object, object)

    def __init__(self, entries: List[TrashEntry], parent: 'TrashView', is_books: bool):
        super().__init__(parent)
        self.is_books = is_books
        self.db = parent.db
        self.delegate = TrashItemDelegate(self)
        self.setItemDelegate(self.delegate)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for entry in sorted(entries, key=attrgetter('mtime'), reverse=True):
            i = QListWidgetItem(self)
            i.setData(Qt.ItemDataRole.UserRole, entry)
            self.addItem(i)
        self.itemDoubleClicked.connect(self.double_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    @property
    def selected_entries(self) -> Iterator[TrashEntry]:
        for i in self.selectedItems():
            yield i.data(Qt.ItemDataRole.UserRole)

    def double_clicked(self, item):
        self.restore_item.emit(self, item)

    def show_context_menu(self, pos):
        item = self.itemAt(pos)
        if item is None:
            return
        m = QMenu(self)
        entry = item.data(Qt.ItemDataRole.UserRole)
        m.addAction(QIcon.ic('save.png'), _('Save "{}" to disk').format(entry.title)).triggered.connect(self.save_current_item)
        m.exec(self.mapToGlobal(pos))

    def save_current_item(self):
        item = self.currentItem()
        if item is not None:
            self.save_entry(item.data(Qt.ItemDataRole.UserRole))

    def save_entry(self, entry: TrashEntry):
        if self.is_books:
            dest = choose_dir(self, 'save-trash-book', _('Choose a location to save: {}').format(entry.title))
            if not dest:
                return
            self.db.copy_book_from_trash(entry.book_id, dest)
        else:
            for fmt in entry.formats:
                dest = choose_save_file(self, 'save-trash-format', _('Choose a location to save: {}').format(
                    entry.title +'.' + fmt.lower()), initial_filename=entry.title + '.' + fmt.lower())
                if dest:
                    self.db.copy_format_from_trash(entry.book_id, fmt, dest)


class TrashView(Dialog):

    books_restored = pyqtSignal(object)

    def __init__(self, db, parent=None):
        self.db = db.new_api
        self.expire_on_close = False
        self.formats_restored = set()
        super().__init__(_('Recently deleted books'), 'trash-view-for-library', parent=parent, default_buttons=QDialogButtonBox.StandardButton.Close)
        self.finished.connect(self.expire_old_trash)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.setWindowIcon(QIcon.ic('trash.png'))

        with BusyCursor():
            books, formats = self.db.list_trash_entries()
        self.books = TrashList(books, self, True)
        self.books.restore_item.connect(self.restore_item)
        self.formats = TrashList(formats, self, False)
        self.formats.restore_item.connect(self.restore_item)

        self.tabs = t = QTabWidget(self)
        l.addWidget(t)
        t.addTab(self.books, QIcon.ic('book.png'), 'books')
        t.addTab(self.formats, QIcon.ic('mimetypes/zero.png'), 'formats')

        la = QLabel(_('&Permanently delete after:'))
        self.auto_delete = ad = QSpinBox(self)
        ad.setMinimum(0)
        ad.setMaximum(365)
        ad.setSpecialValueText(_('on close'))
        ad.setValue(int(self.db.pref('expire_old_trash_after', DEFAULT_TRASH_EXPIRY_TIME_SECONDS) / 86400))
        ad.setSuffix(_(' days'))
        ad.setToolTip(_(
            'Deleted items are permanently deleted automatically after the specified number of days.\n'
            'If set to "on close" they are deleted whenever the library is closed, that is when switching to another library or exiting calibre.'
        ))
        ad.valueChanged.connect(self.trash_expiry_time_changed)
        h = QHBoxLayout()
        h.addWidget(la), h.addWidget(ad), h.addStretch(10)
        la.setBuddy(ad)
        l.addLayout(h)

        h = QHBoxLayout()
        l.addWidget(self.bb)
        self.restore_button = b = self.bb.addButton(_('&Restore selected'), QDialogButtonBox.ButtonRole.ActionRole)
        b.clicked.connect(self.restore_selected)
        b.setIcon(QIcon.ic('edit-undo.png'))
        self.delete_button = b = self.bb.addButton(_('Permanently &delete selected'), QDialogButtonBox.ButtonRole.ActionRole)
        b.setToolTip(_('Remove the selected entries from the trash bin, thereby deleting them permanently'))
        b.setIcon(QIcon.ic('edit-clear.png'))
        b.clicked.connect(self.delete_selected)
        self.clear_button = b = self.bb.addButton(_('&Clear'), QDialogButtonBox.ButtonRole.ResetRole)
        b.clicked.connect(self.clear_all)
        b.setIcon(QIcon.ic('dialog_warning.png'))
        self.update_titles()
        self.bb.button(QDialogButtonBox.StandardButton.Close).setFocus(Qt.FocusReason.OtherFocusReason)

    def clear_all(self):
        if not confirm('<p>'+_('All books and formats will be <b>permanently deleted</b>! Are you sure?'), 'clear_trash_bin', self):
            return
        self.db.clear_trash_bin()
        self.books.clear()
        self.formats.clear()
        self.update_titles()

    def update_titles(self):
        self.tabs.setTabText(0, _('&Books ({})').format(self.books.count()))
        self.tabs.setTabText(1, _('&Formats ({})').format(self.formats.count()))

    def trash_expiry_time_changed(self, val):
        self.db.set_pref('expire_old_trash_after', 86400 * self.auto_delete.value())
        self.expire_on_close = True

    def expire_old_trash(self):
        if self.expire_on_close:
            self.db.expire_old_trash()

    def sizeHint(self):
        return QSize(530, 650)

    def do_operation_on_selected(self, func):
        ok_items, failed_items = [], []
        for i in self.tabs.currentWidget().selectedItems():
            entry = i.data(Qt.ItemDataRole.UserRole)
            try:
                func(entry)
            except Exception as e:
                failed_items.append((entry, e, traceback.format_exc()))
            else:
                ok_items.append(i)
        return ok_items, failed_items

    @property
    def books_tab_is_selected(self):
        return self.tabs.currentWidget() is self.books

    def restore_item(self, which, item):
        is_books = which is self.books
        entry = item.data(Qt.ItemDataRole.UserRole)
        if is_books:
            self.db.move_book_from_trash(entry.book_id)
            self.books_restored.emit({entry.book_id})
        else:
            self.formats_restored.add(entry.book_id)
            for fmt in entry.formats:
                self.db.move_format_from_trash(entry.book_id, fmt)
        self.remove_entries([item])

    def restore_selected(self):
        is_books = self.books_tab_is_selected
        done = set()

        def f(entry):
            if is_books:
                self.db.move_book_from_trash(entry.book_id)
                done.add(entry.book_id)
            else:
                self.formats_restored.add(entry.book_id)
                for fmt in entry.formats:
                    self.db.move_format_from_trash(entry.book_id, fmt)

        ok, failed = self.do_operation_on_selected(f)
        if done:
            self.books_restored.emit(done)
        self.remove_entries(ok)
        self.show_failures(failed, _('restore'))

    def remove_entries(self, remove):
        w = self.tabs.currentWidget()
        for i in remove:
            w.takeItem(w.row(i))
        self.update_titles()

    def delete_selected(self):
        category = 'b' if self.books_tab_is_selected else 'f'

        def f(entry):
            self.db.delete_trash_entry(entry.book_id, category)
        ok, failed = self.do_operation_on_selected(f)
        self.remove_entries(ok)
        self.show_failures(failed, _('delete'))

    def show_failures(self, failures, operation):
        if not failures:
            return
        det_msg = []
        for (entry, exc, tb) in failures:
            det_msg.append(_('Failed for the book {} with error:').format(entry.title))
            det_msg.append(tb)
            det_msg.append('-' * 40)
            det_msg.append('')
        det_msg = det_msg[:-2]
        entry_type = _('Books') if self.books_tab_is_selected else _('Formats')
        error_dialog(
            self, _('Failed to process some {}').format(entry_type),
            _('Could not {0} some {1}. Click "Show details" for details.').format(operation, entry_type),
            det_msg='\n'.join(det_msg), show=True)




if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.library import db
    app = Application([])
    TrashView(db()).exec()
    del app
