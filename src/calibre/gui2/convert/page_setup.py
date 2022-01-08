#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from qt.core import Qt, QAbstractListModel, QModelIndex, QItemSelectionModel

from calibre.gui2.convert.page_setup_ui import Ui_Form
from calibre.gui2.convert import Widget
from calibre.customize.ui import input_profiles, output_profiles
from calibre.ebooks.conversion.config import OPTIONS


class ProfileModel(QAbstractListModel):

    def __init__(self, profiles):
        QAbstractListModel.__init__(self)
        self.profiles = list(profiles)

    def rowCount(self, *args):
        return len(self.profiles)

    def data(self, index, role):
        profile = self.profiles[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            if profile.name.startswith('Default '):
                return _('Default profile')
            return __builtins__['_'](profile.name)
        if role in (Qt.ItemDataRole.StatusTipRole, Qt.ItemDataRole.WhatsThisRole):
            w, h = profile.screen_size
            if w >= 10000:
                ss = _('unlimited')
            else:
                ss = _('%(width)d x %(height)d pixels') % dict(width=w, height=h)
            ss = _('Screen size: %s') % ss
            return (f'{profile.description} [{ss}]')
        return None


class PageSetupWidget(Widget, Ui_Form):

    TITLE = _('Page setup')
    COMMIT_NAME = 'page_setup'

    def __init__(self, parent, get_option, get_help, db=None, book_id=None):
        self.__connections = []
        Widget.__init__(self, parent, OPTIONS['pipe']['page_setup'])

        self.db, self.book_id = db, book_id
        self.input_model = ProfileModel(input_profiles())
        self.output_model = ProfileModel(output_profiles())
        self.opt_input_profile.setModel(self.input_model)
        self.opt_output_profile.setModel(self.output_model)
        for g, slot in self.__connections:
            g.selectionModel().currentChanged.connect(slot)
        del self.__connections

        for x in (self.opt_input_profile, self.opt_output_profile):
            x.setMouseTracking(True)
            x.entered[(QModelIndex)].connect(self.show_desc)
        self.initialize_options(get_option, get_help, db, book_id)
        self.opt_input_profile.setToolTip('')
        self.opt_output_profile.setToolTip('')

    def show_desc(self, index):
        desc = str(index.model().data(index, Qt.ItemDataRole.StatusTipRole) or '')
        self.profile_description.setText(desc)

    def connect_gui_obj_handler(self, g, slot):
        if g not in (self.opt_input_profile, self.opt_output_profile):
            raise NotImplementedError()
        self.__connections.append((g, slot))

    def set_value_handler(self, g, val):
        if g in (self.opt_input_profile, self.opt_output_profile):
            g.clearSelection()
            for idx, p in enumerate(g.model().profiles):
                if p.short_name == val:
                    break
            idx = g.model().index(idx)
            sm = g.selectionModel()
            g.setCurrentIndex(idx)
            sm.select(idx, QItemSelectionModel.SelectionFlag.SelectCurrent)
            return True
        return False

    def get_value_handler(self, g):
        if g in (self.opt_input_profile, self.opt_output_profile):
            idx = g.currentIndex().row()
            return g.model().profiles[idx].short_name
        return Widget.get_value_handler(self, g)
