#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import os
from binascii import hexlify
from collections import OrderedDict, defaultdict
from functools import partial
from PyQt4.Qt import (
    QWidget, QTreeWidget, QGridLayout, QSize, Qt, QTreeWidgetItem, QIcon,
    QStyledItemDelegate, QStyle, QPixmap, QPainter, pyqtSignal, QMenu,
    QDialogButtonBox, QDialog, QLabel, QLineEdit, QVBoxLayout, QScrollArea, QRadioButton)

from calibre import human_readable, sanitize_file_name_unicode
from calibre.ebooks.oeb.base import OEB_STYLES, OEB_DOCS
from calibre.ebooks.oeb.polish.container import guess_type, OEB_FONTS
from calibre.ebooks.oeb.polish.cover import (
    get_cover_page_name, get_raster_cover_name, is_raster_image)
from calibre.gui2 import error_dialog, choose_files, question_dialog, elided_text, choose_save_file
from calibre.gui2.tweak_book import current_container
from calibre.gui2.tweak_book.editor import syntax_from_mime
from calibre.gui2.tweak_book.templates import template_for
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
                try:
                    suffix = NBSP + human_readable(current_container().filesize(unicode(index.data(NAME_ROLE).toString())))
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
    edit_file = pyqtSignal(object, object, object)
    merge_requested = pyqtSignal(object, object, object)
    mark_requested = pyqtSignal(object, object)
    export_requested = pyqtSignal(object, object)
    replace_requested = pyqtSignal(object, object, object, object)

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

    def select_name(self, name):
        for parent in self.categories.itervalues():
            for c in (parent.child(i) for i in xrange(parent.childCount())):
                q = unicode(c.data(0, NAME_ROLE).toString())
                c.setSelected(q == name)
                if q == name:
                    self.scrollToItem(c)

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
        item = self.itemAt(point)
        if item is None or item in set(self.categories.itervalues()):
            return
        m = QMenu(self)
        sel = self.selectedItems()
        num = len(sel)
        container = current_container()
        if num > 0:
            m.addAction(QIcon(I('trash.png')), _('&Delete selected files'), self.request_delete)
            m.addSeparator()
        ci = self.currentItem()
        if ci is not None:
            cn = unicode(ci.data(0, NAME_ROLE).toString())
            mt = unicode(ci.data(0, MIME_ROLE).toString())
            cat = unicode(ci.data(0, CATEGORY_ROLE).toString())
            n = elided_text(cn.rpartition('/')[-1])
            m.addAction(QIcon(I('modified.png')), _('&Rename %s') % n, self.edit_current_item)
            if is_raster_image(mt):
                m.addAction(QIcon(I('default_cover.png')), _('Mark %s as cover image') % n, partial(self.mark_as_cover, cn))
            elif current_container().SUPPORTS_TITLEPAGES and mt in OEB_DOCS and cat == 'text':
                m.addAction(QIcon(I('default_cover.png')), _('Mark %s as cover page') % n, partial(self.mark_as_titlepage, cn))
            m.addSeparator()
            m.addAction(QIcon(I('save.png')), _('Export %s') % n, partial(self.export, cn))
            if cn not in container.names_that_must_not_be_changed and cn not in container.names_that_must_not_be_removed and mt not in OEB_FONTS:
                m.addAction(_('Replace %s with file...') % n, partial(self.replace, cn))
            m.addSeparator()

        selected_map = defaultdict(list)
        for item in sel:
            selected_map[unicode(item.data(0, CATEGORY_ROLE).toString())].append(unicode(item.data(0, NAME_ROLE).toString()))

        for items in selected_map.itervalues():
            items.sort(key=self.index_of_name)

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
                if unicode(item.data(0, NAME_ROLE).toString()) == name:
                    return (category, i)
        return (None, -1)

    def start_merge(self, category, names):
        d = MergeDialog(names, self)
        if d.exec_() == d.Accepted and d.ans:
            self.merge_requested.emit(category, names, d.ans)

    def edit_current_item(self):
        if self.currentItem() is not None:
            self.editItem(self.currentItem())

    def mark_as_cover(self, name):
        self.mark_requested.emit(name, 'cover')

    def mark_as_titlepage(self, name):
        first = unicode(self.categories['text'].child(0).data(0, NAME_ROLE).toString()) == name
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

    @property
    def all_files(self):
        return (category.child(i) for category in self.categories.itervalues() for i in xrange(category.childCount()))

    @property
    def searchable_names(self):
        ans = {'text':OrderedDict(), 'styles':OrderedDict(), 'selected':OrderedDict()}
        for item in self.all_files:
            category = unicode(item.data(0, CATEGORY_ROLE).toString())
            mime = unicode(item.data(0, MIME_ROLE).toString())
            name = unicode(item.data(0, NAME_ROLE).toString())
            ok = category in {'text', 'styles'}
            if ok:
                ans[category][name] = syntax_from_mime(name, mime)
            if not ok and category == 'misc':
                ok = mime in {guess_type('a.'+x) for x in ('opf', 'ncx', 'txt', 'xml')}
            if ok and item.isSelected():
                ans['selected'][name] = syntax_from_mime(name, mime)
        return ans

    def export(self, name):
        path = choose_save_file(self, 'tweak_book_export_file', _('Choose location'), filters=[
            (_('Files'), [name.rpartition('.')[-1].lower()])], all_files=False)
        if path:
            self.export_requested.emit(name, path)

    def replace(self, name):
        c = current_container()
        mt = c.mime_map[name]
        oext = name.rpartition('.')[-1].lower()
        filters = [oext]
        fname = _('Files')
        if mt in OEB_DOCS:
            fname = _('HTML Files')
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


class NewFileDialog(QDialog):  # {{{

    def __init__(self, initial_choice='html', parent=None):
        QDialog.__init__(self, parent)
        self.l = l = QVBoxLayout()
        self.setLayout(l)
        self.la = la = QLabel(_(
            'Choose a name for the new file'))
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
        b.clicked.connect(self.import_file)

        self.ok_button = bb.button(bb.Ok)

        self.file_data = ''
        self.using_template = False

    def show_error(self, msg):
        self.err_label.setText('<p style="color:red">' + msg)
        return False

    def import_file(self):
        path = choose_files(self, 'tweak-book-new-resource-file', _('Choose file'), select_only_single_file=True)
        if path:
            path = path[0]
            with open(path, 'rb') as f:
                self.file_data = f.read()
            name = os.path.basename(path)
            self.name.setText(name)

    @property
    def name_is_ok(self):
        name = unicode(self.name.text())
        if not name or not name.strip():
            return self.show_error('')
        ext = name.rpartition('.')[-1]
        if not ext or ext == name:
            return self.show_error(_('The file name must have an extension'))
        norm = name.replace('\\', '/')
        parts = name.split('/')
        for x in parts:
            if sanitize_file_name_unicode(x) != x:
                return self.show_error(_('The file name contains invalid characters'))
        if current_container().has_name(norm):
            return self.show_error(_('This file name already exists in the book'))
        self.show_error('')
        return True

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
        for b in self.buttons:
            if b.isChecked():
                return unicode(b.text())

# }}}

class FileListWidget(QWidget):

    delete_requested = pyqtSignal(object, object)
    reorder_spine = pyqtSignal(object)
    rename_requested = pyqtSignal(object, object)
    edit_file = pyqtSignal(object, object, object)
    merge_requested = pyqtSignal(object, object, object)
    mark_requested = pyqtSignal(object, object)
    export_requested = pyqtSignal(object, object)
    replace_requested = pyqtSignal(object, object, object, object)

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self.setLayout(QGridLayout(self))
        self.file_list = FileList(self)
        self.layout().addWidget(self.file_list)
        self.layout().setContentsMargins(0, 0, 0, 0)
        for x in ('delete_requested', 'reorder_spine', 'rename_requested',
                  'edit_file', 'merge_requested', 'mark_requested',
                  'export_requested', 'replace_requested'):
            getattr(self.file_list, x).connect(getattr(self, x))
        for x in ('delete_done', 'select_name'):
            setattr(self, x, getattr(self.file_list, x))

    def build(self, container, preserve_state=True):
        self.file_list.build(container, preserve_state=preserve_state)

    @property
    def searchable_names(self):
        return self.file_list.searchable_names

