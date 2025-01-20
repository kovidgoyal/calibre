#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial
import json

from qt.core import QListWidgetItem, Qt

from calibre.gui2 import choose_files, choose_save_file, error_dialog, gprefs
from calibre.gui2.preferences import ConfigTabWidget
from calibre.gui2.preferences.look_feel_tabs import DisplayedFields
from calibre.gui2.preferences.look_feel_tabs.tb_hierarchy_ui import Ui_Form

class TBHierarchicalFields(DisplayedFields):  # {{{
    # The code in this class depends on the fact that the tag browser is
    # initialized before this class is instantiated.

    cant_make_hierarical = {'authors', 'publisher', 'formats', 'news',
                            'identifiers', 'languages', 'rating'}

    def __init__(self, db, parent=None, category_icons=None):
        DisplayedFields.__init__(self, db, parent, category_icons=category_icons)
        from calibre.gui2.ui import get_gui
        self.gui = get_gui()

    def initialize(self, use_defaults=False, pref_data_override=None):
        tv = self.gui.tags_view
        cats = [k for k in tv.model().categories.keys() if (not k.startswith('@') and
                                                            k not in self.cant_make_hierarical)]
        ans = []
        if use_defaults:
            ans = [[k, False] for k in cats]
            self.changed = True
        elif pref_data_override:
            ph = {k:v for k,v in pref_data_override}
            ans = [[k, ph.get(k, False)] for k in cats]
            self.changed = True
        else:
            hier_cats =  self.db.prefs.get('categories_using_hierarchy') or ()
            for key in cats:
                ans.append([key, key in hier_cats])
        self.beginResetModel()
        self.fields = ans
        self.endResetModel()

    def commit(self):
        if self.changed:
            self.db.prefs.set('categories_using_hierarchy', [k for k,v in self.fields if v])
# }}}



class TbHierarchyTab(ConfigTabWidget, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        self.tb_hierarchical_cats_model = TBHierarchicalFields(gui.current_db, self.tb_hierarchical_cats,
                                              category_icons=gui.tags_view.model().category_custom_icons)
        self.tb_hierarchical_cats_model.dataChanged.connect(self.changed_signal)
        self.tb_hierarchical_cats.setModel(self.tb_hierarchical_cats_model)
        self.tb_hierarchy_reset_layout_button.clicked.connect(partial(self.reset_layout,
                                                           model=self.tb_hierarchical_cats_model))
        self.tb_hierarchy_export_layout_button.clicked.connect(partial(self.export_layout,
                                                           model=self.tb_hierarchical_cats_model))
        self.tb_hierarchy_import_layout_button.clicked.connect(partial(self.import_layout,
                                                           model=self.tb_hierarchical_cats_model))

        self.fill_tb_search_order_box()
        self.tb_search_order_up_button.clicked.connect(self.move_tb_search_up)
        self.tb_search_order_down_button.clicked.connect(self.move_tb_search_down)
        self.tb_search_order.set_movement_functions(self.move_tb_search_up, self.move_tb_search_down)
        self.tb_search_order_reset_button.clicked.connect(self.reset_tb_search_order)

    def initialize(self):
        self.tb_hierarchical_cats_model.initialize()

    def fill_tb_search_order_box(self):
        # The tb_search_order is a directed graph of nodes with an arc to the next
        # node in the sequence. Node 0 (zero) is the start node with the last node
        # arcing back to node 0. This code linearizes the graph

        choices = [(1, _('Search for books containing the current item')),
                   (2, _('Search for books containing the current item or its children')),
                   (3, _('Search for books not containing the current item')),
                   (4, _('Search for books not containing the current item or its children'))]
        icon_map = self.gui.tags_view.model().icon_state_map

        order = gprefs.get('tb_search_order')
        self.tb_search_order.clear()
        node = 0
        while True:
            v = order[str(node)]
            if v == 0:
                break
            item = QListWidgetItem(icon_map[v], choices[v-1][1])
            item.setData(Qt.ItemDataRole.UserRole, choices[v-1][0])
            self.tb_search_order.addItem(item)
            node = v

    def move_tb_search_up(self):
        idx = self.tb_search_order.currentRow()
        if idx <= 0:
            return
        item = self.tb_search_order.takeItem(idx)
        self.tb_search_order.insertItem(idx-1, item)
        self.tb_search_order.setCurrentRow(idx-1)
        self.changed_signal.emit()

    def move_tb_search_down(self):
        idx = self.tb_search_order.currentRow()
        if idx < 0 or idx == 3:
            return
        item = self.tb_search_order.takeItem(idx)
        self.tb_search_order.insertItem(idx+1, item)
        self.tb_search_order.setCurrentRow(idx+1)
        self.changed_signal.emit()

    def tb_search_order_commit(self):
        t = {}
        # Walk the items in the list box building the (node -> node) graph of
        # the option order
        node = 0
        for i in range(0, 4):
            v = self.tb_search_order.item(i).data(Qt.ItemDataRole.UserRole)
            # JSON dumps converts integer keys to strings, so do it explicitly
            t[str(node)] = v
            node = v
        # Add the arc from the last node back to node 0
        t[str(node)] = 0
        gprefs.set('tb_search_order', t)

    def reset_tb_search_order(self):
        gprefs.set('tb_search_order', gprefs.defaults['tb_search_order'])
        self.fill_tb_search_order_box()
        self.changed_signal.emit()

    def reset_layout(self, model=None):
        model.initialize(use_defaults=True)
        self.changed_signal.emit()

    def export_layout(self, model=None):
        filename = choose_save_file(self, 'em_import_export_field_list',
                _('Save column list to file'),
                filters=[(_('Column list'), ['json'])])
        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(model.fields, f, indent=1)
            except Exception as err:
                error_dialog(self, _('Export field layout'),
                             _('<p>Could not write field list. Error:<br>%s')%err, show=True)

    def import_layout(self, model=None):
        filename = choose_files(self, 'em_import_export_field_list',
                _('Load column list from file'),
                filters=[(_('Column list'), ['json'])])
        if filename:
            try:
                with open(filename[0]) as f:
                    fields = json.load(f)
                model.initialize(pref_data_override=fields)
                self.changed_signal.emit()
            except Exception as err:
                error_dialog(self, _('Import layout'),
                             _('<p>Could not read field list. Error:<br>%s')%err, show=True)

    def commit(self):
        self.tb_search_order_commit()
        self.tb_hierarchical_cats_model.commit()