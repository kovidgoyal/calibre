#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from PyQt5.Qt import QAbstractListModel, Qt, QIcon, \
        QItemSelectionModel

from calibre.gui2.preferences.toolbar_ui import Ui_Form
from calibre.gui2 import gprefs, warning_dialog, error_dialog
from calibre.gui2.preferences import ConfigWidgetBase, test_widget, AbortCommit
from calibre.utils.icu import primary_sort_key


class FakeAction(object):

    def __init__(self, name, gui_name, icon, tooltip=None,
            dont_add_to=frozenset([]), dont_remove_from=frozenset([])):
        self.name = name
        self.action_spec = (gui_name, icon, tooltip, None)
        self.dont_remove_from = dont_remove_from
        self.dont_add_to = dont_add_to


class BaseModel(QAbstractListModel):

    def name_to_action(self, name, gui):
        if name == 'Donate':
            return FakeAction(
                'Donate', _('Donate'), 'donate.png', tooltip=_('Donate to support the development of calibre'),
                dont_add_to=frozenset(['context-menu', 'context-menu-device']))
        if name == 'Location Manager':
            return FakeAction('Location Manager', _('Location Manager'), 'reader.png',
                    _('Switch between library and device views'),
                    dont_add_to=frozenset(['menubar', 'toolbar',
                        'toolbar-child', 'context-menu',
                        'context-menu-device']))
        if name is None:
            return FakeAction('--- '+('Separator')+' ---',
                    '--- '+_('Separator')+' ---', None,
                    dont_add_to=frozenset(['menubar', 'menubar-device']))
        try:
            return gui.iactions[name]
        except:
            return None

    def rowCount(self, parent):
        return len(self._data)

    def data(self, index, role):
        row = index.row()
        action = self._data[row].action_spec
        if role == Qt.DisplayRole:
            text = action[0]
            text = text.replace('&', '')
            if text == _('%d books'):
                text = _('Choose library')
            return (text)
        if role == Qt.DecorationRole:
            if hasattr(self._data[row], 'qaction'):
                icon = self._data[row].qaction.icon()
                if not icon.isNull():
                    return (icon)
            ic = action[1]
            if ic is None:
                ic = 'blank.png'
            return (QIcon(I(ic)))
        if role == Qt.ToolTipRole and action[2] is not None:
            return (action[2])
        return None

    def names(self, indexes):
        rows = [i.row() for i in indexes]
        ans = []
        for i in rows:
            n = self._data[i].name
            if n.startswith('---'):
                n = None
            ans.append(n)
        return ans

    def has_action(self, name):
        for a in self._data:
            if a.name == name:
                return True
        return False


class AllModel(BaseModel):

    def __init__(self, key, gui):
        BaseModel.__init__(self)
        self.gprefs_name = 'action-layout-'+key
        current = gprefs[self.gprefs_name]
        self.gui = gui
        self.key = key
        self._data = self.get_all_actions(current)

    def get_all_actions(self, current):
        all = list(self.gui.iactions.keys()) + ['Donate', 'Location Manager']
        all = [x for x in all if x not in current] + [None]
        all = [self.name_to_action(x, self.gui) for x in all]
        all = [x for x in all if self.key not in x.dont_add_to]

        def sk(ac):
            try:
                return primary_sort_key(ac.action_spec[0])
            except Exception:
                pass
        all.sort(key=sk)
        return all

    def add(self, names):
        actions = []
        for name in names:
            if name is None or name.startswith('---'):
                continue
            actions.append(self.name_to_action(name, self.gui))
        self.beginResetModel()
        self._data.extend(actions)
        self._data.sort()
        self.endResetModel()

    def remove(self, indices, allowed):
        rows = [i.row() for i in indices]
        remove = set([])
        for row in rows:
            ac = self._data[row]
            if ac.name.startswith('---'):
                continue
            if ac.name in allowed:
                remove.add(row)
        ndata = []
        for i, ac in enumerate(self._data):
            if i not in remove:
                ndata.append(ac)
        self.beginResetModel()
        self._data = ndata
        self.endResetModel()

    def restore_defaults(self):
        current = gprefs.defaults[self.gprefs_name]
        self.beginResetModel()
        self._data = self.get_all_actions(current)
        self.endResetModel()


class CurrentModel(BaseModel):

    def __init__(self, key, gui):
        BaseModel.__init__(self)
        self.gprefs_name = 'action-layout-'+key
        current = gprefs[self.gprefs_name]
        self._data = [self.name_to_action(x, gui) for x in current]
        self._data = [x for x in self._data if x is not None]
        self.key = key
        self.gui = gui

    def move(self, idx, delta):
        row = idx.row()
        if row < 0 or row >= len(self._data):
            return
        nrow = row + delta
        if nrow < 0 or nrow >= len(self._data):
            return
        t = self._data[row]
        self._data[row] = self._data[nrow]
        self._data[nrow] = t
        ni = self.index(nrow)
        self.dataChanged.emit(idx, idx)
        self.dataChanged.emit(ni, ni)
        return ni

    def add(self, names):
        actions = []
        reject = set([])
        for name in names:
            ac = self.name_to_action(name, self.gui)
            if self.key in ac.dont_add_to:
                reject.add(ac)
            else:
                actions.append(ac)

        self.beginResetModel()
        self._data.extend(actions)
        self.endResetModel()
        return reject

    def remove(self, indices):
        rows = [i.row() for i in indices]
        remove, rejected = set([]), set([])
        for row in rows:
            ac = self._data[row]
            if self.key in ac.dont_remove_from:
                rejected.add(ac)
                continue
            remove.add(row)
        ndata = []
        for i, ac in enumerate(self._data):
            if i not in remove:
                ndata.append(ac)
        self.beginResetModel()
        self._data = ndata
        self.endResetModel()
        return rejected

    def commit(self):
        old = gprefs[self.gprefs_name]
        new = []
        for x in self._data:
            n = x.name
            if n.startswith('---'):
                n = None
            new.append(n)
        new = tuple(new)
        if new != old:
            defaults = gprefs.defaults[self.gprefs_name]
            if defaults == new:
                del gprefs[self.gprefs_name]
            else:
                gprefs[self.gprefs_name] = new

    def restore_defaults(self):
        current = gprefs.defaults[self.gprefs_name]
        self.beginResetModel()
        self._data =  [self.name_to_action(x, self.gui) for x in current]
        self.endResetModel()


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    LOCATIONS = [
            ('toolbar', _('The main toolbar')),
            ('toolbar-device', _('The main toolbar when a device is connected')),
            ('toolbar-child', _('The optional second toolbar')),
            ('menubar', _('The menubar')),
            ('menubar-device', _('The menubar when a device is connected')),
            ('context-menu', _('The context menu for the books in the '
                'calibre library')),
            ('context-menu-device', _('The context menu for the books on '
                'the device')),
            ('context-menu-cover-browser', _('The context menu for the Cover '
                'browser')),
            ]

    def genesis(self, gui):
        self.models = {}
        self.what.addItem(_('Click to choose toolbar or menu to customize'),
                'blank')
        for key, text in self.LOCATIONS:
            self.what.addItem(text, key)
            all_model = AllModel(key, gui)
            current_model = CurrentModel(key, gui)
            self.models[key] = (all_model, current_model)
        self.what.setCurrentIndex(0)
        self.what.currentIndexChanged[int].connect(self.what_changed)
        self.what_changed(0)

        self.add_action_button.clicked.connect(self.add_action)
        self.remove_action_button.clicked.connect(self.remove_action)
        self.action_up_button.clicked.connect(partial(self.move, -1))
        self.action_down_button.clicked.connect(partial(self.move, 1))
        self.all_actions.setMouseTracking(True)
        self.current_actions.setMouseTracking(True)
        self.all_actions.entered.connect(self.all_entered)
        self.current_actions.entered.connect(self.current_entered)

    def all_entered(self, index):
        tt = self.all_actions.model().data(index, Qt.ToolTipRole) or ''
        self.help_text.setText(tt)

    def current_entered(self, index):
        tt = self.current_actions.model().data(index, Qt.ToolTipRole) or ''
        self.help_text.setText(tt)

    def what_changed(self, idx):
        key = unicode(self.what.itemData(idx) or '')
        if key == 'blank':
            self.actions_widget.setVisible(False)
            self.spacer_widget.setVisible(True)
        else:
            self.actions_widget.setVisible(True)
            self.spacer_widget.setVisible(False)
            self.all_actions.setModel(self.models[key][0])
            self.current_actions.setModel(self.models[key][1])

    def add_action(self, *args):
        x = self.all_actions.selectionModel().selectedIndexes()
        names = self.all_actions.model().names(x)
        if names:
            not_added = self.current_actions.model().add(names)
            ns = set([y.name for y in not_added])
            added = set(names) - ns
            self.all_actions.model().remove(x, added)
            if not_added:
                warning_dialog(self, _('Cannot add'),
                        _('Cannot add the actions %s to this location') %
                        ','.join([a.action_spec[0] for a in not_added]),
                        show=True)
            if added:
                ca = self.current_actions
                idx = ca.model().index(ca.model().rowCount(None)-1)
                ca.scrollTo(idx)
                self.changed_signal.emit()

    def remove_action(self, *args):
        x = self.current_actions.selectionModel().selectedIndexes()
        names = self.current_actions.model().names(x)
        if names:
            not_removed = self.current_actions.model().remove(x)
            ns = set([y.name for y in not_removed])
            removed = set(names) - ns
            self.all_actions.model().add(removed)
            if not_removed:
                warning_dialog(self, _('Cannot remove'),
                        _('Cannot remove the actions %s from this location') %
                        ','.join([a.action_spec[0] for a in not_removed]),
                        show=True)
            else:
                self.changed_signal.emit()

    def move(self, delta, *args):
        ci = self.current_actions.currentIndex()
        m = self.current_actions.model()
        if ci.isValid():
            ni = m.move(ci, delta)
            if ni is not None:
                self.current_actions.setCurrentIndex(ni)
                self.current_actions.selectionModel().select(ni,
                        QItemSelectionModel.ClearAndSelect)
                self.changed_signal.emit()

    def commit(self):
        # Ensure preferences are showing in either the toolbar or
        # the menubar.
        pref_in_toolbar = self.models['toolbar'][1].has_action('Preferences')
        pref_in_menubar = self.models['menubar'][1].has_action('Preferences')
        lm_in_toolbar = self.models['toolbar-device'][1].has_action('Location Manager')
        lm_in_menubar = self.models['menubar-device'][1].has_action('Location Manager')
        if not pref_in_toolbar and not pref_in_menubar:
            error_dialog(self, _('Preferences missing'), _(
                'The Preferences action must be in either the main toolbar or the menubar.'), show=True)
            raise AbortCommit()
        if not lm_in_toolbar and not lm_in_menubar:
            error_dialog(self, _('Location manager missing'), _(
                'The Location manager must be in either the main toolbar or the menubar when a device is connected.'), show=True)
            raise AbortCommit()

        # Save data.
        for am, cm in self.models.values():
            cm.commit()
        return False

    def restore_defaults(self):
        for am, cm in self.models.values():
            cm.restore_defaults()
            am.restore_defaults()
        self.changed_signal.emit()

    def refresh_gui(self, gui):
        gui.bars_manager.init_bars()
        gui.bars_manager.update_bars()


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    test_widget('Interface', 'Toolbar')
