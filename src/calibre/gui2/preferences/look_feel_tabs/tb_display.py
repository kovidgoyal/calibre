#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2025, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from calibre.db.categories import is_standard_category
from calibre.gui2 import config, gprefs
from calibre.gui2.preferences import ConfigWidgetBase, LazyConfigWidgetBase
from calibre.gui2.preferences.look_feel_tabs import (
     DisplayedFields,
     import_layout,
     export_layout,
     move_field_down,
     move_field_up,
     reset_layout
 )
from calibre.gui2.preferences.look_feel_tabs.tb_display_ui import Ui_Form

class TBDisplayedFields(DisplayedFields):  # {{{
    # The code in this class depends on the fact that the tag browser is
    # initialized before this class is instantiated.

    def __init__(self, db, parent=None, category_icons=None):
        DisplayedFields.__init__(self, db, parent, category_icons=category_icons)
        from calibre.gui2.ui import get_gui
        self.gui = get_gui()

    def initialize(self, use_defaults=False, pref_data_override=None):
        tv = self.gui.tags_view
        cat_ord = tv.model().get_ordered_categories(use_defaults=use_defaults,
                                                    pref_data_override=pref_data_override)
        if use_defaults:
            hc = []
            self.changed = True
        elif pref_data_override:
            hc = [k for k,v in pref_data_override if not v]
            self.changed = True
        else:
            hc = tv.hidden_categories

        self.beginResetModel()
        self.fields = [[x, x not in hc] for x in cat_ord]
        self.endResetModel()

    def commit(self):
        if self.changed:
            self.db.prefs.set('tag_browser_hidden_categories', [k for k,v in self.fields if not v])
            self.db.prefs.set('tag_browser_category_order', [k for k,v in self.fields])
# }}}


class TbDisplayTab(LazyConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        r = self.register
        r('tag_browser_old_look', gprefs)
        r('tag_browser_hide_empty_categories', gprefs)
        r('tag_browser_always_autocollapse', gprefs)
        r('tag_browser_restore_tree_expansion', gprefs)
        r('tag_browser_show_tooltips', gprefs)
        r('tag_browser_allow_keyboard_focus', gprefs)
        r('tag_browser_show_counts', gprefs)
        r('tag_browser_item_padding', gprefs)
        r('show_avg_rating', config)
        r('show_links_in_tag_browser', gprefs)
        r('show_notes_in_tag_browser', gprefs)
        r('icons_on_right_in_tag_browser', gprefs)

        self.tb_display_model = TBDisplayedFields(self.gui.current_db, self.tb_display_order,
                                  category_icons=self.gui.tags_view.model().category_custom_icons)
        self.tb_display_model.dataChanged.connect(self.changed_signal)
        self.tb_display_order.setModel(self.tb_display_model)
        self.tb_reset_layout_button.clicked.connect(partial(reset_layout, self, model=self.tb_display_model))
        self.tb_export_layout_button.clicked.connect(partial(export_layout, self, model=self.tb_display_model))
        self.tb_import_layout_button.clicked.connect(partial(import_layout, self, model=self.tb_display_model))
        self.tb_up_button.clicked.connect(self.tb_up_button_clicked)
        self.tb_down_button.clicked.connect(self.tb_down_button_clicked)
        self.tb_display_order.set_movement_functions(self.tb_up_button_clicked, self.tb_down_button_clicked)

    def lazy_initialize(self):
        self.tb_display_model.initialize()
        self.tb_focus_label.setVisible(self.opt_tag_browser_allow_keyboard_focus.isChecked())

    def tb_down_button_clicked(self):
        idx = self.tb_display_order.currentIndex()
        if idx.isValid():
            row = idx.row()
            model = self.tb_display_model
            fields = model.fields
            key = fields[row][0]
            if not is_standard_category(key):
                return
            if row < len(fields) and is_standard_category(fields[row+1][0]):
                move_field_down(self.tb_display_order, model)

    def tb_up_button_clicked(self):
        idx = self.tb_display_order.currentIndex()
        if idx.isValid():
            row = idx.row()
            model = self.tb_display_model
            fields = model.fields
            key = fields[row][0]
            if not is_standard_category(key):
                return
            move_field_up(self.tb_display_order, model)

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.display_model.restore_defaults()

    def commit(self):
        self.tb_display_model.commit()
        return ConfigWidgetBase.commit(self)
