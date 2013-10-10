#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.Qt import (
    QWidget, QTreeWidget, QGridLayout, QSize, Qt, QTreeWidgetItem, QIcon,
    QStyledItemDelegate, QStyle, QPixmap, QPainter)

from calibre import guess_type, human_readable
from calibre.ebooks.oeb.base import OEB_STYLES
from calibre.ebooks.oeb.polish.cover import get_cover_page_name, get_raster_cover_name
from calibre.gui2.tweak_book import current_container

TOP_ICON_SIZE = 24
NAME_ROLE = Qt.UserRole
NBSP = '\xa0'

class ItemDelegate(QStyledItemDelegate):  # {{{

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

    def __init__(self, parent=None):
        QTreeWidget.__init__(self, parent)
        self.delegate = ItemDelegate(self)
        self.setTextElideMode(Qt.ElideMiddle)
        self.setItemDelegate(self.delegate)
        self.setIconSize(QSize(16, 16))
        self.header().close()
        self.setDragEnabled(True)
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
        self.in_drop_event = False
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

    def build(self, container):
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

        processed, seen = set(), {}

        def get_display_name(name, item):
            parts = name.split('/')
            text = parts[-1]
            while text in seen and parts:
                text = parts.pop() + '/' + text
            seen[text] = item
            return text

        cover_page_name = get_cover_page_name(container)
        cover_image_name = get_raster_cover_name(container)
        manifested_names = set()
        for names in container.manifest_type_map.itervalues():
            manifested_names |= set(names)

        def add_emblems(item, name, linear=True):
            emblems = []
            if name in {cover_page_name, cover_image_name}:
                emblems.append('default_cover.png')
            if name not in manifested_names and name not in {container.opf_name, 'META-INF/container.xml', 'META-INF/encryption.xml'}:
                emblems.append('dialog_question.png')
            if not linear:
                emblems.append('arrow-down.png')
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

        for name, linear in container.spine_names:
            processed.add(name)
            i = QTreeWidgetItem(self.categories['text'], 1)
            prefix = '' if linear else '[nl] '
            i.setText(0, prefix + get_display_name(name, i))
            i.setStatusTip(0, _('Full path: ') + name)
            i.setFlags(Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsSelectable)
            i.setData(0, NAME_ROLE, name)
            add_emblems(i, name, linear=linear)

        font_types = {guess_type('a.'+x)[0] for x in ('ttf', 'otf', 'woff')}

        def get_category(mt):
            category = 'misc'
            if mt.startswith('image/'):
                category = 'images'
            elif mt in font_types:
                category = 'fonts'
            elif mt in OEB_STYLES:
                category = 'styles'
            return category

        all_files = list(container.manifest_type_map.iteritems())
        all_files.append((guess_type('a.opf')[0], [container.opf_name]))

        for name in container.name_path_map:
            if name in processed:
                continue
            processed.add(name)
            imt = container.mime_map.get(name, guess_type(name)[0])
            icat = get_category(imt)
            i = QTreeWidgetItem(self.categories[icat], 1)
            i.setText(0, get_display_name(name, i))
            i.setStatusTip(0, _('Full path: ') + name)
            i.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            i.setData(0, NAME_ROLE, name)
            add_emblems(i, name)

        for c in self.categories.itervalues():
            self.expandItem(c)

    def show_context_menu(self, point):
        pass

class FileListWidget(QWidget):

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setLayout(QGridLayout(self))
        self.file_list = FileList(self)
        self.layout().addWidget(self.file_list)
        self.layout().setContentsMargins(0, 0, 0, 0)

    def build(self, container):
        self.file_list.build(container)


