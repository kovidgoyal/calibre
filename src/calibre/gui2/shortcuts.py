#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt5.Qt import (
    QAbstractListModel, Qt, QKeySequence, QListView, QVBoxLayout, QLabel,
    QHBoxLayout, QWidget, QApplication, QStyledItemDelegate, QStyle, QIcon,
    QTextDocument, QRectF, QFrame, QSize, QFont, QKeyEvent, QRadioButton, QPushButton, QToolButton
)

from calibre.gui2 import error_dialog
from calibre.utils.config import XMLConfig
from calibre.utils.icu import sort_key
from polyglot.builtins import unicode_type

DEFAULTS = Qt.UserRole
DESCRIPTION = Qt.UserRole + 1
CUSTOM = Qt.UserRole + 2
KEY = Qt.UserRole + 3


class Customize(QFrame):

    def __init__(self, index, dup_check, parent=None):
        QFrame.__init__(self, parent)
        self.setFrameShape(self.StyledPanel)
        self.setFrameShadow(self.Raised)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAutoFillBackground(True)
        self.l = l = QVBoxLayout(self)
        self.header = la = QLabel(self)
        la.setWordWrap(True)
        l.addWidget(la)
        self.default_shortcuts = QRadioButton(_("&Default"), self)
        self.custom = QRadioButton(_("&Custom"), self)
        self.custom.toggled.connect(self.custom_toggled)
        l.addWidget(self.default_shortcuts)
        l.addWidget(self.custom)
        for which in 1, 2:
            la = QLabel(_("&Shortcut:") if which == 1 else _("&Alternate shortcut:"))
            setattr(self, 'label%d' % which, la)
            h = QHBoxLayout()
            l.addLayout(h)
            h.setContentsMargins(25, -1, -1, -1)
            h.addWidget(la)
            b = QPushButton(_("Click to change"), self)
            la.setBuddy(b)
            b.clicked.connect(partial(self.capture_clicked, which=which))
            b.installEventFilter(self)
            setattr(self, 'button%d' % which, b)
            h.addWidget(b)
            c = QToolButton(self)
            c.setIcon(QIcon(I('clear_left.png')))
            c.setToolTip(_('Clear'))
            h.addWidget(c)
            c.clicked.connect(partial(self.clear_clicked, which=which))
            setattr(self, 'clear%d' % which, c)
        self.data_model = index.model()
        self.capture = 0
        self.key = None
        self.shorcut1 = self.shortcut2 = None
        self.dup_check = dup_check
        self.custom_toggled(False)

    def eventFilter(self, obj, event):
        if self.capture == 0 or obj not in (self.button1, self.button2):
            return QFrame.eventFilter(self, obj, event)
        t = event.type()
        if t == event.ShortcutOverride:
            event.accept()
            return True
        if t == event.KeyPress:
            self.key_press_event(event, 1 if obj is self.button1 else 2)
            return True
        return QFrame.eventFilter(self, obj, event)

    def clear_button(self, which):
        b = getattr(self, 'button%d' % which)
        s = getattr(self, 'shortcut%d' % which, None)
        b.setText(_('None') if s is None else s.toString(QKeySequence.NativeText))
        b.setFont(QFont())

    def clear_clicked(self, which=0):
        setattr(self, 'shortcut%d'%which, None)
        self.clear_button(which)

    def custom_toggled(self, checked):
        for w in ('1', '2'):
            for o in ('label', 'button', 'clear'):
                getattr(self, o+w).setEnabled(checked)

    def capture_clicked(self, which=1):
        self.capture = which
        for w in 1, 2:
            self.clear_button(w)
        button = getattr(self, 'button%d'%which)
        button.setText(_('Press a key...'))
        button.setFocus(Qt.OtherFocusReason)
        font = QFont()
        font.setBold(True)
        button.setFont(font)

    def key_press_event(self, ev, which=0):
        code = ev.key()
        if self.capture == 0 or code in (0, Qt.Key_unknown,
                Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta,
                Qt.Key_AltGr, Qt.Key_CapsLock, Qt.Key_NumLock, Qt.Key_ScrollLock):
            return QWidget.keyPressEvent(self, ev)
        sequence = QKeySequence(code|(int(ev.modifiers()) & (~Qt.KeypadModifier)))
        setattr(self, 'shortcut%d'%which, sequence)
        self.clear_button(which)
        self.capture = 0
        dup_desc = self.dup_check(sequence, self.key)
        if dup_desc is not None:
            error_dialog(self, _('Already assigned'),
                    unicode_type(sequence.toString(QKeySequence.NativeText)) + ' ' +
                    _('already assigned to') + ' ' + dup_desc, show=True)
            self.clear_clicked(which=which)


class Delegate(QStyledItemDelegate):

    def __init__(self, parent=None):
        QStyledItemDelegate.__init__(self, parent)
        self.editing_indices = {}
        self.closeEditor.connect(self.editing_done)

    def to_doc(self, index):
        doc =  QTextDocument()
        doc.setHtml(index.data())
        return doc

    def editing_done(self, editor, hint):
        remove = None
        for row, w in self.editing_indices.items():
            remove = (row, w.data_model.index(row))
        if remove is not None:
            self.editing_indices.pop(remove[0])
            self.sizeHintChanged.emit(remove[1])

    def sizeHint(self, option, index):
        if index.row() in self.editing_indices:
            return QSize(200, 200)
        ans = self.to_doc(index).size().toSize()
        ans.setHeight(ans.height()+10)
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
        w = Customize(index, index.model().duplicate_check, parent=parent)
        self.editing_indices[index.row()] = w
        self.sizeHintChanged.emit(index)
        return w

    def setEditorData(self, editor, index):
        defs = index.data(DEFAULTS)
        defs = _(' or ').join([unicode_type(x.toString(x.NativeText)) for x in defs])
        editor.key = unicode_type(index.data(KEY))
        editor.default_shortcuts.setText(_('&Default') + ': %s' % defs)
        editor.default_shortcuts.setChecked(True)
        editor.header.setText('<b>%s: %s</b>'%(_('Customize shortcuts for'),
            unicode_type(index.data(DESCRIPTION))))
        custom = index.data(CUSTOM)
        if custom:
            editor.custom.setChecked(True)
            for x in (0, 1):
                button = getattr(editor, 'button%d'%(x+1))
                if len(custom) > x:
                    seq = QKeySequence(custom[x])
                    button.setText(seq.toString(seq.NativeText))
                    setattr(editor, 'shortcut%d'%(x+1), seq)

    def setModelData(self, editor, model, index):
        self.closeEditor.emit(editor, self.NoHint)
        custom = []
        if editor.custom.isChecked():
            for x in ('1', '2'):
                sc = getattr(editor, 'shortcut'+x, None)
                if sc is not None:
                    custom.append(sc)

        model.set_data(index, custom)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)


class Shortcuts(QAbstractListModel):

    TEMPLATE = '''
    <p><b>{0}</b><br>
    {2}: <code>{1}</code></p>
    '''

    def __init__(self, shortcuts, config_file_base_name, parent=None):
        QAbstractListModel.__init__(self, parent)

        self.descriptions = {}
        for k, v in shortcuts.items():
            self.descriptions[k] = v[-1]
        self.keys = {}
        for k, v in shortcuts.items():
            self.keys[k] = v[0]
        self.order = list(shortcuts)
        self.order.sort(key=lambda x : sort_key(self.descriptions[x]))
        self.sequences = {}
        for k, v in self.keys.items():
            self.sequences[k] = [QKeySequence(x) for x in v]

        self.custom = XMLConfig(config_file_base_name)

    def rowCount(self, parent):
        return len(self.order)

    def get_sequences(self, key):
        custom = self.custom.get(key, [])
        if custom:
            return [QKeySequence(x) for x in custom]
        return self.sequences[key]

    def get_match(self, event_or_sequence, ignore=tuple()):
        q = event_or_sequence
        if isinstance(q, QKeyEvent):
            q = QKeySequence(q.key()|(int(q.modifiers()) & (~Qt.KeypadModifier)))
        for key in self.order:
            if key not in ignore:
                for seq in self.get_sequences(key):
                    if seq.matches(q) == QKeySequence.ExactMatch:
                        return key
        return None

    def duplicate_check(self, seq, ignore):
        key = self.get_match(seq, ignore=[ignore])
        if key is not None:
            return self.descriptions[key]

    def get_shortcuts(self, key):
        return [unicode_type(x.toString(x.NativeText)) for x in
                self.get_sequences(key)]

    def data(self, index, role):
        row = index.row()
        if row < 0 or row >= len(self.order):
            return None
        key = self.order[row]
        if role == Qt.DisplayRole:
            return self.TEMPLATE.format(self.descriptions[key],
                    _(' or ').join(self.get_shortcuts(key)), _('Keys'))
        if role == Qt.ToolTipRole:
            return _('Double click to change')
        if role == DEFAULTS:
            return self.sequences[key]
        if role == DESCRIPTION:
            return self.descriptions[key]
        if role == CUSTOM:
            if key in self.custom:
                return self.custom[key]
            else:
                return []
        if role == KEY:
            return key
        return None

    def set_data(self, index, custom):
        key = self.order[index.row()]
        if custom:
            self.custom[key] = [unicode_type(x.toString(QKeySequence.PortableText)) for x in custom]
        elif key in self.custom:
            del self.custom[key]

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        return QAbstractListModel.flags(self, index) | Qt.ItemIsEditable


class ShortcutConfig(QWidget):

    def __init__(self, model, parent=None):
        QWidget.__init__(self, parent)
        self._layout = QHBoxLayout()
        self.setLayout(self._layout)
        self.view = QListView(self)
        self._layout.addWidget(self.view)
        self.view.setModel(model)
        self.delegate = Delegate()
        self.view.setItemDelegate(self.delegate)
        self.delegate.sizeHintChanged.connect(self.scrollTo,
                type=Qt.QueuedConnection)

    def scrollTo(self, index):
        self.view.scrollTo(index, self.view.EnsureVisible)

    @property
    def is_editing(self):
        return self.view.state() == self.view.EditingState


if __name__ == '__main__':
    app = QApplication([])
    from calibre.gui2.viewer.keys import SHORTCUTS
    model = Shortcuts(SHORTCUTS, 'shortcuts/viewer')
    conf = ShortcutConfig(model)
    conf.resize(400, 500)
    conf.show()
    app.exec_()
