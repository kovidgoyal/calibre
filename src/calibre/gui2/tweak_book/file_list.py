#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from binascii import hexlify
from PyQt4.Qt import (
    QWidget, QTreeWidget, QGridLayout, QSize, Qt, QTreeWidgetItem, QIcon,
    QStyledItemDelegate, QStyle, QPixmap, QPainter, pyqtSignal)

from calibre import human_readable
from calibre.ebooks.oeb.base import OEB_STYLES, OEB_DOCS
from calibre.ebooks.oeb.polish.container import guess_type
from calibre.ebooks.oeb.polish.cover import get_cover_page_name, get_raster_cover_name
from calibre.gui2 import error_dialog
from calibre.gui2.tweak_book import current_container
from calibre.utils.icu import sort_key

TOP_ICON_SIZE = 24
NAME_ROLE = Qt.UserRole
CATEGORY_ROLE = NAME_ROLE + 1
LINEAR_ROLE = CATEGORY_ROLE + 1
MIME_ROLE = LINEAR_ROLE + 1
NBSP = '\xa0'

class ItemDelegate(QStyledItemDelegate):  # {{{

    rename_requested = pyqtSignal(object, object)

    def setEditorData(self, editor, index):
        name = unicode(index.data(NAME_ROLE).toString())
        editor.setText(name)

    def setModelData(self, editor, model, index):
        newname = unicode(editor.text())
        oldname = unicode(index.data(NAME_ROLE).toString())
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
                suffix = NBSP + human_readable(current_container().filesize(unicode(index.data(NAME_ROLE).toString())))
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
    edit_file = pyqtSignal(object, object, object)

    def __init__(self, parent=None):
        QTreeWidget.__init__(self, parent)
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
            name : QPixmap(I(icon)).scaled(TOP_ICON_SIZE, TOP_ICON_SIZE, transformMode=Qt.SmoothTransformation)
            for name, icon in {
                'text':'keyboard-prefs.png',
                'styles':'lookfeel.png',
                'fonts':'font.png',
                'misc':'mimetypes/dir.png',
                'images':'view-image.png',
            }.iteritems()}
        self.itemDoubleClicked.connect(self.item_double_clicked)

    def get_state(self):
        s = {'pos':self.verticalScrollBar().value()}
        s['expanded'] = {c for c, item in self.categories.iteritems() if item.isExpanded()}
        s['selected'] = {unicode(i.data(0, NAME_ROLE).toString()) for i in self.selectedItems()}
        return s

    def set_state(self, state):
        for category, item in self.categories.iteritems():
            item.setExpanded(category in state['expanded'])
        self.verticalScrollBar().setValue(state['pos'])
        for parent in self.categories.itervalues():
            for c in (parent.child(i) for i in xrange(parent.childCount())):
                name = unicode(c.data(0, NAME_ROLE).toString())
                if name in state['selected']:
                    c.setSelected(True)

    def build(self, container, preserve_state=True):
        if preserve_state:
            state = self.get_state()
        self.clear()
        self.root = self.invisibleRootItem()
        self.root.setFlags(Qt.ItemIsDragEnabled)
        self.categories = {}
        for category, text in (
            ('text', _('Text')),
            ('styles', _('Styles')),
            ('images', _('Images')),
            ('fonts', _('Fonts')),
            ('misc', _('Miscellaneous')),
        ):
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

        font_types = {guess_type('a.'+x) for x in ('ttf', 'otf', 'woff')}

        def get_category(mt):
            category = 'misc'
            if mt.startswith('image/'):
                category = 'images'
            elif mt in font_types:
                category = 'fonts'
            elif mt in OEB_STYLES:
                category = 'styles'
            elif mt in OEB_DOCS:
                category = 'text'
            return category

        def set_display_name(name, item):
            if name in processed:
                # We have an exact duplicate (can happen if there are
                # duplicates in the spine)
                item.setText(0, processed[name].text(0))
                item.setText(1, processed[name].text(1))
                return

            parts = name.split('/')
            text = parts[-1]
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
                        pm = self.emblem_cache[emblem] = QPixmap(
                            I(emblem)).scaled(self.iconSize(), transformMode=Qt.SmoothTransformation)
                    pixmaps.append(pm)
                num = len(pixmaps)
                w, h = pixmaps[0].width(), pixmaps[0].height()
                if num == 1:
                    icon = self.rendered_emblem_cache[emblems] = QIcon(pixmaps[0])
                else:
                    canvas = QPixmap((num * w) + ((num-1)*2), h)
                    canvas.fill(Qt.transparent)
                    painter = QPainter(canvas)
                    for i, pm in enumerate(pixmaps):
                        painter.drawPixmap(i * (w + 2), 0, pm)
                    painter.end()
                    icon = self.rendered_emblem_cache[emblems] = canvas
            item.setData(0, Qt.DecorationRole, icon)

        ok_to_be_unmanifested = container.names_that_need_not_be_manifested
        cannot_be_renamed = container.names_that_must_not_be_changed

        def create_item(name, linear=None):
            imt = container.mime_map.get(name, guess_type(name))
            icat = get_category(imt)
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
            # TODO: Add appropriate tooltips based on the emblems
            emblems = []
            if name in {cover_page_name, cover_image_name}:
                emblems.append('default_cover.png')
            if name not in manifested_names and name not in ok_to_be_unmanifested:
                emblems.append('dialog_question.png')
            if linear is False:
                emblems.append('arrow-down.png')
            if linear is None and icat == 'text':
                # Text item outside spine
                emblems.append('dialog_warning.png')
            if category == 'text' and name in processed:
                # Duplicate entry in spine
                emblems.append('dialog_warning.png')

            render_emblems(item, emblems)
            return item

        for name, linear in container.spine_names:
            processed[name] = create_item(name, linear=linear)

        all_files = list(container.manifest_type_map.iteritems())
        all_files.append((guess_type('a.opf'), [container.opf_name]))

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

    def show_context_menu(self, point):
        pass  # TODO: Implement this

    def keyPressEvent(self, ev):
        if ev.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            ev.accept()
            self.request_delete()
        else:
            return QTreeWidget.keyPressEvent(self, ev)

    def request_delete(self):
        names = {unicode(item.data(0, NAME_ROLE).toString()) for item in self.selectedItems()}
        bad = names & current_container().names_that_must_not_be_removed
        if bad:
            return error_dialog(self, _('Cannot delete'),
                         _('The file(s) %s cannot be deleted.') % ('<b>%s</b>' % ', '.join(bad)), show=True)

        text = self.categories['text']
        children = (text.child(i) for i in xrange(text.childCount()))
        spine_removals = [(unicode(item.data(0, NAME_ROLE).toString()), item.isSelected()) for item in children]
        other_removals = {unicode(item.data(0, NAME_ROLE).toString()) for item in self.selectedItems()
                          if unicode(item.data(0, CATEGORY_ROLE).toString()) != 'text'}
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
                    if unicode(child.data(0, NAME_ROLE).toString()) in other_removals:
                        removals.append(child)

        for c in removals:
            c.parent().removeChild(c)

    def dropEvent(self, event):
        text = self.categories['text']
        pre_drop_order = {text.child(i):i for i in xrange(text.childCount())}
        super(FileList, self).dropEvent(event)
        current_order = {text.child(i):i for i in xrange(text.childCount())}
        if current_order != pre_drop_order:
            order = []
            for child in (text.child(i) for i in xrange(text.childCount())):
                name = unicode(child.data(0, NAME_ROLE).toString())
                linear = child.data(0, LINEAR_ROLE).toBool()
                order.append([name, linear])
            # Ensure that all non-linear items are at the end, any non-linear
            # items not at the end will be made linear
            for i, (name, linear) in tuple(enumerate(order)):
                if not linear and i < len(order) - 1 and order[i+1][1]:
                    order[i][1] = True
            self.reorder_spine.emit(order)

    def item_double_clicked(self, item, column):
        category = unicode(item.data(0, CATEGORY_ROLE).toString())
        mime = unicode(item.data(0, MIME_ROLE).toString())
        name = unicode(item.data(0, NAME_ROLE).toString())
        syntax = {'text':'html', 'styles':'css'}.get(category, None)
        self.edit_file.emit(name, syntax, mime)

class FileListWidget(QWidget):

    delete_requested = pyqtSignal(object, object)
    reorder_spine = pyqtSignal(object)
    rename_requested = pyqtSignal(object, object)
    edit_file = pyqtSignal(object, object, object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setLayout(QGridLayout(self))
        self.file_list = FileList(self)
        self.layout().addWidget(self.file_list)
        self.layout().setContentsMargins(0, 0, 0, 0)
        for x in ('delete_requested', 'reorder_spine', 'rename_requested', 'edit_file'):
            getattr(self.file_list, x).connect(getattr(self, x))
        for x in ('delete_done',):
            setattr(self, x, getattr(self.file_list, x))

    def build(self, container, preserve_state=True):
        self.file_list.build(container, preserve_state=preserve_state)


