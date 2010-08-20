#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from PyQt4.Qt import QWidget, QAbstractListModel, Qt, QIcon, \
        QVariant, QItemSelectionModel

from calibre.gui2.dialogs.config.toolbar_ui import Ui_Form
from calibre.gui2.layout import TOOLBAR_NO_DEVICE, TOOLBAR_DEVICE
from calibre.gui2.init import LIBRARY_CONTEXT_MENU, DEVICE_CONTEXT_MENU
from calibre.gui2 import gprefs, NONE

DEFAULTS = {
        'toolbar': TOOLBAR_NO_DEVICE,
        'toolbar-device': TOOLBAR_DEVICE,
        'context-menu': LIBRARY_CONTEXT_MENU,
        'context-menu-device': DEVICE_CONTEXT_MENU,
}

UNREMOVABLE = {
        'toolbar': ['Preferences'],
        'toolbar-device': ['Send To Device', 'Location Manager'],
}

UNADDABLE = {
        'toolbar': ['Location Manager'],
        'context-menu': ['Location Manager'],
        'context-menu-device': ['Location Manager'],
}

class FakeAction(object):

    def __init__(self, name, icon, tooltip=None):
        self.name = name
        self.action_spec = (name, icon, tooltip, None)

class BaseModel(QAbstractListModel):

    def name_to_action(self, name, gui):
        if name == 'Donate':
            return FakeAction(name, 'donate.svg')
        if name == 'Location Manager':
            return FakeAction(name, None)
        if name is None:
            return FakeAction('--- '+_('Separator')+' ---', None)
        return gui.iactions[name]

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
            return QVariant(text)
        if role == Qt.DecorationRole:
            ic = action[1]
            if ic is None:
                ic = 'blank.svg'
            return QVariant(QIcon(I(ic)))
        if role == Qt.ToolTipRole and action[2] is not None:
            return QVariant(action[2])
        return NONE


class AllModel(BaseModel):

    def __init__(self, key, gui):
        BaseModel.__init__(self)
        current = gprefs.get('action-layout-'+key, DEFAULTS[key])
        all = list(gui.iactions.keys()) + ['Donate']
        all = [x for x in all if x not in current] + [None]
        all = [self.name_to_action(x, gui) for x in all]
        all.sort()

        self._data = all

class CurrentModel(BaseModel):

    def __init__(self, key, gui):
        BaseModel.__init__(self)
        current = gprefs.get('action-layout-'+key, DEFAULTS[key])
        self._data =  [self.name_to_action(x, gui) for x in current]

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


class ToolbarLayout(QWidget, Ui_Form):

    LOCATIONS = [
            ('toolbar', _('The main toolbar')),
            ('toolbar-device', _('The main toolbar when a device is connected')),
            ('context-menu', _('The context menu for the books in the '
                'calibre library')),
            ('context-menu-device', _('The context menu for the books on '
                'the device'))
            ]

    def __init__(self, gui, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)

        self.models = {}
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
        self.action_up_button.clicked.connect(self.action_up)
        self.action_down_button.clicked.connect(self.action_down)

    def what_changed(self, idx):
        key = unicode(self.what.itemData(idx).toString())
        self.all_actions.setModel(self.models[key][0])
        self.current_actions.setModel(self.models[key][1])

    def add_action(self, *args):
        pass

    def remove_action(self, *args):
        pass

    def action_up(self, *args):
        ci = self.current_actions.currentIndex()
        m = self.current_actions.model()
        if ci.isValid():
            ni = m.move(ci, -1)
            if ni is not None:
                self.current_actions.setCurrentIndex(ni)
                self.current_actions.selectionModel().select(ni,
                        QItemSelectionModel.ClearAndSelect)

    def action_down(self, *args):
        ci = self.current_actions.currentIndex()
        m = self.current_actions.model()
        if ci.isValid():
            ni = m.move(ci, 1)
            if ni is not None:
                self.current_actions.setCurrentIndex(ni)
                self.current_actions.selectionModel().select(ni,
                        QItemSelectionModel.ClearAndSelect)

if __name__ == '__main__':
    from PyQt4.Qt import QApplication
    from calibre.gui2.ui import Main
    app=QApplication([])
    m = Main(None)
    a = ToolbarLayout(m)
    a.show()
    app.exec_()

