#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import sys, os
from functools import partial

from PyQt5.Qt import (
    QGridLayout, QSize, QListView, QStyledItemDelegate, QLabel, QPixmap,
    QApplication, QSizePolicy, QAbstractListModel, Qt, QRect, QCheckBox,
    QPainter, QSortFilterProxyModel, QLineEdit, QToolButton,
    QIcon, QFormLayout, pyqtSignal, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
    QMenu, QInputDialog, QHBoxLayout)

from calibre import fit_image
from calibre.constants import plugins
from calibre.ebooks.metadata import string_to_authors
from calibre.ebooks.metadata.book.base import Metadata
from calibre.gui2 import choose_files, error_dialog, pixmap_to_data, empty_index
from calibre.gui2.languages import LanguagesEdit
from calibre.gui2.tweak_book import current_container, tprefs
from calibre.gui2.tweak_book.widgets import Dialog
from calibre.gui2.tweak_book.file_list import name_is_ok
from calibre.ptempfile import PersistentTemporaryFile
from calibre.utils.localization import get_lang, canonicalize_lang
from calibre.utils.icu import sort_key


class ChooseName(Dialog):  # {{{

    ''' Chooses the filename for a newly imported file, with error checking '''

    def __init__(self, candidate, parent=None):
        self.candidate = candidate
        self.filename = None
        Dialog.__init__(self, _('Choose file name'), 'choose-file-name', parent=parent)

    def setup_ui(self):
        self.l = l = QFormLayout(self)
        self.setLayout(l)

        self.err_label = QLabel('')
        self.name_edit = QLineEdit(self)
        self.name_edit.textChanged.connect(self.verify)
        self.name_edit.setText(self.candidate)
        pos = self.candidate.rfind('.')
        if pos > -1:
            self.name_edit.setSelection(0, pos)
        l.addRow(_('File &name:'), self.name_edit)
        l.addRow(self.err_label)
        l.addRow(self.bb)

    def show_error(self, msg):
        self.err_label.setText('<p style="color:red">' + msg)
        return False

    def verify(self):
        return name_is_ok(unicode(self.name_edit.text()), self.show_error)

    def accept(self):
        if not self.verify():
            return error_dialog(self, _('No name specified'), _(
                'You must specify a file name for the new file, with an extension.'), show=True)
        n = unicode(self.name_edit.text()).replace('\\', '/')
        name, ext = n.rpartition('.')[0::2]
        self.filename = name + '.' + ext.lower()
        super(ChooseName, self).accept()
# }}}

# Images {{{


class ImageDelegate(QStyledItemDelegate):

    MARGIN = 4

    def __init__(self, parent):
        super(ImageDelegate, self).__init__(parent)
        self.set_dimensions()
        self.cover_cache = {}

    def set_dimensions(self):
        width, height = 120, 160
        self.cover_size = QSize(width, height)
        f = self.parent().font()
        sz = f.pixelSize()
        if sz < 5:
            sz = f.pointSize() * self.parent().logicalDpiY() / 72.0
        self.title_height = max(25, sz + 10)
        self.item_size = self.cover_size + QSize(2 * self.MARGIN, (2 * self.MARGIN) + self.title_height)
        self.calculate_spacing()

    def calculate_spacing(self):
        self.spacing = max(10, min(50, int(0.1 * self.item_size.width())))

    def sizeHint(self, option, index):
        return self.item_size

    def paint(self, painter, option, index):
        QStyledItemDelegate.paint(self, painter, option, empty_index)  # draw the hover and selection highlights
        name = unicode(index.data(Qt.DisplayRole) or '')
        cover = self.cover_cache.get(name, None)
        if cover is None:
            cover = self.cover_cache[name] = QPixmap()
            try:
                raw = current_container().raw_data(name, decode=False)
            except:
                pass
            else:
                try:
                    dpr = painter.device().devicePixelRatioF()
                except AttributeError:
                    dpr = painter.device().devicePixelRatio()
                cover.loadFromData(raw)
                cover.setDevicePixelRatio(dpr)
                if not cover.isNull():
                    scaled, width, height = fit_image(cover.width(), cover.height(), self.cover_size.width(), self.cover_size.height())
                    if scaled:
                        cover = self.cover_cache[name] = cover.scaled(int(dpr*width), int(dpr*height), transformMode=Qt.SmoothTransformation)

        painter.save()
        try:
            rect = option.rect
            rect.adjust(self.MARGIN, self.MARGIN, -self.MARGIN, -self.MARGIN)
            trect = QRect(rect)
            rect.setBottom(rect.bottom() - self.title_height)
            if not cover.isNull():
                dx = max(0, int((rect.width() - int(cover.width()/cover.devicePixelRatio()))/2.0))
                dy = max(0, rect.height() - int(cover.height()/cover.devicePixelRatio()))
                rect.adjust(dx, dy, -dx, 0)
                painter.drawPixmap(rect, cover)
            rect = trect
            rect.setTop(rect.bottom() - self.title_height + 5)
            painter.setRenderHint(QPainter.TextAntialiasing, True)
            metrics = painter.fontMetrics()
            painter.drawText(rect, Qt.AlignCenter|Qt.TextSingleLine,
                                metrics.elidedText(name, Qt.ElideLeft, rect.width()))
        finally:
            painter.restore()


class Images(QAbstractListModel):

    def __init__(self, parent):
        QAbstractListModel.__init__(self, parent)
        self.icon_size = parent.iconSize()
        self.build()

    def build(self):
        c = current_container()
        self.image_names = []
        self.image_cache = {}
        if c is not None:
            for name in sorted(c.mime_map, key=sort_key):
                if c.mime_map[name].startswith('image/'):
                    self.image_names.append(name)

    def refresh(self):
        from calibre.gui2.tweak_book.boss import get_boss
        boss = get_boss()
        boss.commit_all_editors_to_container()
        self.beginResetModel()
        self.build()
        self.endResetModel()

    def rowCount(self, *args):
        return len(self.image_names)

    def data(self, index, role):
        try:
            name = self.image_names[index.row()]
        except IndexError:
            return None
        if role in (Qt.DisplayRole, Qt.ToolTipRole):
            return name
        return None


class InsertImage(Dialog):

    image_activated = pyqtSignal(object)

    def __init__(self, parent=None, for_browsing=False):
        self.for_browsing = for_browsing
        Dialog.__init__(self, _('Images in book') if for_browsing else _('Choose an image'),
                        'browse-image-dialog' if for_browsing else 'insert-image-dialog', parent)
        self.chosen_image = None
        self.chosen_image_is_external = False

    def sizeHint(self):
        return QSize(800, 600)

    def setup_ui(self):
        self.l = l = QGridLayout(self)
        self.setLayout(l)

        self.la1 = la = QLabel(_('&Existing images in the book'))
        la.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        l.addWidget(la, 0, 0, 1, 2)
        if self.for_browsing:
            la.setVisible(False)

        self.view = v = QListView(self)
        v.setViewMode(v.IconMode)
        v.setFlow(v.LeftToRight)
        v.setSpacing(4)
        v.setResizeMode(v.Adjust)
        v.setUniformItemSizes(True)
        pi = plugins['progress_indicator'][0]
        if hasattr(pi, 'set_no_activate_on_click'):
            pi.set_no_activate_on_click(v)
        v.activated.connect(self.activated)
        v.doubleClicked.connect(self.activated)
        self.d = ImageDelegate(v)
        v.setItemDelegate(self.d)
        self.model = Images(self.view)
        self.fm = fm = QSortFilterProxyModel(self.view)
        self.fm.setDynamicSortFilter(self.for_browsing)
        fm.setSourceModel(self.model)
        fm.setFilterCaseSensitivity(False)
        v.setModel(fm)
        l.addWidget(v, 1, 0, 1, 2)
        v.pressed.connect(self.pressed)
        la.setBuddy(v)

        self.filter = f = QLineEdit(self)
        f.setPlaceholderText(_('Search for image by file name'))
        l.addWidget(f, 2, 0)
        self.cb = b = QToolButton(self)
        b.setIcon(QIcon(I('clear_left.png')))
        b.clicked.connect(f.clear)
        l.addWidget(b, 2, 1)
        f.textChanged.connect(self.filter_changed)

        if self.for_browsing:
            self.bb.clear()
            self.bb.addButton(self.bb.Close)
            b = self.refresh_button = self.bb.addButton(_('&Refresh'), self.bb.ActionRole)
            b.clicked.connect(self.refresh)
            b.setIcon(QIcon(I('view-refresh.png')))
            b.setToolTip(_('Refresh the displayed images'))
            self.setAttribute(Qt.WA_DeleteOnClose, False)
        else:
            b = self.import_button = self.bb.addButton(_('&Import image'), self.bb.ActionRole)
            b.clicked.connect(self.import_image)
            b.setIcon(QIcon(I('view-image.png')))
            b.setToolTip(_('Import an image from elsewhere in your computer'))
            b = self.paste_button = self.bb.addButton(_('&Paste image'), self.bb.ActionRole)
            b.clicked.connect(self.paste_image)
            b.setIcon(QIcon(I('edit-paste.png')))
            b.setToolTip(_('Paste an image from the clipboard'))
            self.fullpage = f = QCheckBox(_('Full page image'), self)
            f.setToolTip(_('Insert the image so that it takes up an entire page when viewed in a reader'))
            f.setChecked(tprefs['insert_full_screen_image'])
            self.preserve_aspect_ratio = a = QCheckBox(_('Preserve aspect ratio'))
            a.setToolTip(_('Preserve the aspect ratio of the inserted image when rendering it full paged'))
            a.setChecked(tprefs['preserve_aspect_ratio_when_inserting_image'])
            f.toggled.connect(lambda : (tprefs.set('insert_full_screen_image', f.isChecked()), a.setVisible(f.isChecked())))
            a.toggled.connect(lambda : tprefs.set('preserve_aspect_ratio_when_inserting_image', a.isChecked()))
            a.setVisible(f.isChecked())
            h = QHBoxLayout()
            l.addLayout(h, 3, 0, 1, -1)
            h.addWidget(f), h.addStretch(10), h.addWidget(a)
        l.addWidget(self.bb, 4, 0, 1, 2)

    def refresh(self):
        self.d.cover_cache.clear()
        self.model.refresh()

    def import_image(self):
        path = choose_files(self, 'tweak-book-choose-image-for-import', _('Choose image'),
                            filters=[(_('Images'), ('jpg', 'jpeg', 'png', 'gif', 'svg'))], all_files=True, select_only_single_file=True)
        if path:
            path = path[0]
            basename = os.path.basename(path)
            n, e = basename.rpartition('.')[0::2]
            basename = n + '.' + e.lower()
            d = ChooseName(basename, self)
            if d.exec_() == d.Accepted and d.filename:
                self.accept()
                self.chosen_image_is_external = (d.filename, path)

    def paste_image(self):
        c = QApplication.instance().clipboard()
        img = c.image()
        if img.isNull():
            img = c.image(c.Selection)
        if img.isNull():
            return error_dialog(self, _('No image'), _(
                'There is no image on the clipboard'), show=True)
        d = ChooseName('image.jpg', self)
        if d.exec_() == d.Accepted and d.filename:
            fmt = d.filename.rpartition('.')[-1].lower()
            if fmt not in {'jpg', 'jpeg', 'png'}:
                return error_dialog(self, _('Invalid file extension'), _(
                    'The file name you choose must have a .jpg or .png extension'), show=True)
            t = PersistentTemporaryFile(prefix='editor-paste-image-', suffix='.' + fmt)
            t.write(pixmap_to_data(img, fmt))
            t.close()
            self.chosen_image_is_external = (d.filename, t.name)
            self.accept()

    def pressed(self, index):
        if QApplication.mouseButtons() & Qt.LeftButton:
            self.activated(index)

    def activated(self, index):
        if self.for_browsing:
            return self.image_activated.emit(unicode(index.data() or ''))
        self.chosen_image_is_external = False
        self.accept()

    def accept(self):
        self.chosen_image = unicode(self.view.currentIndex().data() or '')
        super(InsertImage, self).accept()

    def filter_changed(self, *args):
        f = unicode(self.filter.text())
        self.fm.setFilterFixedString(f)
# }}}


def get_resource_data(rtype, parent):
    if rtype == 'image':
        d = InsertImage(parent)
        if d.exec_() == d.Accepted:
            return d.chosen_image, d.chosen_image_is_external, d.fullpage.isChecked(), d.preserve_aspect_ratio.isChecked()


def create_folder_tree(container):
    root = {}

    all_folders = {tuple(x.split('/')[:-1]) for x in container.name_path_map}
    all_folders.discard(())

    for folder_path in all_folders:
        current = root
        for x in folder_path:
            current[x] = current = current.get(x, {})
    return root


class ChooseFolder(Dialog):  # {{{

    def __init__(self, msg=None, parent=None):
        self.msg = msg
        Dialog.__init__(self, _('Choose folder'), 'choose-folder', parent=parent)

    def setup_ui(self):
        self.l = l = QVBoxLayout(self)
        self.setLayout(l)

        self.msg = m = QLabel(self.msg or _(
        'Choose the folder into which the files will be placed'))
        l.addWidget(m)
        m.setWordWrap(True)

        self.folders = f = QTreeWidget(self)
        f.setHeaderHidden(True)
        f.itemDoubleClicked.connect(self.accept)
        l.addWidget(f)
        f.setContextMenuPolicy(Qt.CustomContextMenu)
        f.customContextMenuRequested.connect(self.show_context_menu)
        self.root = QTreeWidgetItem(f, ('/',))

        def process(node, parent):
            parent.setIcon(0, QIcon(I('mimetypes/dir.png')))
            for child in sorted(node, key=sort_key):
                c = QTreeWidgetItem(parent, (child,))
                process(node[child], c)
        process(create_folder_tree(current_container()), self.root)
        self.root.setSelected(True)
        f.expandAll()

        l.addWidget(self.bb)

    def show_context_menu(self, point):
        item = self.folders.itemAt(point)
        if item is None:
            return
        m = QMenu(self)
        m.addAction(QIcon(I('mimetypes/dir.png')), _('Create new folder'), partial(self.create_folder, item))
        m.popup(self.folders.mapToGlobal(point))

    def create_folder(self, item):
        text, ok = QInputDialog.getText(self, _('Folder name'), _('Enter a name for the new folder'))
        if ok and unicode(text):
            c = QTreeWidgetItem(item, (unicode(text),))
            c.setIcon(0, QIcon(I('mimetypes/dir.png')))
            for item in self.folders.selectedItems():
                item.setSelected(False)
            c.setSelected(True)
            self.folders.setCurrentItem(c)

    def folder_path(self, item):
        ans = []
        while item is not self.root:
            ans.append(unicode(item.text(0)))
            item = item.parent()
        return tuple(reversed(ans))

    @property
    def chosen_folder(self):
        try:
            return '/'.join(self.folder_path(self.folders.selectedItems()[0]))
        except IndexError:
            return ''
# }}}


class NewBook(Dialog):  # {{{

    def __init__(self, parent=None):
        self.fmt = 'epub'
        Dialog.__init__(self, _('Create new book'), 'create-new-book', parent=parent)

    def setup_ui(self):
        self.l = l = QFormLayout(self)
        self.setLayout(l)

        self.title = t = QLineEdit(self)
        l.addRow(_('&Title:'), t)
        t.setFocus(Qt.OtherFocusReason)

        self.authors = a = QLineEdit(self)
        l.addRow(_('&Authors:'), a)
        a.setText(tprefs.get('previous_new_book_authors', ''))

        self.languages = la = LanguagesEdit(self)
        l.addRow(_('&Language:'), la)
        la.lang_codes = (tprefs.get('previous_new_book_lang', canonicalize_lang(get_lang())),)

        bb = self.bb
        l.addRow(bb)
        bb.clear()
        bb.addButton(bb.Cancel)
        b = bb.addButton('&EPUB', bb.AcceptRole)
        b.clicked.connect(partial(self.set_fmt, 'epub'))
        b = bb.addButton('&AZW3', bb.AcceptRole)
        b.clicked.connect(partial(self.set_fmt, 'azw3'))

    def set_fmt(self, fmt):
        self.fmt = fmt

    def accept(self):
        with tprefs:
            tprefs.set('previous_new_book_authors', unicode(self.authors.text()))
            tprefs.set('previous_new_book_lang', (self.languages.lang_codes or [get_lang()])[0])
            self.languages.update_recently_used()
        super(NewBook, self).accept()

    @property
    def mi(self):
        mi = Metadata(unicode(self.title.text()).strip() or _('Unknown'))
        mi.authors = string_to_authors(unicode(self.authors.text()).strip()) or [_('Unknown')]
        mi.languages = self.languages.lang_codes or [get_lang()]
        return mi

# }}}


if __name__ == '__main__':
    app = QApplication([])  # noqa
    from calibre.gui2.tweak_book import set_current_container
    from calibre.gui2.tweak_book.boss import get_container
    set_current_container(get_container(sys.argv[-1]))

    d = InsertImage(for_browsing=True)
    d.exec_()
