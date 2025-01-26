#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2025, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from calibre.gui2 import gprefs
from calibre.gui2.actions.show_quickview import get_quickview_action_plugin
from calibre.gui2.dialogs.quickview import get_qv_field_list
from calibre.gui2.preferences import LazyConfigWidgetBase, ConfigWidgetBase
from calibre.gui2.preferences.look_feel_tabs import DisplayedFields, move_field_down, move_field_up
from calibre.gui2.preferences.look_feel_tabs.tb_quickview_ui import Ui_Form

class QVDisplayedFields(DisplayedFields):  # {{{

    def __init__(self, db, parent=None):
        DisplayedFields.__init__(self, db, parent)

    def initialize(self, use_defaults=False):
        self.beginResetModel()
        self.fields = [[x[0], x[1]] for x in
                get_qv_field_list(self.db.field_metadata, use_defaults=use_defaults)]
        self.endResetModel()
        self.changed = True

    def commit(self):
        if self.changed:
            self.db.new_api.set_pref('qv_display_fields', self.fields)

# }}}


class QuickviewTab(LazyConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        r = self.register

        r('qv_respects_vls', gprefs)
        r('qv_dclick_changes_column', gprefs)
        r('qv_retkey_changes_column', gprefs)
        r('qv_follows_column', gprefs)

        self.qv_display_model = QVDisplayedFields(self.gui.current_db, self.qv_display_order)
        self.qv_display_model.dataChanged.connect(self.changed_signal)
        self.qv_display_order.setModel(self.qv_display_model)

        mu = partial(move_field_up, self.qv_display_order, self.qv_display_model)
        md = partial(move_field_down, self.qv_display_order, self.qv_display_model)
        self.qv_display_order.set_movement_functions(mu, md)
        self.qv_up_button.clicked.connect(mu)
        self.qv_down_button.clicked.connect(md)

    def lazy_initialize(self):
        self.qv_display_model.initialize()

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.qv_display_model.restore_defaults()

    def refresh_gui(self, gui):
        qv = get_quickview_action_plugin()
        if qv:
            qv.refill_quickview()

    def commit(self, *args):
        rr = ConfigWidgetBase.commit(self, *args)
        self.qv_display_model.commit()
        return rr


