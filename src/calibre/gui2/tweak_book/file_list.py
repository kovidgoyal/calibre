#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2013, Kovid Goyal <kovid at kovidgoyal.net>
from __future__ import absolute_import, division, print_function, unicode_literals

import os
import posixpath
from binascii import hexlify
from collections import Counter, OrderedDict, defaultdict
from functools import partial

import sip
from PyQt5.Qt import (
    QCheckBox, QDialog, QDialogButtonBox, QFont, QFormLayout, QGridLayout, QIcon,
    QInputDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMenu, QPainter,
    QPixmap, QRadioButton, QScrollArea, QSize, QSpinBox, QStyle, QStyledItemDelegate,
    Qt, QTimer, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget, pyqtSignal
)

from calibre import human_readable, plugins, sanitize_file_name_unicode
from calibre.ebooks.oeb.base import OEB_DOCS, OEB_STYLES
from calibre.ebooks.oeb.polish.container import OEB_FONTS, guess_type
from calibre.ebooks.oeb.polish.cover import (
    get_cover_page_name, get_raster_cover_name, is_raster_image
)
from calibre.ebooks.oeb.polish.replace import get_recommended_folders
from calibre.gui2 import (
    choose_dir, choose_files, choose_save_file, elided_text, error_dialog,
    question_dialog
)
from calibre.gui2.tweak_book import (
    CONTAINER_DND_MIMETYPE, current_container, editors, tprefs
)
from calibre.gui2.tweak_book.editor import syntax_from_mime
from calibre.gui2.tweak_book.templates import template_for
from calibre.utils.icu import sort_key

TOP_ICON_SIZE = 24
NAME_ROLE = Qt.UserRole
CATEGORY_ROLE = NAME_ROLE + 1
LINEAR_ROLE = CATEGORY_ROLE + 1
MIME_ROLE = LINEAR_ROLE + 1
NBSP = '\xa0'

CATEGORIES = (
    ('text', _('Text'), _('Chapter-')),
    ('styles', _('Styles'), _('Style-')),
    ('images', _('Images'), _('Image-')),
    ('fonts', _('Fonts'), _('Font-')),
    ('misc', _('Miscellaneous'), _('Misc-')),
)


def name_is_ok(name, show_error):
    if not name or not name.strip():
        return show_error('') and False
    ext = name.rpartition('.')[-1]
    if not ext or ext == name:
        return show_error(_('The file name must have an extension')) and False
    norm = name.replace('\\', '/')
    parts = name.split('/')
    for x in parts:
        if sanitize_file_name_unicode(x) != x:
            return show_error(_('The file name contains invalid characters')) and False
    if current_container().has_name(norm):
        return show_error(_('This file name already exists in the book')) and False
    show_error('')
    return True


def get_bulk_rename_settings(parent, number, msg=None, sanitize=sanitize_file_name_unicode, leading_zeros=True, prefix=None, category='text'):  # {{{
    d = QDialog(parent)
    d.setWindowTitle(_('Bulk rename items'))
    d.l = l = QFormLayout(d)
    d.setLayout(l)
    d.prefix = p = QLineEdit(d)
    default_prefix = {k:v for k, __, v in CATEGORIES}.get(category, _('Chapter-'))
    previous = tprefs.get('file-list-bulk-rename-prefix', {})
    prefix = prefix or previous.get(category, default_prefix)
    p.setText(prefix)
    p.selectAll()
    d.la = la = QLabel(msg or _(
        'All selected files will be renamed to the form prefix-number'))
    l.addRow(la)
    l.addRow(_('&Prefix:'), p)
    d.num = num = QSpinBox(d)
    num.setMinimum(0), num.setValue(1), num.setMaximum(1000)
    l.addRow(_('Starting &number:'), num)
    d.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    bb.accepted.connect(d.accept), bb.rejected.connect(d.reject)
    l.addRow(bb)

    if d.exec_() == d.Accepted:
        prefix = sanitize(unicode(d.prefix.text()))
        previous[category] = prefix
        tprefs.set('file-list-bulk-rename-prefix', previous)
        num = d.num.value()
        fmt = '%d'
        if leading_zeros:
            largest = num + number - 1
            fmt = '%0{0}d'.format(len(str(largest)))
        return prefix + fmt, num
    return None, None
# }}}


class ItemDelegate(QStyledItemDelegate):  # {{{

    rename_requested = pyqtSignal(object, object)

    def setEditorData(self, editor, index):
        name = unicode(index.data(NAME_ROLE) or '')
        # We do this because Qt calls selectAll() unconditionally on the
        # editor, and we want only a part of the file name to be selected
        QTimer.singleShot(0, partial(self.set_editor_data, name, editor))

    def set_editor_data(self, name, editor):
        if sip.isdeleted(editor):
            return
        editor.setText(name)
        ext_pos = name.rfind('.')
        slash_pos = name.rfind('/')
        if slash_pos == -1 and ext_pos > 0:
            editor.setSelection(0, ext_pos)
        elif ext_pos > -1 and slash_pos > -1 and ext_pos > slash_pos + 1:
            editor.setSelection(slash_pos+1, ext_pos - slash_pos - 1)
        else:
            editor.selectAll()

    def setModelData(self, editor, model, index):
        newname = unicode(editor.text())
        oldname = unicode(index.data(NAME_ROLE) or '')
        if newname != oldname:
            self.rename_requested.emit(oldname, newname)

    def sizeHint(self, option, index):
        ans = QStyledItemDelegate.sizeHint(self, option, index)
        top_level = not index.parent().isValid()
        ans += QSize(0, 20 if top_level else 10)
        return ans

    def paint(self, painter, option, index):
        top_level = not index.parent().isValid()
        hover = option.state & QStyle.State_MouseOver
        if hover:
            if top_level:
                suffix = '%s(%d)' % (NBSP, index.model().rowCount(index))
            else:
                try:
                    suffix = NBSP + human_readable(current_container().filesize(unicode(index.data(NAME_ROLE) or '')))
                except EnvironmentError:
                    suffix = NBSP + human_readable(0)
            br = painter.boundingRect(option.rect, Qt.AlignRight|Qt.AlignVCenter, suffix)
        if top_level and index.row() > 0:
            option.rect.adjust(0, 5, 0, 0)
            painter.drawLine(option.rect.topLeft(), option.rect.topRight())
            option.rect.adjust(0, 1, 0, 0)
        if hover:
            option.rect.adjust(0, 0, -br.width(), 0)
        QStyledItemDelegate.paint(self, painter, option, index)
        if hover:
            option.rect.adjust(0, 0, br.width(), 0)
            painter.drawText(option.rect, Qt.AlignRight|Qt.AlignVCenter, suffix)
# }}}


class FileList(QTreeWidget):

    delete_requested = pyqtSignal(object, object)
    reorder_spine = pyqtSignal(object)
    rename_requested = pyqtSignal(object, object)
    bulk_rename_requested = pyqtSignal(object)
    edit_file = pyqtSignal(object, object, object)
    merge_requested = pyqtSignal(object, object, object)
    mark_requested = pyqtSignal(object, object)
    export_requested = pyqtSignal(object, object)
    replace_requested = pyqtSignal(object, object, object, object)
    link_stylesheets_requested = pyqtSignal(object, object, object)

    def __init__(self, parent=None):
        QTreeWidget.__init__(self, parent)
        self.categories = {}
        self.ordered_selected_indexes = False
        pi = plugins['progress_indicator'][0]
        if hasattr(pi, 'set_no_activate_on_click'):
            pi.set_no_activate_on_click(self)
        self.current_edited_name = None
        self.delegate = ItemDelegate(self)
        self.delegate.rename_requested.connect(self.rename_requested)
        self.setTextElideMode(Qt.ElideMiddle)
        self.setItemDelegate(self.delegate)
        self.setIconSize(QSize(16, 16))
        self.header().close()
        self.setDragEnabled(True)
        self.setEditTriggers(self.EditKeyPressed)
        self.setSelectionMode(self.ExtendedSelection)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(self.InternalMove)
        self.setAutoScroll(True)
        self.setAutoScrollMargin(TOP_ICON_SIZE*2)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setAutoExpandDelay(1000)
        self.setAnimated(True)
        self.setMouseTracking(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.root = self.invisibleRootItem()
        self.emblem_cache = {}
        self.rendered_emblem_cache = {}
        self.top_level_pixmap_cache = {
            name : QIcon(I(icon)).pixmap(TOP_ICON_SIZE, TOP_ICON_SIZE)
            for name, icon in {
                'text':'keyboard-prefs.png',
                'styles':'lookfeel.png',
                'fonts':'font.png',
                'misc':'mimetypes/dir.png',
                'images':'view-image.png',
            }.iteritems()}
        self.itemActivated.connect(self.item_double_clicked)

    def mimeTypes(self):
        ans = QTreeWidget.mimeTypes(self)
        ans.append(CONTAINER_DND_MIMETYPE)
        return ans

    def mimeData(self, indices):
        ans = QTreeWidget.mimeData(self, indices)
        names = (idx.data(0, NAME_ROLE) for idx in indices if idx.data(0, MIME_ROLE))
        ans.setData(CONTAINER_DND_MIMETYPE, '\n'.join(filter(None, names)).encode('utf-8'))
        return ans

    @property
    def current_name(self):
        ci = self.currentItem()
        if ci is not None:
            return unicode(ci.data(0, NAME_ROLE) or '')
        return ''

    def get_state(self):
        s = {'pos':self.verticalScrollBar().value()}
        s['expanded'] = {c for c, item in self.categories.iteritems() if item.isExpanded()}
        s['selected'] = {unicode(i.data(0, NAME_ROLE) or '') for i in self.selectedItems()}
        return s

    def set_state(self, state):
        for category, item in self.categories.iteritems():
            item.setExpanded(category in state['expanded'])
        self.verticalScrollBar().setValue(state['pos'])
        for parent in self.categories.itervalues():
            for c in (parent.child(i) for i in xrange(parent.childCount())):
                name = unicode(c.data(0, NAME_ROLE) or '')
                if name in state['selected']:
                    c.setSelected(True)

    def item_from_name(self, name):
        for parent in self.categories.itervalues():
            for c in (parent.child(i) for i in xrange(parent.childCount())):
                q = unicode(c.data(0, NAME_ROLE) or '')
                if q == name:
                    return c

    def select_name(self, name, set_as_current_index=False):
        for parent in self.categories.itervalues():
            for c in (parent.child(i) for i in xrange(parent.childCount())):
                q = unicode(c.data(0, NAME_ROLE) or '')
                c.setSelected(q == name)
                if q == name:
                    self.scrollToItem(c)
                    if set_as_current_index:
                        self.setCurrentItem(c)

    def select_names(self, names, current_name=None):
        for parent in self.categories.itervalues():
            for c in (parent.child(i) for i in xrange(parent.childCount())):
                q = unicode(c.data(0, NAME_ROLE) or '')
                c.setSelected(q in names)
                if q == current_name:
                    self.scrollToItem(c)
                    s = self.selectionModel()
                    s.setCurrentIndex(self.indexFromItem(c), s.NoUpdate)

    def mark_name_as_current(self, name):
        current = self.item_from_name(name)
        if current is not None:
            if self.current_edited_name is not None:
                ci = self.item_from_name(self.current_edited_name)
                if ci is not None:
                    ci.setData(0, Qt.FontRole, None)
            self.current_edited_name = name
            self.mark_item_as_current(current)

    def mark_item_as_current(self, item):
        font = QFont(self.font())
        font.setItalic(True)
        font.setBold(True)
        item.setData(0, Qt.FontRole, font)

    def clear_currently_edited_name(self):
        if self.current_edited_name:
            ci = self.item_from_name(self.current_edited_name)
            if ci is not None:
                ci.setData(0, Qt.FontRole, None)
        self.current_edited_name = None

    def build(self, container, preserve_state=True):
        if container is None:
            return
        if preserve_state:
            state = self.get_state()
        self.clear()
        self.root = self.invisibleRootItem()
        self.root.setFlags(Qt.ItemIsDragEnabled)
        self.categories = {}
        for category, text, __ in CATEGORIES:
            self.categories[category] = i = QTreeWidgetItem(self.root, 0)
            i.setText(0, text)
            i.setData(0, Qt.DecorationRole, self.top_level_pixmap_cache[category])
            f = i.font(0)
            f.setBold(True)
            i.setFont(0, f)
            i.setData(0, NAME_ROLE, category)
            flags = Qt.ItemIsEnabled
            if category == 'text':
                flags |= Qt.ItemIsDropEnabled
            i.setFlags(flags)

        processed, seen = {}, {}

        cover_page_name = get_cover_page_name(container)
        cover_image_name = get_raster_cover_name(container)
        manifested_names = set()
        for names in container.manifest_type_map.itervalues():
            manifested_names |= set(names)

        def get_category(name, mt):
            category = 'misc'
            if mt.startswith('image/'):
                category = 'images'
            elif mt in OEB_FONTS:
                category = 'fonts'
            elif mt in OEB_STYLES:
                category = 'styles'
            elif mt in OEB_DOCS:
                category = 'text'
            ext = name.rpartition('.')[-1].lower()
            if ext in {'ttf', 'otf', 'woff'}:
                # Probably wrong mimetype in the OPF
                category = 'fonts'
            return category

        def set_display_name(name, item):
            if tprefs['file_list_shows_full_pathname']:
                text = name
            else:
                if name in processed:
                    # We have an exact duplicate (can happen if there are
                    # duplicates in the spine)
                    item.setText(0, processed[name].text(0))
                    item.setText(1, processed[name].text(1))
                    return

                parts = name.split('/')
                text = parts.pop()
                while text in seen and parts:
                    text = parts.pop() + '/' + text

            seen[text] = item
            item.setText(0, text)
            item.setText(1, hexlify(sort_key(text)))

        def render_emblems(item, emblems):
            emblems = tuple(emblems)
            if not emblems:
                return
            icon = self.rendered_emblem_cache.get(emblems, None)
            if icon is None:
                pixmaps = []
                for emblem in emblems:
                    pm = self.emblem_cache.get(emblem, None)
                    if pm is None:
                        pm = self.emblem_cache[emblem] = QIcon(I(emblem)).pixmap(self.iconSize())
                    pixmaps.append(pm)
                num = len(pixmaps)
                w, h = pixmaps[0].width(), pixmaps[0].height()
                if num == 1:
                    icon = self.rendered_emblem_cache[emblems] = QIcon(pixmaps[0])
                else:
                    canvas = QPixmap((num * w) + ((num-1)*2), h)
                    canvas.setDevicePixelRatio(pixmaps[0].devicePixelRatio())
                    canvas.fill(Qt.transparent)
                    painter = QPainter(canvas)
                    for i, pm in enumerate(pixmaps):
                        painter.drawPixmap(int(i * (w + 2)/canvas.devicePixelRatio()), 0, pm)
                    painter.end()
                    icon = self.rendered_emblem_cache[emblems] = canvas
            item.setData(0, Qt.DecorationRole, icon)

        cannot_be_renamed = container.names_that_must_not_be_changed
        ncx_mime = guess_type('a.ncx')
        nav_items = frozenset(container.manifest_items_with_property('nav'))

        def create_item(name, linear=None):
            imt = container.mime_map.get(name, guess_type(name))
            icat = get_category(name, imt)
            category = 'text' if linear is not None else ({'text':'misc'}.get(icat, icat))
            item = QTreeWidgetItem(self.categories['text' if linear is not None else category], 1)
            flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
            if category == 'text':
                flags |= Qt.ItemIsDragEnabled
            if name not in cannot_be_renamed:
                flags |= Qt.ItemIsEditable
            item.setFlags(flags)
            item.setStatusTip(0, _('Full path: ') + name)
            item.setData(0, NAME_ROLE, name)
            item.setData(0, CATEGORY_ROLE, category)
            item.setData(0, LINEAR_ROLE, bool(linear))
            item.setData(0, MIME_ROLE, imt)
            set_display_name(name, item)
            tooltips = []
            emblems = []
            if name in {cover_page_name, cover_image_name}:
                emblems.append('default_cover.png')
                tooltips.append(_('This file is the cover %s for this book') % (_('image') if name == cover_image_name else _('page')))
            if name in container.opf_name:
                emblems.append('metadata.png')
                tooltips.append(_('This file contains all the metadata and book structure information'))
            if imt == ncx_mime or name in nav_items:
                emblems.append('toc.png')
                tooltips.append(_('This file contains the metadata table of contents'))
            if name not in manifested_names and not container.ok_to_be_unmanifested(name):
                emblems.append('dialog_question.png')
                tooltips.append(_('This file is not listed in the book manifest'))
            if linear is False:
                emblems.append('arrow-down.png')
                tooltips.append(_('This file is marked as non-linear in the spine\nDrag it to the top to make it linear'))
            if linear is None and icat == 'text':
                # Text item outside spine
                emblems.append('dialog_warning.png')
                tooltips.append(_('This file is a text file that is not referenced in the spine'))
            if category == 'text' and name in processed:
                # Duplicate entry in spine
                emblems.append('dialog_error.png')
                tooltips.append(_('This file occurs more than once in the spine'))

            render_emblems(item, emblems)
            if tooltips:
                item.setData(0, Qt.ToolTipRole, '\n'.join(tooltips))
            return item

        for name, linear in container.spine_names:
            processed[name] = create_item(name, linear=linear)

        for name in container.name_path_map:
            if name in processed:
                continue
            processed[name] = create_item(name)

        for name, c in self.categories.iteritems():
            c.setExpanded(True)
            if name != 'text':
                c.sortChildren(1, Qt.AscendingOrder)

        if preserve_state:
            self.set_state(state)

        if self.current_edited_name:
            item = self.item_from_name(self.current_edited_name)
            if item is not None:
                self.mark_item_as_current(item)

    def show_context_menu(self, point):
        item = self.itemAt(point)
        if item is None or item in set(self.categories.itervalues()):
            return
        m = QMenu(self)
        sel = self.selectedItems()
        num = len(sel)
        container = current_container()
        ci = self.currentItem()
        if ci is not None:
            cn = unicode(ci.data(0, NAME_ROLE) or '')
            mt = unicode(ci.data(0, MIME_ROLE) or '')
            cat = unicode(ci.data(0, CATEGORY_ROLE) or '')
            n = elided_text(cn.rpartition('/')[-1])
            m.addAction(QIcon(I('save.png')), _('Export %s') % n, partial(self.export, cn))
            if cn not in container.names_that_must_not_be_changed and cn not in container.names_that_must_not_be_removed and mt not in OEB_FONTS:
                m.addAction(_('Replace %s with file...') % n, partial(self.replace, cn))
            if num > 1:
                m.addAction(QIcon(I('save.png')), _('Export all %d selected files') % num, self.export_selected)

            m.addSeparator()

            m.addAction(QIcon(I('modified.png')), _('&Rename %s') % n, self.edit_current_item)
            if is_raster_image(mt):
                m.addAction(QIcon(I('default_cover.png')), _('Mark %s as cover image') % n, partial(self.mark_as_cover, cn))
            elif current_container().SUPPORTS_TITLEPAGES and mt in OEB_DOCS and cat == 'text':
                m.addAction(QIcon(I('default_cover.png')), _('Mark %s as cover page') % n, partial(self.mark_as_titlepage, cn))
            m.addSeparator()

        if num > 0:
            m.addSeparator()
            if num > 1:
                m.addAction(QIcon(I('modified.png')), _('&Bulk rename the selected files'), self.request_bulk_rename)
            m.addAction(QIcon(I('modified.png')), _('Change the file extension for the selected files'), self.request_change_ext)
            m.addAction(QIcon(I('trash.png')), ngettext(
                '&Delete the selected file', '&Delete the {} selected files', num).format(num), self.request_delete)
            m.addSeparator()

        selected_map = defaultdict(list)
        for item in sel:
            selected_map[unicode(item.data(0, CATEGORY_ROLE) or '')].append(unicode(item.data(0, NAME_ROLE) or ''))

        for items in selected_map.itervalues():
            items.sort(key=self.index_of_name)

        if selected_map['text']:
            m.addAction(QIcon(I('format-text-color.png')), _('Link &stylesheets...'), partial(self.link_stylesheets, selected_map['text']))

        if len(selected_map['text']) > 1:
            m.addAction(QIcon(I('merge.png')), _('&Merge selected text files'), partial(self.start_merge, 'text', selected_map['text']))
        if len(selected_map['styles']) > 1:
            m.addAction(QIcon(I('merge.png')), _('&Merge selected style files'), partial(self.start_merge, 'styles', selected_map['styles']))

        if len(list(m.actions())) > 0:
            m.popup(self.mapToGlobal(point))

    def index_of_name(self, name):
        for category, parent in self.categories.iteritems():
            for i in xrange(parent.childCount()):
                item = parent.child(i)
                if unicode(item.data(0, NAME_ROLE) or '') == name:
                    return (category, i)
        return (None, -1)

    def start_merge(self, category, names):
        d = MergeDialog(names, self)
        if d.exec_() == d.Accepted and d.ans:
            self.merge_requested.emit(category, names, d.ans)

    def edit_current_item(self):
        if not current_container().SUPPORTS_FILENAMES:
            error_dialog(self, _('Cannot rename'), _(
                '%s books do not support file renaming as they do not use file names'
                ' internally. The filenames you see are automatically generated from the'
                ' internal structures of the original file.') % current_container().book_type.upper(), show=True)
            return
        if self.currentItem() is not None:
            self.editItem(self.currentItem())

    def mark_as_cover(self, name):
        self.mark_requested.emit(name, 'cover')

    def mark_as_titlepage(self, name):
        first = unicode(self.categories['text'].child(0).data(0, NAME_ROLE) or '') == name
        move_to_start = False
        if not first:
            move_to_start = question_dialog(self, _('Not first item'), _(
                '%s is not the first text item. You should only mark the'
                ' first text item as cover. Do you want to make it the'
                ' first item?') % elided_text(name))
        self.mark_requested.emit(name, 'titlepage:%r' % move_to_start)

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            ev.accept()
            self.request_delete()
        else:
            return QTreeWidget.keyPressEvent(self, ev)

    def request_rename_common(self):
        if not current_container().SUPPORTS_FILENAMES:
            error_dialog(self, _('Cannot rename'), _(
                '%s books do not support file renaming as they do not use file names'
                ' internally. The filenames you see are automatically generated from the'
                ' internal structures of the original file.') % current_container().book_type.upper(), show=True)
            return
        names = {unicode(item.data(0, NAME_ROLE) or '') for item in self.selectedItems()}
        bad = names & current_container().names_that_must_not_be_changed
        if bad:
            error_dialog(self, _('Cannot rename'),
                         _('The file(s) %s cannot be renamed.') % ('<b>%s</b>' % ', '.join(bad)), show=True)
            return
        names = sorted(names, key=self.index_of_name)
        return names

    def request_bulk_rename(self):
        names = self.request_rename_common()
        if names is not None:
            categories = Counter(unicode(item.data(0, CATEGORY_ROLE) or '') for item in self.selectedItems())
            fmt, num = get_bulk_rename_settings(self, len(names), category=categories.most_common(1)[0][0])
            if fmt is not None:
                def change_name(name, num):
                    parts = name.split('/')
                    base, ext = parts[-1].rpartition('.')[0::2]
                    parts[-1] = (fmt % num) + '.' + ext
                    return '/'.join(parts)
                name_map = {n:change_name(n, num + i) for i, n in enumerate(names)}
                self.bulk_rename_requested.emit(name_map)

    def request_change_ext(self):
        names = self.request_rename_common()
        if names is not None:
            text, ok = QInputDialog.getText(self, _('Rename files'), _('New file extension:'))
            if ok and text:
                ext = text.lstrip('.')

                def change_name(name):
                    base = posixpath.splitext(name)[0]
                    return base + '.' + ext
                name_map = {n:change_name(n) for n in names}
                self.bulk_rename_requested.emit(name_map)

    @property
    def selected_names(self):
        ans = {unicode(item.data(0, NAME_ROLE) or '') for item in self.selectedItems()}
        ans.discard('')
        return ans

    def request_delete(self):
        names = self.selected_names
        bad = names & current_container().names_that_must_not_be_removed
        if bad:
            return error_dialog(self, _('Cannot delete'),
                         _('The file(s) %s cannot be deleted.') % ('<b>%s</b>' % ', '.join(bad)), show=True)

        text = self.categories['text']
        children = (text.child(i) for i in xrange(text.childCount()))
        spine_removals = [(unicode(item.data(0, NAME_ROLE) or ''), item.isSelected()) for item in children]
        other_removals = {unicode(item.data(0, NAME_ROLE) or '') for item in self.selectedItems()
                          if unicode(item.data(0, CATEGORY_ROLE) or '') != 'text'}
        self.delete_requested.emit(spine_removals, other_removals)

    def delete_done(self, spine_removals, other_removals):
        removals = []
        for i, (name, remove) in enumerate(spine_removals):
            if remove:
                removals.append(self.categories['text'].child(i))
        for category, parent in self.categories.iteritems():
            if category != 'text':
                for i in xrange(parent.childCount()):
                    child = parent.child(i)
                    if unicode(child.data(0, NAME_ROLE) or '') in other_removals:
                        removals.append(child)

        # The sorting by index is necessary otherwise Qt crashes with recursive
        # repaint detected message
        for c in sorted(removals, key=lambda x:x.parent().indexOfChild(x), reverse=True):
            sip.delete(c)

        # A bug in the raster paint engine on linux causes a crash if the scrollbar
        # is at the bottom and the delete happens to cause the scrollbar to
        # update
        b = self.verticalScrollBar()
        if b.value() == b.maximum():
            b.setValue(b.minimum())
            QTimer.singleShot(0, lambda : b.setValue(b.maximum()))

    def __enter__(self):
        self.ordered_selected_indexes = True

    def __exit__(self, *args):
        self.ordered_selected_indexes = False

    def selectedIndexes(self):
        ans = QTreeWidget.selectedIndexes(self)
        if self.ordered_selected_indexes:
            ans = list(sorted(ans, key=lambda idx:idx.row()))
        return ans

    def dropEvent(self, event):
        with self:
            text = self.categories['text']
            pre_drop_order = {text.child(i):i for i in xrange(text.childCount())}
            super(FileList, self).dropEvent(event)
            current_order = {text.child(i):i for i in xrange(text.childCount())}
            if current_order != pre_drop_order:
                order = []
                for child in (text.child(i) for i in xrange(text.childCount())):
                    name = unicode(child.data(0, NAME_ROLE) or '')
                    linear = bool(child.data(0, LINEAR_ROLE))
                    order.append([name, linear])
                # Ensure that all non-linear items are at the end, any non-linear
                # items not at the end will be made linear
                for i, (name, linear) in tuple(enumerate(order)):
                    if not linear and i < len(order) - 1 and order[i+1][1]:
                        order[i][1] = True
                self.reorder_spine.emit(order)

    def item_double_clicked(self, item, column):
        category = unicode(item.data(0, CATEGORY_ROLE) or '')
        if category:
            self._request_edit(item)

    def _request_edit(self, item):
        category = unicode(item.data(0, CATEGORY_ROLE) or '')
        mime = unicode(item.data(0, MIME_ROLE) or '')
        name = unicode(item.data(0, NAME_ROLE) or '')
        syntax = {'text':'html', 'styles':'css'}.get(category, None)
        self.edit_file.emit(name, syntax, mime)

    def request_edit(self, name):
        item = self.item_from_name(name)
        if item is not None:
            self._request_edit(item)
        else:
            error_dialog(self, _('Cannot edit'),
                         _('No item with the name: %s was found') % name, show=True)

    @property
    def all_files(self):
        return (category.child(i) for category in self.categories.itervalues() for i in xrange(category.childCount()))

    @property
    def searchable_names(self):
        ans = {'text':OrderedDict(), 'styles':OrderedDict(), 'selected':OrderedDict(), 'open':OrderedDict()}
        for item in self.all_files:
            category = unicode(item.data(0, CATEGORY_ROLE) or '')
            mime = unicode(item.data(0, MIME_ROLE) or '')
            name = unicode(item.data(0, NAME_ROLE) or '')
            ok = category in {'text', 'styles'}
            if ok:
                ans[category][name] = syntax_from_mime(name, mime)
            if not ok and category == 'misc':
                ok = mime in {guess_type('a.'+x) for x in ('opf', 'ncx', 'txt', 'xml')}
            if ok:
                cats = []
                if item.isSelected():
                    cats.append('selected')
                if name in editors:
                    cats.append('open')
                for cat in cats:
                    ans[cat][name] = syntax_from_mime(name, mime)
        return ans

    def export(self, name):
        path = choose_save_file(self, 'tweak_book_export_file', _('Choose location'), filters=[
            (_('Files'), [name.rpartition('.')[-1].lower()])], all_files=False, initial_filename=name.split('/')[-1])
        if path:
            self.export_requested.emit(name, path)

    def export_selected(self):
        names = self.selected_names
        if not names:
            return
        path = choose_dir(self, 'tweak_book_export_selected', _('Choose location'))
        if path:
            self.export_requested.emit(names, path)

    def replace(self, name):
        c = current_container()
        mt = c.mime_map[name]
        oext = name.rpartition('.')[-1].lower()
        filters = [oext]
        fname = _('Files')
        if mt in OEB_DOCS:
            fname = _('HTML files')
            filters = 'html htm xhtm xhtml shtml'.split()
        elif is_raster_image(mt):
            fname = _('Images')
            filters = 'jpeg jpg gif png'.split()
        path = choose_files(self, 'tweak_book_import_file', _('Choose file'), filters=[(fname, filters)], select_only_single_file=True)
        if not path:
            return
        path = path[0]
        ext = path.rpartition('.')[-1].lower()
        force_mt = None
        if mt in OEB_DOCS:
            force_mt = c.guess_type('a.html')
        nname = os.path.basename(path)
        nname, ext = nname.rpartition('.')[0::2]
        nname = nname + '.' + ext.lower()
        self.replace_requested.emit(name, path, nname, force_mt)

    def link_stylesheets(self, names):
        s = self.categories['styles']
        sheets = [unicode(s.child(i).data(0, NAME_ROLE) or '') for i in xrange(s.childCount())]
        if not sheets:
            return error_dialog(self, _('No stylesheets'), _(
                'This book currently has no stylesheets. You must first create a stylesheet'
                ' before linking it.'), show=True)
        d = QDialog(self)
        d.l = l = QVBoxLayout(d)
        d.setLayout(l)
        d.setWindowTitle(_('Choose stylesheets'))
        d.la = la = QLabel(_('Choose the stylesheets to link. Drag and drop to re-arrange'))

        la.setWordWrap(True)
        l.addWidget(la)
        d.s = s = QListWidget(d)
        l.addWidget(s)
        s.setDragEnabled(True)
        s.setDropIndicatorShown(True)
        s.setDragDropMode(self.InternalMove)
        s.setAutoScroll(True)
        s.setDefaultDropAction(Qt.MoveAction)
        for name in sheets:
            i = QListWidgetItem(name, s)
            flags = Qt.ItemIsEnabled | Qt.ItemIsUserCheckable | Qt.ItemIsDragEnabled | Qt.ItemIsSelectable
            i.setFlags(flags)
            i.setCheckState(Qt.Checked)
        d.r = r = QCheckBox(_('Remove existing links to stylesheets'))
        r.setChecked(tprefs['remove_existing_links_when_linking_sheets'])
        l.addWidget(r)
        d.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(d.accept), bb.rejected.connect(d.reject)
        l.addWidget(bb)
        if d.exec_() == d.Accepted:
            tprefs['remove_existing_links_when_linking_sheets'] = r.isChecked()
            sheets = [unicode(s.item(il).text()) for il in xrange(s.count()) if s.item(il).checkState() == Qt.Checked]
            if sheets:
                self.link_stylesheets_requested.emit(names, sheets, r.isChecked())


class NewFileDialog(QDialog):  # {{{

    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        self.la = la = QLabel(_(
            'Choose a name for the new (blank) file. To place the file in a'
            ' specific folder in the book, include the folder name, for example: <i>text/chapter1.html'))
        la.setWordWrap(True)
        self.setWindowTitle(_('Choose file'))
        l.addWidget(la)
        self.name = n = QLineEdit(self)
        n.textChanged.connect(self.update_ok)
        l.addWidget(n)
        self.err_label = la = QLabel('')
        la.setWordWrap(True)
        l.addWidget(la)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        l.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.imp_button = b = bb.addButton(_('Import resource file (image/font/etc.)'), bb.ActionRole)
        b.setIcon(QIcon(I('view-image.png')))
        b.setToolTip(_('Import a file from your computer as a new'
                       ' file into the book.'))
        b.clicked.connect(self.import_file)

        self.ok_button = bb.button(bb.Ok)

        self.file_data = b''
        self.using_template = False
        self.setMinimumWidth(350)

    def show_error(self, msg):
        self.err_label.setText('<p style="color:red">' + msg)
        return False

    def import_file(self):
        path = choose_files(self, 'tweak-book-new-resource-file', _('Choose file'), select_only_single_file=True)
        if path:
            self.do_import_file(path[0])

    def do_import_file(self, path, hide_button=False):
        with open(path, 'rb') as f:
            self.file_data = f.read()
        name = os.path.basename(path)
        fmap = get_recommended_folders(current_container(), (name,))
        if fmap[name]:
            name = '/'.join((fmap[name], name))
        self.name.setText(name)
        self.la.setText(_('Choose a name for the imported file'))
        if hide_button:
            self.imp_button.setVisible(False)

    @property
    def name_is_ok(self):
        return name_is_ok(unicode(self.name.text()), self.show_error)

    def update_ok(self, *args):
        self.ok_button.setEnabled(self.name_is_ok)

    def accept(self):
        if not self.name_is_ok:
            return error_dialog(self, _('No name specified'), _(
                'You must specify a name for the new file, with an extension, for example, chapter1.html'), show=True)
        name = unicode(self.name.text())
        name, ext = name.rpartition('.')[0::2]
        name = (name + '.' + ext.lower()).replace('\\', '/')
        mt = guess_type(name)
        if not self.file_data:
            if mt in OEB_DOCS:
                self.file_data = template_for('html').encode('utf-8')
                self.using_template = True
            elif mt in OEB_STYLES:
                self.file_data = template_for('css').encode('utf-8')
                self.using_template = True
        self.file_name = name
        QDialog.accept(self)
# }}}


class MergeDialog(QDialog):  # {{{

    def __init__(self, names, parent=None):
        QDialog.__init__(self, parent)
        self.names = names
        self.setWindowTitle(_('Choose master file'))
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        self.la = la = QLabel(_('Choose the master file. All selected files will be merged into the master file:'))
        la.setWordWrap(True)
        l.addWidget(la)
        self.sa = sa = QScrollArea(self)
        l.addWidget(sa)
        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        l.addWidget(bb)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.w = w = QWidget(self)
        w.l = QVBoxLayout()
        w.setLayout(w.l)

        buttons = self.buttons = [QRadioButton(n) for n in names]
        buttons[0].setChecked(True)
        map(w.l.addWidget, buttons)
        sa.setWidget(w)

        self.resize(self.sizeHint() + QSize(150, 20))

    @property
    def ans(self):
        for n, b in zip(self.names, self.buttons):
            if b.isChecked():
                return n

# }}}


class FileListWidget(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setLayout(QGridLayout(self))
        self.file_list = FileList(self)
        self.layout().addWidget(self.file_list)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.forwarded_signals = {k for k, o in vars(self.file_list.__class__).iteritems() if isinstance(o, pyqtSignal) and '_' in k and not hasattr(self, k)}
        for x in ('delete_done', 'select_name', 'select_names', 'request_edit', 'mark_name_as_current', 'clear_currently_edited_name'):
            setattr(self, x, getattr(self.file_list, x))
        self.setFocusProxy(self.file_list)

    def build(self, container, preserve_state=True):
        self.file_list.build(container, preserve_state=preserve_state)

    @property
    def searchable_names(self):
        return self.file_list.searchable_names

    @property
    def current_name(self):
        return self.file_list.current_name

    def __getattr__(self, name):
        if name in self.forwarded_signals:
            return getattr(self.file_list, name)
        return QWidget.__getattr__(self, name)
