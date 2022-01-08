#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from qt.core import QAbstractListModel, Qt, QIcon, QItemSelectionModel

from calibre import force_unicode
from calibre.gui2.preferences.toolbar_ui import Ui_Form
from calibre.gui2 import gprefs, warning_dialog, error_dialog
from calibre.gui2.preferences import ConfigWidgetBase, test_widget, AbortCommit
from calibre.utils.icu import primary_sort_key


def sort_key_for_action(ac):
    q = getattr(ac, 'action_spec', None)
    try:
        q = ac.name if q is None else q[0]
        return primary_sort_key(force_unicode(q))
    except Exception:
        return primary_sort_key('')


class FakeAction:

    def __init__(self, name, gui_name, icon, tooltip=None,
            dont_add_to=frozenset(), dont_remove_from=frozenset()):
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
        if role == Qt.ItemDataRole.DisplayRole:
            text = action[0]
            text = text.replace('&', '')
            if text == _('%d books'):
                text = _('Choose library')
            return (text)
        if role == Qt.ItemDataRole.DecorationRole:
            if hasattr(self._data[row], 'qaction'):
                icon = self._data[row].qaction.icon()
                if not icon.isNull():
                    return (icon)
            ic = action[1]
            if ic is None:
                ic = 'blank.png'
            return (QIcon.ic(ic))
        if role == Qt.ItemDataRole.ToolTipRole and action[2] is not None:
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

        all.sort(key=sort_key_for_action)
        return all

    def add(self, names):
        actions = []
        for name in names:
            if name is None or name.startswith('---'):
                continue
            actions.append(self.name_to_action(name, self.gui))
        self.beginResetModel()
        self._data.extend(actions)
        self._data.sort(key=sort_key_for_action)
        self.endResetModel()

    def remove(self, indices, allowed):
        rows = [i.row() for i in indices]
        remove = set()
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
        nrow = (row + delta + len(self._data)) % len(self._data)
        if nrow < 0 or nrow >= len(self._data):
            return
        t = self._data[row]
        self._data[row] = self._data[nrow]
        self._data[nrow] = t
        ni = self.index(nrow)
        self.dataChanged.emit(idx, idx)
        self.dataChanged.emit(ni, ni)
        return ni

    def move_many(self, indices, delta):
        indices = sorted(indices, key=lambda i: i.row(), reverse=delta > 0)
        ans = {}
        for idx in indices:
            ni = self.move(idx, delta)
            ans[idx.row()] = ni
        return ans

    def add(self, names):
        actions = []
        reject = set()
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
        remove, rejected = set(), set()
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
            ('context-menu-split', _('The context menu for the split book list')),
            ('context-menu-device', _('The context menu for the books on '
                'the device')),
            ('context-menu-cover-browser', _('The context menu for the Cover '
                'browser')),
            ]

    def genesis(self, gui):
        self.all_actions.doubleClicked.connect(self.add_single_action)
        self.current_actions.doubleClicked.connect(self.remove_single_action)
        self.models = {}
        self.what.addItem(_('Click to choose toolbar or menu to customize'),
                'blank')
        for key, text in self.LOCATIONS:
            self.what.addItem(text, key)
            all_model = AllModel(key, gui)
            current_model = CurrentModel(key, gui)
            self.models[key] = (all_model, current_model)
        self.what.setCurrentIndex(0)
        self.what.currentIndexChanged.connect(self.what_changed)
        self.what_changed(0)

        self.add_action_button.clicked.connect(self.add_action)
        self.remove_action_button.clicked.connect(self.remove_action)
        connect_lambda(self.action_up_button.clicked, self, lambda self: self.move(-1))
        connect_lambda(self.action_down_button.clicked, self, lambda self: self.move(1))
        self.all_actions.setMouseTracking(True)
        self.current_actions.setMouseTracking(True)
        self.all_actions.entered.connect(self.all_entered)
        self.current_actions.entered.connect(self.current_entered)

    def all_entered(self, index):
        tt = self.all_actions.model().data(index, Qt.ItemDataRole.ToolTipRole) or ''
        self.help_text.setText(tt)

    def current_entered(self, index):
        tt = self.current_actions.model().data(index, Qt.ItemDataRole.ToolTipRole) or ''
        self.help_text.setText(tt)

    def what_changed(self, idx):
        key = str(self.what.itemData(idx) or '')
        if key == 'blank':
            self.actions_widget.setVisible(False)
            self.spacer_widget.setVisible(True)
        else:
            self.actions_widget.setVisible(True)
            self.spacer_widget.setVisible(False)
            self.all_actions.setModel(self.models[key][0])
            self.current_actions.setModel(self.models[key][1])

    def add_action(self, *args):
        self._add_action(self.all_actions.selectionModel().selectedIndexes())

    def add_single_action(self, index):
        self._add_action([index])

    def _add_action(self, indices):
        names = self.all_actions.model().names(indices)
        if names:
            not_added = self.current_actions.model().add(names)
            ns = {y.name for y in not_added}
            added = set(names) - ns
            self.all_actions.model().remove(indices, added)
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
        self._remove_action(self.current_actions.selectionModel().selectedIndexes())

    def remove_single_action(self, index):
        self._remove_action([index])

    def _remove_action(self, indices):
        names = self.current_actions.model().names(indices)
        if names:
            not_removed = self.current_actions.model().remove(indices)
            ns = {y.name for y in not_removed}
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
        sm = self.current_actions.selectionModel()
        x = sm.selectedIndexes()
        if x and len(x):
            i = sm.currentIndex().row()
            m = self.current_actions.model()
            idx_map = m.move_many(x, delta)
            newci = idx_map.get(i)
            if newci is not None:
                sm.setCurrentIndex(newci, QItemSelectionModel.SelectionFlag.ClearAndSelect)
            sm.clear()
            for idx in idx_map.values():
                sm.select(idx, QItemSelectionModel.SelectionFlag.Select)
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
