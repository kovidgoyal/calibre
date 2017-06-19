#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial
import textwrap
from collections import OrderedDict

from calibre.gui2.preferences import ConfigWidgetBase, test_widget, AbortCommit
from calibre.gui2.search_box import SearchBox2
from calibre.gui2 import error_dialog, info_dialog
from calibre.utils.config import read_raw_tweaks, write_tweaks
from calibre.gui2.widgets import PythonHighlighter
from calibre import isbytestring
from calibre.utils.icu import lower
from calibre.utils.search_query_parser import (ParseException,
        SearchQueryParser)

from PyQt5.Qt import (
    QAbstractListModel, Qt, QStyledItemDelegate, QStyle, QStyleOptionViewItem,
    QFont, QDialogButtonBox, QDialog, QApplication, QVBoxLayout,
    QPlainTextEdit, QLabel, QModelIndex, QMenu, QIcon, QListView, QGridLayout,
    QSizePolicy, QGroupBox, QWidget, QPushButton, QSplitter, pyqtSignal)

ROOT = QModelIndex()


class AdaptSQP(SearchQueryParser):

    def __init__(self, *args, **kwargs):
        pass


class Delegate(QStyledItemDelegate):  # {{{

    def __init__(self, view):
        QStyledItemDelegate.__init__(self, view)
        self.view = view

    def paint(self, p, opt, idx):
        copy = QStyleOptionViewItem(opt)
        copy.showDecorationSelected = True
        if self.view.currentIndex() == idx:
            copy.state |= QStyle.State_HasFocus
        QStyledItemDelegate.paint(self, p, copy, idx)

# }}}


class Tweak(object):  # {{{

    def __init__(self, name, doc, var_names, defaults, custom):
        translate = _
        self.name = translate(name)
        self.doc = doc.strip()
        if self.doc:
            self.doc = translate(self.doc)
        self.var_names = var_names
        if self.var_names:
            self.doc = u"%s: %s\n\n%s"%(_('ID'), self.var_names[0], self.doc)
        self.default_values = OrderedDict()
        for x in var_names:
            self.default_values[x] = defaults[x]
        self.custom_values = OrderedDict()
        for x in var_names:
            if x in custom:
                self.custom_values[x] = custom[x]

    def __str__(self):
        ans = ['#: ' + self.name]
        for line in self.doc.splitlines():
            if line:
                ans.append('# ' + line)
        for key, val in self.default_values.iteritems():
            val = self.custom_values.get(key, val)
            ans.append('%s = %r'%(key, val))
        ans = '\n'.join(ans)
        if isinstance(ans, unicode):
            ans = ans.encode('utf-8')
        return ans

    def __cmp__(self, other):
        return -1 * cmp(self.is_customized,
                            getattr(other, 'is_customized', False))

    @property
    def is_customized(self):
        for x, val in self.default_values.iteritems():
            if self.custom_values.get(x, val) != val:
                return True
        return False

    @property
    def edit_text(self):
        ans = ['# %s'%self.name]
        for x, val in self.default_values.iteritems():
            val = self.custom_values.get(x, val)
            ans.append('%s = %r'%(x, val))
        return '\n\n'.join(ans)

    def restore_to_default(self):
        self.custom_values.clear()

    def update(self, varmap):
        self.custom_values.update(varmap)

# }}}


class Tweaks(QAbstractListModel, AdaptSQP):  # {{{

    def __init__(self, parent=None):
        QAbstractListModel.__init__(self, parent)
        SearchQueryParser.__init__(self, ['all'])
        raw_defaults, raw_custom = read_raw_tweaks()

        self.parse_tweaks(raw_defaults, raw_custom)

    def rowCount(self, *args):
        return len(self.tweaks)

    def data(self, index, role):
        row = index.row()
        try:
            tweak = self.tweaks[row]
        except:
            return None
        if role == Qt.DisplayRole:
            return textwrap.fill(tweak.name, 40)
        if role == Qt.FontRole and tweak.is_customized:
            ans = QFont()
            ans.setBold(True)
            return ans
        if role == Qt.ToolTipRole:
            tt = _('This tweak has it default value')
            if tweak.is_customized:
                tt = '<p>'+_('This tweak has been customized')
                tt += '<pre>'
                for varn, val in tweak.custom_values.iteritems():
                    tt += '%s = %r\n\n'%(varn, val)
            return textwrap.fill(tt)
        if role == Qt.UserRole:
            return tweak
        return None

    def parse_tweaks(self, defaults, custom):
        l, g = {}, {}
        try:
            exec(custom, g, l)
        except:
            print 'Failed to load custom tweaks file'
            import traceback
            traceback.print_exc()
        dl, dg = {}, {}
        exec(defaults, dg, dl)
        lines = defaults.splitlines()
        pos = 0
        self.tweaks = []
        while pos < len(lines):
            line = lines[pos]
            if line.startswith('#:'):
                pos = self.read_tweak(lines, pos, dl, l)
            pos += 1

        self.tweaks.sort()
        default_keys = set(dl.iterkeys())
        custom_keys = set(l.iterkeys())

        self.plugin_tweaks = {}
        for key in custom_keys - default_keys:
            self.plugin_tweaks[key] = l[key]

    def read_tweak(self, lines, pos, defaults, custom):
        name = lines[pos][2:].strip()
        doc, var_names = [], []
        while True:
            pos += 1
            line = lines[pos]
            if not line.startswith('#'):
                break
            doc.append(line[1:].strip())
        doc = '\n'.join(doc)
        while True:
            try:
                line = lines[pos]
            except IndexError:
                break
            if not line.strip():
                break
            spidx1 = line.find(' ')
            spidx2 = line.find('=')
            spidx = spidx1 if spidx1 > 0 and (spidx2 == 0 or spidx2 > spidx1) else spidx2
            if spidx > 0:
                var = line[:spidx]
                if var not in defaults:
                    raise ValueError('%r not in default tweaks dict'%var)
                var_names.append(var)
            pos += 1
        if not var_names:
            raise ValueError('Failed to find any variables for %r'%name)
        self.tweaks.append(Tweak(name, doc, var_names, defaults, custom))
        # print '\n\n', self.tweaks[-1]
        return pos

    def restore_to_default(self, idx):
        tweak = self.data(idx, Qt.UserRole)
        if tweak is not None:
            tweak.restore_to_default()
            self.dataChanged.emit(idx, idx)

    def restore_to_defaults(self):
        for r in range(self.rowCount()):
            self.restore_to_default(self.index(r))
        self.plugin_tweaks = {}

    def update_tweak(self, idx, varmap):
        tweak = self.data(idx, Qt.UserRole)
        if tweak is not None:
            tweak.update(varmap)
            self.dataChanged.emit(idx, idx)

    def to_string(self):
        ans = ['#!/usr/bin/env python',
               '# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai', '',
               '# This file was automatically generated by calibre, do not'
               ' edit it unless you know what you are doing.', '',
            ]
        for tweak in self.tweaks:
            ans.extend(['', str(tweak), ''])

        if self.plugin_tweaks:
            ans.extend(['', '',
                '# The following are tweaks for installed plugins', ''])
            for key, val in self.plugin_tweaks.iteritems():
                ans.extend(['%s = %r'%(key, val), '', ''])
        return '\n'.join(ans)

    @property
    def plugin_tweaks_string(self):
        ans = []
        for key, val in self.plugin_tweaks.iteritems():
            ans.extend(['%s = %r'%(key, val), '', ''])
        ans = '\n'.join(ans)
        if isbytestring(ans):
            ans = ans.decode('utf-8')
        return ans

    def set_plugin_tweaks(self, d):
        self.plugin_tweaks = d

    def universal_set(self):
        return set(xrange(self.rowCount()))

    def get_matches(self, location, query, candidates=None):
        if candidates is None:
            candidates = self.universal_set()
        ans = set()
        if not query:
            return ans
        query = lower(query)
        for r in candidates:
            dat = self.data(self.index(r), Qt.UserRole)
            var_names = u' '.join(dat.default_values)
            if query in lower(dat.name) or query in lower(var_names):
                ans.add(r)
        return ans

    def find(self, query):
        query = query.strip()
        if not query:
            return ROOT
        matches = self.parse(query)
        if not matches:
            return ROOT
        matches = list(sorted(matches))
        return self.index(matches[0])

    def find_next(self, idx, query, backwards=False):
        query = query.strip()
        if not query:
            return idx
        matches = self.parse(query)
        if not matches:
            return idx
        loc = idx.row()
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
        return self.index(ans)

# }}}


class PluginTweaks(QDialog):  # {{{

    def __init__(self, raw, parent=None):
        QDialog.__init__(self, parent)
        self.setWindowTitle(_('Plugin tweaks'))
        self.edit = QPlainTextEdit(self)
        self.highlighter = PythonHighlighter(self.edit.document())
        self.l = QVBoxLayout()
        self.setLayout(self.l)
        self.msg = QLabel(
            _('Add/edit tweaks for any custom plugins you have installed. '
                'Documentation for these tweaks should be available '
                'on the website from where you downloaded the plugins.'))
        self.msg.setWordWrap(True)
        self.l.addWidget(self.msg)
        self.l.addWidget(self.edit)
        self.edit.setPlainText(raw)
        self.bb = QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel,
                Qt.Horizontal, self)
        self.bb.accepted.connect(self.accept)
        self.bb.rejected.connect(self.reject)
        self.l.addWidget(self.bb)
        self.resize(550, 300)

# }}}


class TweaksView(QListView):

    current_changed = pyqtSignal(object, object)

    def __init__(self, parent=None):
        QListView.__init__(self, parent)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.setAlternatingRowColors(True)
        self.setSpacing(5)
        self.setUniformItemSizes(True)
        self.setVerticalScrollMode(self.ScrollPerPixel)

    def currentChanged(self, cur, prev):
        QListView.currentChanged(self, cur, prev)
        self.current_changed.emit(cur, prev)


class ConfigWidget(ConfigWidgetBase):

    def setupUi(self, x):
        self.l = l = QVBoxLayout(self)
        self.la1 = la = QLabel(
            _("Values for the tweaks are shown below. Edit them to change the behavior of calibre."
              " Your changes will only take effect <b>after a restart</b> of calibre."))
        l.addWidget(la), la.setWordWrap(True)
        self.splitter = s = QSplitter(self)
        s.setChildrenCollapsible(False)
        l.addWidget(s, 10)

        self.lv = lv = QWidget(self)
        lv.l = l2 = QVBoxLayout(lv)
        l2.setContentsMargins(0, 0, 0, 0)
        self.tweaks_view = tv = TweaksView(self)
        l2.addWidget(tv)
        self.plugin_tweaks_button = b = QPushButton(self)
        b.setToolTip(_("Edit tweaks for any custom plugins you have installed"))
        b.setText(_("&Plugin tweaks"))
        l2.addWidget(b)
        s.addWidget(lv)

        self.lv1 = lv = QWidget(self)
        s.addWidget(lv)
        lv.g = g = QGridLayout(lv)
        g.setContentsMargins(0, 0, 0, 0)

        self.search = sb = SearchBox2(self)
        sb.sizePolicy().setHorizontalStretch(10)
        sb.setSizeAdjustPolicy(sb.AdjustToMinimumContentsLength)
        sb.setMinimumContentsLength(10)
        g.addWidget(self.search, 0, 0, 1, 1)
        self.next_button = b = QPushButton(self)
        b.setIcon(QIcon(I("arrow-down.png")))
        b.setText(_("&Next"))
        g.addWidget(self.next_button, 0, 1, 1, 1)
        self.previous_button = b = QPushButton(self)
        b.setIcon(QIcon(I("arrow-up.png")))
        b.setText(_("&Previous"))
        g.addWidget(self.previous_button, 0, 2, 1, 1)

        self.hb = hb = QGroupBox(self)
        hb.setTitle(_("Help"))
        hb.l = l2 = QVBoxLayout(hb)
        self.help = h = QPlainTextEdit(self)
        l2.addWidget(h)
        h.setLineWrapMode(QPlainTextEdit.NoWrap)
        h.setReadOnly(True)
        g.addWidget(hb, 1, 0, 1, 3)

        self.eb = eb = QGroupBox(self)
        g.addWidget(eb, 2, 0, 1, 3)
        eb.setTitle(_("Edit tweak"))
        eb.g = ebg = QGridLayout(eb)
        self.edit_tweak = et = QPlainTextEdit(self)
        et.setMinimumWidth(400)
        et.setLineWrapMode(QPlainTextEdit.NoWrap)
        ebg.addWidget(et, 0, 0, 1, 2)
        self.restore_default_button = b = QPushButton(self)
        b.setToolTip(_("Restore this tweak to its default value"))
        b.setText(_("&Reset this tweak"))
        ebg.addWidget(b, 1, 0, 1, 1)
        self.apply_button = ab = QPushButton(self)
        ab.setToolTip(_("Apply any changes you made to this tweak"))
        ab.setText(_("&Apply changes to this tweak"))
        ebg.addWidget(ab, 1, 1, 1, 1)

    def genesis(self, gui):
        self.gui = gui
        self.delegate = Delegate(self.tweaks_view)
        self.tweaks_view.setItemDelegate(self.delegate)
        self.tweaks_view.current_changed.connect(self.current_changed)
        self.view = self.tweaks_view
        self.highlighter = PythonHighlighter(self.edit_tweak.document())
        self.restore_default_button.clicked.connect(self.restore_to_default)
        self.apply_button.clicked.connect(self.apply_tweak)
        self.plugin_tweaks_button.clicked.connect(self.plugin_tweaks)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 100)
        self.next_button.clicked.connect(self.find_next)
        self.previous_button.clicked.connect(self.find_previous)
        self.search.initialize('tweaks_search_history', help_text=_('Search for tweak'))
        self.search.search.connect(self.find)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self.show_context_menu)
        self.copy_icon = QIcon(I('edit-copy.png'))

    def show_context_menu(self, point):
        idx = self.tweaks_view.currentIndex()
        if not idx.isValid():
            return True
        tweak = self.tweaks.data(idx, Qt.UserRole)
        self.context_menu = QMenu(self)
        self.context_menu.addAction(self.copy_icon,
                            _('Copy to clipboard'),
                            partial(self.copy_item_to_clipboard,
                                    val=u"%s (%s: %s)"%(tweak.name,
                                                        _('ID'),
                                                        tweak.var_names[0])))
        self.context_menu.popup(self.mapToGlobal(point))
        return True

    def copy_item_to_clipboard(self, val):
        cb = QApplication.clipboard()
        cb.clear()
        cb.setText(val)

    def plugin_tweaks(self):
        raw = self.tweaks.plugin_tweaks_string
        d = PluginTweaks(raw, self)
        if d.exec_() == d.Accepted:
            g, l = {}, {}
            try:
                exec(unicode(d.edit.toPlainText()), g, l)
            except:
                import traceback
                return error_dialog(self, _('Failed'),
                    _('There was a syntax error in your tweak. Click '
                        'the show details button for details.'), show=True,
                    det_msg=traceback.format_exc())
            self.tweaks.set_plugin_tweaks(l)
            self.changed()

    def current_changed(self, current, previous):
        self.tweaks_view.scrollTo(current)
        tweak = self.tweaks.data(current, Qt.UserRole)
        self.help.setPlainText(tweak.doc)
        self.edit_tweak.setPlainText(tweak.edit_text)

    def changed(self, *args):
        self.changed_signal.emit()

    def initialize(self):
        self.tweaks = self._model = Tweaks()
        self.tweaks_view.setModel(self.tweaks)

    def restore_to_default(self, *args):
        idx = self.tweaks_view.currentIndex()
        if idx.isValid():
            self.tweaks.restore_to_default(idx)
            tweak = self.tweaks.data(idx, Qt.UserRole)
            self.edit_tweak.setPlainText(tweak.edit_text)
            self.changed()

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.tweaks.restore_to_defaults()
        self.changed()

    def apply_tweak(self):
        idx = self.tweaks_view.currentIndex()
        if idx.isValid():
            l, g = {}, {}
            try:
                exec(unicode(self.edit_tweak.toPlainText()), g, l)
            except:
                import traceback
                error_dialog(self.gui, _('Failed'),
                        _('There was a syntax error in your tweak. Click '
                            'the "Show details" button for details.'),
                        det_msg=traceback.format_exc(), show=True)
                return
            self.tweaks.update_tweak(idx, l)
            self.changed()

    def commit(self):
        raw = self.tweaks.to_string()
        try:
            exec(raw)
        except:
            import traceback
            error_dialog(self, _('Invalid tweaks'),
                    _('The tweaks you entered are invalid, try resetting the'
                        ' tweaks to default and changing them one by one until'
                        ' you find the invalid setting.'),
                    det_msg=traceback.format_exc(), show=True)
            raise AbortCommit('abort')
        write_tweaks(raw)
        ConfigWidgetBase.commit(self)
        return True

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
        if not idx.isValid():
            return
        self.view.scrollTo(idx)
        self.view.selectionModel().select(idx,
                self.view.selectionModel().ClearAndSelect)
        self.view.setCurrentIndex(idx)

    def find_next(self, *args):
        idx = self.view.currentIndex()
        if not idx.isValid():
            idx = self._model.index(0)
        idx = self._model.find_next(idx,
                unicode(self.search.currentText()))
        self.highlight_index(idx)

    def find_previous(self, *args):
        idx = self.view.currentIndex()
        if not idx.isValid():
            idx = self._model.index(0)
        idx = self._model.find_next(idx,
            unicode(self.search.currentText()), backwards=True)
        self.highlight_index(idx)


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    # Tweaks()
    # test_widget
    test_widget('Advanced', 'Tweaks')
