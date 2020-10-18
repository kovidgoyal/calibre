#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt5.Qt import (
    QAction, QApplication, QDialog, QDialogButtonBox, QGridLayout, QIcon, QMenu,
    QSize, QStackedWidget, QStyledItemDelegate, Qt, QTimer, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget, pyqtSignal
)

from calibre.ebooks.oeb.polish.toc import commit_toc, get_toc
from calibre.gui2 import error_dialog, make_view_use_window_background
from calibre.gui2.toc.main import ItemEdit, TOCView
from calibre.gui2.tweak_book import TOP, actions, current_container, tprefs
from calibre_extensions.progress_indicator import set_no_activate_on_click
from polyglot.builtins import range, unicode_type


class TOCEditor(QDialog):

    explode_done = pyqtSignal(object)
    writing_done = pyqtSignal(object)

    def __init__(self, title=None, parent=None):
        QDialog.__init__(self, parent)

        t = title or current_container().mi.title
        self.book_title = t
        self.setWindowTitle(_('Edit the ToC in %s')%t)
        self.setWindowIcon(QIcon(I('toc.png')))

        l = self.l = QVBoxLayout()
        self.setLayout(l)

        self.stacks = s = QStackedWidget(self)
        l.addWidget(s)
        self.toc_view = TOCView(self, tprefs)
        self.toc_view.add_new_item.connect(self.add_new_item)
        s.addWidget(self.toc_view)
        self.item_edit = ItemEdit(self, tprefs)
        s.addWidget(self.item_edit)

        bb = self.bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        l.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.undo_button = b = bb.addButton(_('&Undo'), bb.ActionRole)
        b.setToolTip(_('Undo the last action, if any'))
        b.setIcon(QIcon(I('edit-undo.png')))
        b.clicked.connect(self.toc_view.undo)

        self.read_toc()

        self.resize(950, 630)
        geom = tprefs.get('toc_editor_window_geom', None)
        if geom is not None:
            QApplication.instance().safe_restore_geometry(self, bytes(geom))

    def add_new_item(self, item, where):
        self.item_edit(item, where)
        self.stacks.setCurrentIndex(1)

    def accept(self):
        if self.stacks.currentIndex() == 1:
            self.toc_view.update_item(*self.item_edit.result)
            tprefs['toc_edit_splitter_state'] = bytearray(self.item_edit.splitter.saveState())
            self.stacks.setCurrentIndex(0)
        elif self.stacks.currentIndex() == 0:
            self.write_toc()
            tprefs['toc_editor_window_geom'] = bytearray(self.saveGeometry())
            super(TOCEditor, self).accept()

    def really_accept(self, tb):
        tprefs['toc_editor_window_geom'] = bytearray(self.saveGeometry())
        if tb:
            error_dialog(self, _('Failed to write book'),
                _('Could not write %s. Click "Show details" for'
                  ' more information.')%self.book_title, det_msg=tb, show=True)
            super(TOCEditor, self).reject()
            return

        super(TOCEditor, self).accept()

    def reject(self):
        if not self.bb.isEnabled():
            return
        if self.stacks.currentIndex() == 1:
            tprefs['toc_edit_splitter_state'] = bytearray(self.item_edit.splitter.saveState())
            self.stacks.setCurrentIndex(0)
        else:
            tprefs['toc_editor_window_geom'] = bytearray(self.saveGeometry())
            super(TOCEditor, self).reject()

    def read_toc(self):
        self.toc_view(current_container())
        self.item_edit.load(current_container())
        self.stacks.setCurrentIndex(0)

    def write_toc(self):
        toc = self.toc_view.create_toc()
        toc.toc_title = getattr(self.toc_view, 'toc_title', None)
        commit_toc(current_container(), toc, lang=self.toc_view.toc_lang,
                uid=self.toc_view.toc_uid)


DEST_ROLE = Qt.UserRole
FRAG_ROLE = DEST_ROLE + 1


class Delegate(QStyledItemDelegate):

    def sizeHint(self, *args):
        ans = QStyledItemDelegate.sizeHint(self, *args)
        return ans + QSize(0, 10)


class TOCViewer(QWidget):

    navigate_requested = pyqtSignal(object, object)
    refresh_requested = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.l = l = QGridLayout(self)
        self.toc_title = None
        self.setLayout(l)
        l.setContentsMargins(0, 0, 0, 0)

        self.view = make_view_use_window_background(QTreeWidget(self))
        self.delegate = Delegate(self.view)
        self.view.setItemDelegate(self.delegate)
        self.view.setHeaderHidden(True)
        self.view.setAnimated(True)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.show_context_menu, type=Qt.QueuedConnection)
        self.view.itemActivated.connect(self.emit_navigate)
        self.view.itemPressed.connect(self.item_pressed)
        set_no_activate_on_click(self.view)
        self.view.itemDoubleClicked.connect(self.emit_navigate)
        l.addWidget(self.view)

        self.refresh_action = QAction(QIcon(I('view-refresh.png')), _('&Refresh'), self)
        self.refresh_action.triggered.connect(self.refresh)
        self.refresh_timer = t = QTimer(self)
        t.setInterval(1000), t.setSingleShot(True)
        t.timeout.connect(self.auto_refresh)
        self.toc_name = None
        self.currently_editing = None

    def start_refresh_timer(self, name):
        if self.isVisible() and self.toc_name == name:
            self.refresh_timer.start()

    def auto_refresh(self):
        if self.isVisible():
            try:
                self.refresh()
            except Exception:
                # ignore errors during live refresh of the toc
                import traceback
                traceback.print_exc()

    def refresh(self):
        self.refresh_requested.emit()  # Give boss a chance to commit dirty editors to the container
        self.build()

    def item_pressed(self, item):
        if QApplication.mouseButtons() & Qt.LeftButton:
            QTimer.singleShot(0, self.emit_navigate)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.addAction(actions['edit-toc'])
        menu.addAction(_('&Expand all'), self.view.expandAll)
        menu.addAction(_('&Collapse all'), self.view.collapseAll)
        menu.addAction(self.refresh_action)
        menu.exec_(self.view.mapToGlobal(pos))

    def iter_items(self, parent=None):
        if parent is None:
            parent = self.invisibleRootItem()
        for i in range(parent.childCount()):
            child = parent.child(i)
            yield child
            for gc in self.iter_items(parent=child):
                yield gc

    def emit_navigate(self, *args):
        item = self.view.currentItem()
        if item is not None:
            dest = unicode_type(item.data(0, DEST_ROLE) or '')
            frag = unicode_type(item.data(0, FRAG_ROLE) or '')
            if not frag:
                frag = TOP
            self.navigate_requested.emit(dest, frag)

    def build(self):
        c = current_container()
        if c is None:
            return
        toc = get_toc(c, verify_destinations=False)
        self.toc_name = getattr(toc, 'toc_file_name', None)
        self.toc_title = toc.toc_title

        def process_node(toc, parent):
            for child in toc:
                node = QTreeWidgetItem(parent)
                node.setText(0, child.title or '')
                node.setData(0, DEST_ROLE, child.dest or '')
                node.setData(0, FRAG_ROLE, child.frag or '')
                tt = _('File: {0}\nAnchor: {1}').format(
                    child.dest or '', child.frag or _('Top of file'))
                node.setData(0, Qt.ToolTipRole, tt)
                process_node(child, node)

        self.view.clear()
        process_node(toc, self.view.invisibleRootItem())

    def showEvent(self, ev):
        if self.toc_name is None or not ev.spontaneous():
            self.build()
        return super(TOCViewer, self).showEvent(ev)

    def update_if_visible(self):
        if self.isVisible():
            self.build()
