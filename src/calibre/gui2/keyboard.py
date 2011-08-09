#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from collections import OrderedDict

from PyQt4.Qt import (QObject, QKeySequence, QAbstractItemModel, QModelIndex,
        Qt, QStyledItemDelegate, QTextDocument, QStyle, pyqtSignal,
        QApplication, QSize, QRectF, QWidget, QHBoxLayout, QTreeView)

from calibre.utils.config import JSONConfig
from calibre.constants import DEBUG
from calibre import prints
from calibre.utils.icu import sort_key
from calibre.gui2 import NONE

ROOT = QModelIndex()

class NameConflict(ValueError):
    pass

class Manager(QObject): # {{{

    def __init__(self, parent=None):
        QObject.__init__(self, parent)

        self.config = JSONConfig('shortcuts/main')
        self.custom_keys_map = {}
        self.shortcuts = OrderedDict()
        self.keys_map = {}
        self.groups = {}

    def register_shortcut(self, unique_name, name, default_keys=(),
            description=None, action=None, group=None):
        if unique_name in self.shortcuts:
            name = self.shortcuts[unique_name]['name']
            raise NameConflict('Shortcut for %r already registered by %s'%(
                    unique_name, name))
        shortcut = {'name':name, 'desc':description, 'action': action,
                'default_keys':tuple(default_keys)}
        self.shortcuts[unique_name] = shortcut
        group = group if group else _('Miscellaneous')
        self.groups[group] = self.groups.get(group, []) + [unique_name]

    def finalize(self):
        self.custom_keys_map = {un:tuple(keys) for un, keys in self.config.get(
                'map', {}).iteritems()}

        seen = {}
        for unique_name, shortcut in self.shortcuts.iteritems():
            custom_keys = self.custom_keys_map.get(unique_name, None)
            if custom_keys is None:
                candidates = shortcut['default_keys']
            else:
                candidates = custom_keys
            keys = []
            for x in candidates:
                ks = QKeySequence(x, QKeySequence.PortableText)
                x = unicode(ks.toString(QKeySequence.PortableText))
                if x in seen:
                    if DEBUG:
                        prints('Key %r for shortcut %s is already used by'
                                ' %s, ignoring'%(x, shortcut['name'], seen[x]['name']))
                    continue
                seen[x] = shortcut
                keys.append(ks)
            keys = tuple(keys)
            #print (111111, unique_name, candidates, keys)

            self.keys_map[unique_name] = keys
            ac = shortcut['action']
            if ac is not None:
                ac.setShortcuts(list(keys))

        self.groups = {g:frozenset(v) for g, v in self.groups.iteritems()}
# }}}

# Model {{{

class Node(object):

    def __init__(self, group_map, shortcut_map, name=None, shortcut=None):
        self.data = name if name is not None else shortcut
        self.is_shortcut = shortcut is not None
        self.children = []
        if name is not None:
            self.children = [Node(None, None, shortcut=shortcut_map[uname])
                    for uname in group_map[name]]

    def __len__(self):
        return len(self.children)

    def __getitem__(self, row):
        return self.children[row]

class ConfigModel(QAbstractItemModel):

    def __init__(self, keyboard, parent=None):
        QAbstractItemModel.__init__(self, parent)

        self.keyboard = keyboard
        groups = sorted(keyboard.groups, key=sort_key)
        shortcut_map = {k:dict(v) for k, v in
                self.keyboard.shortcuts.iteritems()}
        for un, s in shortcut_map.iteritems():
            s['keys'] = tuple(self.keyboard.keys_map[un])
            s['unique_name'] = un
            s['group'] = [g for g, names in self.keyboard.groups.iteritems() if un in
                    names][0]

        group_map = {group:sorted(names, key=lambda x:
                sort_key(shortcut_map[x]['name'])) for group, names in
                self.keyboard.groups.iteritems()}

        self.data = [Node(group_map, shortcut_map, group) for group in groups]

    def rowCount(self, parent=ROOT):
        ip = parent.internalPointer()
        if ip is None:
            return len(self.data)
        return len(ip)

    def columnCount(self, parent=ROOT):
        return 1

    def index(self, row, column, parent=ROOT):
        ip = parent.internalPointer()
        if ip is None:
            ip = self.data
        try:
            return self.createIndex(row, column, ip[row])
        except:
            pass
        return ROOT

    def parent(self, index):
        ip = index.internalPointer()
        if ip is None or not ip.is_shortcut:
            return ROOT
        group = ip.data['group']
        for i, g in enumerate(self.data):
            if g.data == group:
                return self.index(i, 0)
        return ROOT

    def data(self, index, role=Qt.DisplayRole):
        ip = index.internalPointer()
        if ip is not None and role == Qt.UserRole:
            return ip
        return NONE

# }}}

class Delegate(QStyledItemDelegate): # {{{

    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)
        self.editing_indices = {}

    def to_doc(self, index):
        data = index.data(Qt.UserRole).toPyObject()
        if data.is_shortcut:
            shortcut = data.data
            # Shortcut
            keys = [unicode(k.toString(k.NativeText)) for k in shortcut['keys']]
            if not keys:
                keys = _('None')
            else:
                keys = ', '.join(keys)
            html = '<h4>%s</h4>%s: %s'%(shortcut['name'], _('Shortcuts'), keys)
        else:
            # Group
            html = '<h2>%s</h2>'%data.data
        doc =  QTextDocument()
        doc.setHtml(html)
        return doc

    def sizeHint(self, option, index):
        if index.row() in self.editing_indices:
            return QSize(200, 200)
        ans = self.to_doc(index).size().toSize()
        #ans.setHeight(ans.height()+10)
        return ans

    def paint(self, painter, option, index):
        painter.save()
        painter.setClipRect(QRectF(option.rect))
        if hasattr(QStyle, 'CE_ItemViewItem'):
            QApplication.style().drawControl(QStyle.CE_ItemViewItem, option, painter)
        elif option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        painter.translate(option.rect.topLeft())
        self.to_doc(index).drawContents(painter)
        painter.restore()

# }}}

class ShortcutConfig(QWidget):

    changed_signal = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._layout = QHBoxLayout()
        self.setLayout(self._layout)
        self.view = QTreeView(self)
        self.view.setAlternatingRowColors(True)
        self.view.setHeaderHidden(True)
        self.view.setAnimated(True)
        self._layout.addWidget(self.view)
        self.delegate = Delegate()
        self.view.setItemDelegate(self.delegate)
        self.delegate.sizeHintChanged.connect(self.scrollTo)

    def initialize(self, keyboard):
        self._model = ConfigModel(keyboard, parent=self)
        self.view.setModel(self._model)

    def scrollTo(self, index):
        self.view.scrollTo(index)

    @property
    def is_editing(self):
        return self.view.state() == self.view.EditingState


