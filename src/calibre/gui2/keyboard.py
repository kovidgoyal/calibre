#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from collections import OrderedDict
from functools import partial

from PyQt4.Qt import (QObject, QKeySequence, QAbstractItemModel, QModelIndex,
        Qt, QStyledItemDelegate, QTextDocument, QStyle, pyqtSignal, QFrame,
        QApplication, QSize, QRectF, QWidget, QTreeView,
        QGridLayout, QLabel, QRadioButton, QPushButton, QToolButton, QIcon)

from calibre.utils.config import JSONConfig
from calibre.constants import DEBUG
from calibre import prints
from calibre.utils.icu import sort_key
from calibre.gui2 import NONE, error_dialog

ROOT = QModelIndex()

class NameConflict(ValueError):
    pass

def finalize(shortcuts, custom_keys_map={}): # {{{
    '''
    Resolve conflicts and assign keys to every action in shorcuts, which must
    be a OrderedDict. User specified mappings of unique names to keys (as a
    list of strings) should be passed in in custom_keys_map. Return a mapping
    of unique names to resolved keys. Also sets the set_to_defaul member
    correctly for each shortcut.
    '''
    seen, keys_map = {}, {}
    for unique_name, shortcut in shortcuts.iteritems():
        custom_keys = custom_keys_map.get(unique_name, None)
        if custom_keys is None:
            candidates = shortcut['default_keys']
            shortcut['set_to_default'] = True
        else:
            candidates = custom_keys
            shortcut['set_to_default'] = False
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

        keys_map[unique_name] = keys
        ac = shortcut['action']
        if ac is not None:
            ac.setShortcuts(list(keys))

    return keys_map

# }}}

class Manager(QObject): # {{{

    def __init__(self, parent=None):
        QObject.__init__(self, parent)

        self.config = JSONConfig('shortcuts/main')
        self.shortcuts = OrderedDict()
        self.keys_map = {}
        self.groups = {}

    def register_shortcut(self, unique_name, name, default_keys=(),
            description=None, action=None, group=None):
        '''
        Register a shortcut with calibre. calibre will manage the shortcut,
        automatically resolving conflicts and allowing the user to customize
        it.

        :param unique_name: A string that uniquely identifies this shortcut
        :param name: A user visible name describing the action performed by
        this shortcut
        :param default_keys: A tuple of keys that trigger this shortcut. Each
        key must be a string. For example: ('Ctrl+A', 'Alt+B', 'C',
        'Shift+Meta_D'). These keys will be assigned to the
        shortcut unless there is a conflict.
        :param action: A QAction object. The shortcut will cause this QAction
        to be triggered. Connect to its triggered signal in your code to
        respond to the shortcut.
        :param group: A string describing what "group" this shortcut belongs
        to. This is used to organize the list of shortcuts when the user is
        customizing them.
        '''
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
        custom_keys_map = {un:tuple(keys) for un, keys in self.config.get(
            'map', {}).iteritems()}
        self.keys_map = finalize(self.shortcuts, custom_keys_map=custom_keys_map)

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

    def __iter__(self):
        for child in self.children:
            yield child

class ConfigModel(QAbstractItemModel):

    def __init__(self, keyboard, parent=None):
        QAbstractItemModel.__init__(self, parent)

        self.keyboard = keyboard
        groups = sorted(keyboard.groups, key=sort_key)
        shortcut_map = {k:v.copy() for k, v in
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

    @property
    def all_shortcuts(self):
        for group in self.data:
            for sc in group:
                yield sc

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

    def flags(self, index):
        ans = QAbstractItemModel.flags(self, index)
        ip = index.internalPointer()
        if getattr(ip, 'is_shortcut', False):
            ans |= Qt.ItemIsEditable
        return ans

    def restore_defaults(self):
        shortcut_map = {}
        for node in self.all_shortcuts:
            sc = node.data
            shortcut_map[sc['unique_name']] = sc
        shortcuts = OrderedDict([(un, shortcut_map[un]) for un in
            self.keyboard.shortcuts])
        keys_map = finalize(shortcuts)
        for node in self.all_shortcuts:
            s = node.data
            s['keys'] = tuple(keys_map[s['unique_name']])
        for r in xrange(self.rowCount()):
            group = self.index(r, 0)
            num = self.rowCount(group)
            if num > 0:
                self.dataChanged.emit(self.index(0, 0, group),
                        self.index(num-1, 0, group))

    def commit(self):
        kmap = {}
        for node in self.all_shortcuts:
            sc = node.data
            if sc['set_to_default']: continue
            keys = [unicode(k.toString(k.PortableText)) for k in sc['keys']]
            kmap[sc['unique_name']] = keys
        self.keyboard.config['map'] = kmap


# }}}

class Editor(QFrame): # {{{

    editing_done = pyqtSignal(object)

    def __init__(self, parent=None):
        QFrame.__init__(self, parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAutoFillBackground(True)
        self.capture = 0

        self.setFrameShape(self.StyledPanel)
        self.setFrameShadow(self.Raised)
        self._layout = l = QGridLayout(self)
        self.setLayout(l)

        self.header = QLabel('')
        l.addWidget(self.header, 0, 0, 1, 2)

        self.use_default = QRadioButton('')
        self.use_custom = QRadioButton(_('Custom'))
        l.addWidget(self.use_default, 1, 0, 1, 3)
        l.addWidget(self.use_custom, 2, 0, 1, 3)
        self.use_custom.toggled.connect(self.custom_toggled)

        off = 2
        for which in (1, 2):
            text = _('&Shortcut:') if which == 1 else _('&Alternate shortcut:')
            la = QLabel(text)
            la.setStyleSheet('QLabel { margin-left: 1.5em }')
            l.addWidget(la, off+which, 0, 1, 3)
            setattr(self, 'label%d'%which, la)
            button = QPushButton(_('None'), self)
            button.clicked.connect(partial(self.capture_clicked, which=which))
            button.keyPressEvent = partial(self.key_press_event, which=which)
            setattr(self, 'button%d'%which, button)
            clear = QToolButton(self)
            clear.setIcon(QIcon(I('clear_left.png')))
            clear.clicked.connect(partial(self.clear_clicked, which=which))
            setattr(self, 'clear%d'%which, clear)
            l.addWidget(button, off+which, 1, 1, 1)
            l.addWidget(clear, off+which, 2, 1, 1)
            la.setBuddy(button)

        self.done_button = doneb = QPushButton(_('Done'), self)
        l.addWidget(doneb, 0, 2, 1, 1)
        doneb.clicked.connect(lambda : self.editing_done.emit(self))
        l.setColumnStretch(0, 100)

        self.custom_toggled(False)

    def initialize(self, shortcut, all_shortcuts):
        self.header.setText('<b>%s: %s</b>'%(_('Customize'), shortcut['name']))
        self.all_shortcuts = all_shortcuts
        self.shortcut = shortcut

        self.default_keys = [QKeySequence(k, QKeySequence.PortableText) for k
                in shortcut['default_keys']]
        self.current_keys = list(shortcut['keys'])
        default = ', '.join([unicode(k.toString(k.NativeText)) for k in
                    self.default_keys])
        if not default: default = _('None')
        current = ', '.join([unicode(k.toString(k.NativeText)) for k in
                    self.current_keys])
        if not current: current = _('None')

        self.use_default.setText(_('Default: %s [Currently not conflicting: %s]')%
                (default, current))

        if shortcut['set_to_default']:
            self.use_default.setChecked(True)
        else:
            self.use_custom.setChecked(True)
            for key, which in zip(self.current_keys, [1,2]):
                button = getattr(self, 'button%d'%which)
                button.setText(key.toString(key.NativeText))

    def custom_toggled(self, checked):
        for w in ('1', '2'):
            for o in ('label', 'button', 'clear'):
                getattr(self, o+w).setEnabled(checked)

    def capture_clicked(self, which=1):
        self.capture = which
        button = getattr(self, 'button%d'%which)
        button.setText(_('Press a key...'))
        button.setFocus(Qt.OtherFocusReason)
        button.setStyleSheet('QPushButton { font-weight: bold}')

    def clear_clicked(self, which=0):
        button = getattr(self, 'button%d'%which)
        button.setText(_('None'))

    def key_press_event(self, ev, which=0):
        code = ev.key()
        if self.capture == 0 or code in (0, Qt.Key_unknown,
                Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta,
                Qt.Key_AltGr, Qt.Key_CapsLock, Qt.Key_NumLock, Qt.Key_ScrollLock):
            return QWidget.keyPressEvent(self, ev)
        button = getattr(self, 'button%d'%which)
        button.setStyleSheet('QPushButton { font-weight: normal}')
        sequence = QKeySequence(code|(int(ev.modifiers())&~Qt.KeypadModifier))
        button.setText(sequence.toString(QKeySequence.NativeText))
        self.capture = 0
        dup_desc = self.dup_check(sequence)
        if dup_desc is not None:
            error_dialog(self, _('Already assigned'),
                    unicode(sequence.toString(QKeySequence.NativeText)) + ' ' +
                    _('already assigned to') + ' ' + dup_desc, show=True)
            self.clear_clicked(which=which)

    def dup_check(self, sequence):
        for sc in self.all_shortcuts:
            if sc is self.shortcut: continue
            for k in sc['keys']:
                if k == sequence:
                    return sc['name']

    @property
    def custom_keys(self):
        if self.use_default.isChecked():
            return None
        ans = []
        for which in (1, 2):
            button = getattr(self, 'button%d'%which)
            t = unicode(button.text())
            if t == _('None'):
                continue
            ks = QKeySequence(t, QKeySequence.NativeText)
            if not ks.isEmpty():
                ans.append(ks)
        return tuple(ans)


# }}}

class Delegate(QStyledItemDelegate): # {{{

    changed_signal = pyqtSignal()

    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)
        self.editing_index = None
        self.closeEditor.connect(self.editing_done)

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
            html = '<b>%s</b><br>%s: %s'%(shortcut['name'], _('Shortcuts'), keys)
        else:
            # Group
            html = '<h3>%s</h3>'%data.data
        doc =  QTextDocument()
        doc.setHtml(html)
        return doc

    def sizeHint(self, option, index):
        if index == self.editing_index:
            return QSize(200, 200)
        ans = self.to_doc(index).size().toSize()
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

    def createEditor(self, parent, option, index):
        w = Editor(parent=parent)
        w.editing_done.connect(self.editor_done)
        self.editing_index = index
        self.sizeHintChanged.emit(index)
        return w

    def editor_done(self, editor):
        self.commitData.emit(editor)

    def setEditorData(self, editor, index):
        all_shortcuts = [x.data for x in index.model().all_shortcuts]
        shortcut = index.internalPointer().data
        editor.initialize(shortcut, all_shortcuts)

    def setModelData(self, editor, model, index):
        self.closeEditor.emit(editor, self.NoHint)
        custom_keys = editor.custom_keys
        sc = index.data(Qt.UserRole).toPyObject().data
        if custom_keys is None:
            candidates = []
            for ckey in sc['default_keys']:
                ckey = QKeySequence(ckey, QKeySequence.PortableText)
                matched = False
                for s in editor.all_shortcuts:
                    for k in s['keys']:
                        if k == ckey:
                            matched = True
                            break
                if not matched:
                    candidates.append(ckey)
            candidates = tuple(candidates)
            sc['set_to_default'] = True
        else:
            sc['set_to_default'] = False
            candidates = custom_keys
        sc['keys'] = candidates
        self.changed_signal.emit()

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def editing_done(self, *args):
        idx = self.editing_index
        self.editing_index = None
        if idx is not None:
            self.sizeHintChanged.emit(idx)

# }}}

class ShortcutConfig(QWidget): # {{{

    changed_signal = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._layout = l = QGridLayout()
        self.setLayout(self._layout)
        self.header = QLabel(_('Double click on any entry to change the'
            ' keyboard shortcuts associated with it'))
        l.addWidget(self.header, 0, 0, 1, 1)
        self.view = QTreeView(self)
        self.view.setAlternatingRowColors(True)
        self.view.setHeaderHidden(True)
        self.view.setAnimated(True)
        l.addWidget(self.view, 1, 0, 1, 1)
        self.delegate = Delegate()
        self.view.setItemDelegate(self.delegate)
        self.delegate.sizeHintChanged.connect(self.scrollTo)
        self.delegate.changed_signal.connect(self.changed_signal)

    def restore_defaults(self):
        self._model.restore_defaults()
        self.changed_signal.emit()

    def commit(self):
        self._model.commit()

    def initialize(self, keyboard):
        self._model = ConfigModel(keyboard, parent=self)
        self.view.setModel(self._model)

    def scrollTo(self, index):
        if index is not None:
            self.view.scrollTo(index, self.view.PositionAtCenter)

    @property
    def is_editing(self):
        return self.view.state() == self.view.EditingState

# }}}

