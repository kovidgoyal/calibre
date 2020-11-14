#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from collections import OrderedDict
from functools import partial

from PyQt5.Qt import (QObject, QKeySequence, QAbstractItemModel, QModelIndex,
        Qt, QStyledItemDelegate, QTextDocument, QStyle, pyqtSignal, QFrame,
        QApplication, QSize, QRectF, QWidget, QTreeView, QHBoxLayout, QVBoxLayout,
        QGridLayout, QLabel, QRadioButton, QPushButton, QToolButton, QIcon)
try:
    from PyQt5 import sip
except ImportError:
    import sip

from calibre.utils.config import JSONConfig
from calibre.constants import DEBUG
from calibre import prints, prepare_string_for_xml
from calibre.utils.icu import sort_key, lower
from calibre.gui2 import error_dialog, info_dialog
from calibre.utils.search_query_parser import SearchQueryParser, ParseException
from calibre.gui2.search_box import SearchBox2
from polyglot.builtins import iteritems, itervalues, unicode_type, range

ROOT = QModelIndex()


class NameConflict(ValueError):
    pass


def keysequence_from_event(ev):  # {{{
    k, mods = ev.key(), int(ev.modifiers())
    if k in (
            0, Qt.Key_unknown, Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt,
            Qt.Key_Meta, Qt.Key_AltGr, Qt.Key_CapsLock, Qt.Key_NumLock,
            Qt.Key_ScrollLock):
        return
    letter = QKeySequence(k).toString(QKeySequence.PortableText)
    if mods & Qt.SHIFT and letter.lower() == letter.upper():
        # Something like Shift+* or Shift+> we have to remove the shift,
        # since it is included in keycode.
        mods = mods & ~Qt.SHIFT
    return QKeySequence(k | mods)
# }}}


def finalize(shortcuts, custom_keys_map={}):  # {{{
    '''
    Resolve conflicts and assign keys to every action in shortcuts, which must
    be a OrderedDict. User specified mappings of unique names to keys (as a
    list of strings) should be passed in in custom_keys_map. Return a mapping
    of unique names to resolved keys. Also sets the set_to_default member
    correctly for each shortcut.
    '''
    seen, keys_map = {}, {}
    for unique_name, shortcut in iteritems(shortcuts):
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
            x = unicode_type(ks.toString(QKeySequence.PortableText))
            if x in seen:
                if DEBUG:
                    prints('Key %r for shortcut %s is already used by'
                            ' %s, ignoring'%(x, shortcut['name'], seen[x]['name']))
                keys_map[unique_name] = ()
                continue
            seen[x] = shortcut
            keys.append(ks)
        keys = tuple(keys)

        keys_map[unique_name] = keys
        ac = shortcut['action']
        if ac is None or sip.isdeleted(ac):
            if ac is not None and DEBUG:
                prints('Shortcut %r has a deleted action' % unique_name)
            continue
        ac.setShortcuts(list(keys))

    return keys_map

# }}}


class Manager(QObject):  # {{{

    def __init__(self, parent=None, config_name='shortcuts/main'):
        QObject.__init__(self, parent)

        self.config = JSONConfig(config_name)
        self.shortcuts = OrderedDict()
        self.keys_map = {}
        self.groups = {}

    def register_shortcut(self, unique_name, name, default_keys=(),
            description=None, action=None, group=None, persist_shortcut=False):
        '''
        Register a shortcut with calibre. calibre will manage the shortcut,
        automatically resolving conflicts and allowing the user to customize
        it.

        :param unique_name: A string that uniquely identifies this shortcut
        :param name: A user visible name describing the action performed by
        this shortcut
        :param default_keys: A tuple of keys that trigger this shortcut. Each
        key must be a string. For example: ('Ctrl+A', 'Alt+B', 'C',
        'Shift+Meta+D'). These keys will be assigned to the
        shortcut unless there is a conflict.
        :param action: A QAction object. The shortcut will cause this QAction
        to be triggered. Connect to its triggered signal in your code to
        respond to the shortcut.
        :param group: A string describing what "group" this shortcut belongs
        to. This is used to organize the list of shortcuts when the user is
        customizing them.
        :persist_shortcut: Shortcuts for actions that don't always
        appear, or are library dependent, may disappear when other
        keyboard shortcuts are edited unless ```persist_shortcut``` is
        set True.
        '''
        if unique_name in self.shortcuts:
            name = self.shortcuts[unique_name]['name']
            raise NameConflict('Shortcut for %r already registered by %s'%(
                    unique_name, name))
        shortcut = {'name':name, 'desc':description, 'action': action,
                'default_keys':tuple(default_keys),
                'persist_shortcut':persist_shortcut}
        self.shortcuts[unique_name] = shortcut
        group = group if group else _('Miscellaneous')
        self.groups[group] = self.groups.get(group, []) + [unique_name]

    def unregister_shortcut(self, unique_name):
        '''
        Remove a registered shortcut. You need to call finalize() after you are
        done unregistering.
        '''
        self.shortcuts.pop(unique_name, None)
        for group in itervalues(self.groups):
            try:
                group.remove(unique_name)
            except ValueError:
                pass

    def finalize(self):
        custom_keys_map = {un:tuple(keys) for un, keys in iteritems(self.config.get(
            'map', {}))}
        self.keys_map = finalize(self.shortcuts, custom_keys_map=custom_keys_map)

    def replace_action(self, unique_name, new_action):
        '''
        Replace the action associated with a shortcut.
        Once you're done calling replace_action() for all shortcuts you want
        replaced, call finalize() to have the shortcuts assigned to the replaced
        actions.
        '''
        sc = self.shortcuts[unique_name]
        sc['action'] = new_action

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


class ConfigModel(SearchQueryParser, QAbstractItemModel):

    def __init__(self, keyboard, parent=None):
        QAbstractItemModel.__init__(self, parent)
        SearchQueryParser.__init__(self, ['all'])

        self.keyboard = keyboard
        groups = sorted(keyboard.groups, key=sort_key)
        shortcut_map = {k:v.copy() for k, v in
                iteritems(self.keyboard.shortcuts)}
        for un, s in iteritems(shortcut_map):
            s['keys'] = tuple(self.keyboard.keys_map.get(un, ()))
            s['unique_name'] = un
            s['group'] = [g for g, names in iteritems(self.keyboard.groups) if un in
                    names][0]

        group_map = {group:sorted(names, key=lambda x:
                sort_key(shortcut_map[x]['name'])) for group, names in
                iteritems(self.keyboard.groups)}

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
        return None

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
        for r in range(self.rowCount()):
            group = self.index(r, 0)
            num = self.rowCount(group)
            if num > 0:
                self.dataChanged.emit(self.index(0, 0, group),
                        self.index(num-1, 0, group))

    def commit(self):
        kmap = {}
        # persist flags not in map for back compat
        # not *just* persist flag for forward compat
        options_map = {}
        options_map.update(self.keyboard.config.get('options_map', {}))
        # keep mapped keys that are marked persistent.
        for un, keys in iteritems(self.keyboard.config.get('map', {})):
            if options_map.get(un, {}).get('persist_shortcut',False):
                kmap[un] = keys
        for node in self.all_shortcuts:
            sc = node.data
            un = sc['unique_name']
            if sc['set_to_default']:
                if un in kmap:
                    del kmap[un]
                if un in options_map:
                    del options_map[un]
            else:
                if sc['persist_shortcut']:
                    options_map[un] = options_map.get(un, {})
                    options_map[un]['persist_shortcut'] = sc['persist_shortcut']
                keys = [unicode_type(k.toString(k.PortableText)) for k in sc['keys']]
                kmap[un] = keys
        with self.keyboard.config:
            self.keyboard.config['map'] = kmap
            self.keyboard.config['options_map'] = options_map

    def universal_set(self):
        ans = set()
        for i, group in enumerate(self.data):
            ans.add((i, -1))
            for j, sc in enumerate(group.children):
                ans.add((i, j))
        return ans

    def get_matches(self, location, query, candidates=None):
        if candidates is None:
            candidates = self.universal_set()
        ans = set()
        if not query:
            return ans
        query = lower(query)
        for c, p in candidates:
            if p < 0:
                if query in lower(self.data[c].data):
                    ans.add((c, p))
            else:
                try:
                    sc = self.data[c].children[p].data
                except:
                    continue
                if query in lower(sc['name']):
                    ans.add((c, p))
        return ans

    def find(self, query):
        query = query.strip()
        if not query:
            return ROOT
        matches = self.parse(query)
        if not matches:
            return ROOT
        matches = list(sorted(matches))
        c, p = matches[0]
        cat_idx = self.index(c, 0)
        if p == -1:
            return cat_idx
        return self.index(p, 0, cat_idx)

    def find_next(self, idx, query, backwards=False):
        query = query.strip()
        if not query:
            return idx
        matches = self.parse(query)
        if not matches:
            return idx
        if idx.parent().isValid():
            loc = (idx.parent().row(), idx.row())
        else:
            loc = (idx.row(), -1)
        if loc not in matches:
            return self.find(query)
        if len(matches) == 1:
            return ROOT
        matches = list(sorted(matches))
        i = matches.index(loc)
        if backwards:
            ans = i - 1 if i - 1 >= 0 else len(matches)-1
        else:
            ans = i + 1 if i + 1 < len(matches) else 0

        ans = matches[ans]

        return (self.index(ans[0], 0) if ans[1] < 0 else
                self.index(ans[1], 0, self.index(ans[0], 0)))

    def index_for_group(self, name):
        for i in range(self.rowCount()):
            node = self.data[i]
            if node.data == name:
                return self.index(i, 0)

    @property
    def group_names(self):
        for i in range(self.rowCount()):
            node = self.data[i]
            yield node.data

# }}}


class Editor(QFrame):  # {{{

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
        self.use_custom = QRadioButton(_('&Custom'))
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
            button.installEventFilter(self)
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
        default = ', '.join([unicode_type(k.toString(k.NativeText)) for k in
                    self.default_keys])
        if not default:
            default = _('None')
        current = ', '.join([unicode_type(k.toString(k.NativeText)) for k in
                    self.current_keys])
        if not current:
            current = _('None')

        self.use_default.setText(_('&Default: %(deflt)s [Currently not conflicting: %(curr)s]')%
                dict(deflt=default, curr=current))

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

    def eventFilter(self, obj, event):
        if self.capture and obj in (self.button1, self.button2):
            t = event.type()
            if t == event.ShortcutOverride:
                event.accept()
                return True
            if t == event.KeyPress:
                self.key_press_event(event, 1 if obj is self.button1 else 2)
                return True
        return QFrame.eventFilter(self, obj, event)

    def key_press_event(self, ev, which=0):
        if self.capture == 0:
            return QWidget.keyPressEvent(self, ev)
        sequence = keysequence_from_event(ev)
        if sequence is None:
            return QWidget.keyPressEvent(self, ev)
        ev.accept()

        button = getattr(self, 'button%d'%which)
        button.setStyleSheet('QPushButton { font-weight: normal}')
        button.setText(sequence.toString(QKeySequence.NativeText))
        self.capture = 0
        dup_desc = self.dup_check(sequence)
        if dup_desc is not None:
            error_dialog(self, _('Already assigned'),
                    unicode_type(sequence.toString(QKeySequence.NativeText)) + ' ' + _(
                        'already assigned to') + ' ' + dup_desc, show=True)
            self.clear_clicked(which=which)

    def dup_check(self, sequence):
        for sc in self.all_shortcuts:
            if sc is self.shortcut:
                continue
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
            t = unicode_type(button.text())
            if t == _('None'):
                continue
            ks = QKeySequence(t, QKeySequence.NativeText)
            if not ks.isEmpty():
                ans.append(ks)
        return tuple(ans)


# }}}

class Delegate(QStyledItemDelegate):  # {{{

    changed_signal = pyqtSignal()

    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)
        self.editing_index = None
        self.closeEditor.connect(self.editing_done)

    def to_doc(self, index):
        data = index.data(Qt.UserRole)
        if data is None:
            html = _('<b>This shortcut no longer exists</b>')
        elif data.is_shortcut:
            shortcut = data.data
            # Shortcut
            keys = [unicode_type(k.toString(k.NativeText)) for k in shortcut['keys']]
            if not keys:
                keys = _('None')
            else:
                keys = ', '.join(keys)
            html = '<b>%s</b><br>%s: %s'%(
                prepare_string_for_xml(shortcut['name']), _('Shortcuts'), prepare_string_for_xml(keys))
        else:
            # Group
            html = data.data
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
        self.current_editor = w
        self.sizeHintChanged.emit(index)
        return w

    def accept_changes(self):
        self.editor_done(self.current_editor)

    def editor_done(self, editor):
        self.commitData.emit(editor)

    def setEditorData(self, editor, index):
        all_shortcuts = [x.data for x in index.model().all_shortcuts]
        shortcut = index.internalPointer().data
        editor.initialize(shortcut, all_shortcuts)

    def setModelData(self, editor, model, index):
        self.closeEditor.emit(editor, self.NoHint)
        custom_keys = editor.custom_keys
        sc = index.data(Qt.UserRole).data
        if custom_keys is None:
            candidates = []
            for ckey in sc['default_keys']:
                ckey = QKeySequence(ckey, QKeySequence.PortableText)
                matched = False
                for s in editor.all_shortcuts:
                    if s is editor.shortcut:
                        continue
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
        self.current_editor = None
        idx = self.editing_index
        self.editing_index = None
        if idx is not None:
            self.sizeHintChanged.emit(idx)

# }}}


class ShortcutConfig(QWidget):  # {{{

    changed_signal = pyqtSignal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        self._layout = l = QVBoxLayout(self)
        self.header = QLabel(_('Double click on any entry to change the'
            ' keyboard shortcuts associated with it'))
        l.addWidget(self.header)
        self.view = QTreeView(self)
        self.view.setAlternatingRowColors(True)
        self.view.setHeaderHidden(True)
        self.view.setAnimated(True)
        l.addWidget(self.view)
        self.delegate = Delegate()
        self.view.setItemDelegate(self.delegate)
        self.delegate.sizeHintChanged.connect(self.editor_opened,
                type=Qt.QueuedConnection)
        self.delegate.changed_signal.connect(self.changed_signal)
        self.search = SearchBox2(self)
        self.search.initialize('shortcuts_search_history',
                help_text=_('Search for a shortcut by name'))
        self.search.search.connect(self.find)
        self._h = h = QHBoxLayout()
        l.addLayout(h)
        h.addWidget(self.search)
        self.nb = QPushButton(QIcon(I('arrow-down.png')), _('&Next'), self)
        self.pb = QPushButton(QIcon(I('arrow-up.png')), _('&Previous'), self)
        self.nb.clicked.connect(self.find_next)
        self.pb.clicked.connect(self.find_previous)
        h.addWidget(self.nb), h.addWidget(self.pb)
        h.setStretch(0, 100)

    def restore_defaults(self):
        self._model.restore_defaults()
        self.changed_signal.emit()

    def commit(self):
        if self.view.state() == self.view.EditingState:
            self.delegate.accept_changes()
        self._model.commit()

    def initialize(self, keyboard):
        self._model = ConfigModel(keyboard, parent=self)
        self.view.setModel(self._model)

    def editor_opened(self, index):
        self.view.scrollTo(index, self.view.EnsureVisible)

    @property
    def is_editing(self):
        return self.view.state() == self.view.EditingState

    def find(self, query):
        if not query:
            return
        try:
            idx = self._model.find(query)
        except ParseException:
            self.search.search_done(False)
            return
        self.search.search_done(True)
        if not idx.isValid():
            info_dialog(self, _('No matches'),
                    _('Could not find any shortcuts matching %s')%query,
                    show=True, show_copy_button=False)
            return
        self.highlight_index(idx)

    def highlight_index(self, idx):
        self.view.scrollTo(idx)
        self.view.selectionModel().select(idx,
                self.view.selectionModel().ClearAndSelect)
        self.view.setCurrentIndex(idx)
        self.view.setFocus(Qt.OtherFocusReason)

    def find_next(self, *args):
        idx = self.view.currentIndex()
        if not idx.isValid():
            idx = self._model.index(0, 0)
        idx = self._model.find_next(idx,
                unicode_type(self.search.currentText()))
        self.highlight_index(idx)

    def find_previous(self, *args):
        idx = self.view.currentIndex()
        if not idx.isValid():
            idx = self._model.index(0, 0)
        idx = self._model.find_next(idx,
            unicode_type(self.search.currentText()), backwards=True)
        self.highlight_index(idx)

    def highlight_group(self, group_name):
        idx = self.view.model().index_for_group(group_name)
        if idx is not None:
            self.view.expand(idx)
            self.view.scrollTo(idx, self.view.PositionAtTop)
            self.view.selectionModel().select(idx,
                    self.view.selectionModel().ClearAndSelect)
            self.view.setCurrentIndex(idx)
            self.view.setFocus(Qt.OtherFocusReason)

# }}}
