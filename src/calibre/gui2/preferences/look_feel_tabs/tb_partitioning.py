#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2025, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from functools import partial

from calibre.gui2 import  gprefs
from calibre.gui2.preferences import ConfigWidgetBase, LazyConfigWidgetBase
from calibre.gui2.preferences.look_feel_tabs import DisplayedFields, export_layout, import_layout, reset_layout
from calibre.gui2.preferences.look_feel_tabs.tb_partitioning_ui import Ui_Form


class TBPartitionedFields(DisplayedFields):  # {{{
    # The code in this class depends on the fact that the tag browser is
    # initialized before this class is instantiated.

    def __init__(self, db, parent=None, category_icons=None):
        DisplayedFields.__init__(self, db, parent, category_icons=category_icons)
        from calibre.gui2.ui import get_gui
        self.gui = get_gui()

    def filter_user_categories(self, tv):
        cats = tv.model().categories
        answer = {}
        filtered = set()
        for key,name in cats.items():
            if key.startswith('@'):
                key = key.partition('.')[0]
                name = key[1:]
            if key not in filtered:
                answer[key] = name
                filtered.add(key)
        return answer

    def initialize(self, use_defaults=False, pref_data_override=None):
        tv = self.gui.tags_view
        cats = self.filter_user_categories(tv)
        ans = []
        if use_defaults:
            ans = [[k, True] for k in cats.keys()]
            self.changed = True
        elif pref_data_override:
            po = {k:v for k,v in pref_data_override}
            ans = [[k, po.get(k, True)] for k in cats.keys()]
            self.changed = True
        else:
            # Check if setting not migrated yet
            cats_to_partition = frozenset(self.db.prefs.get('tag_browser_dont_collapse', gprefs.get('tag_browser_dont_collapse')) or ())
            for key in cats:
                ans.append([key, key not in cats_to_partition])
        self.beginResetModel()
        self.fields = ans
        self.endResetModel()

    def commit(self):
        if self.changed:
            # Migrate to a per-library setting
            self.db.prefs.set('tag_browser_dont_collapse', [k for k,v in self.fields if not v])
# }}}


class TbPartitioningTab(LazyConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui
        r = self.register

        choices = [(_('Disabled'), 'disable'), (_('By first letter'), 'first letter'),
                   (_('Partitioned'), 'partition')]
        r('tags_browser_partition_method', gprefs, choices=choices)
        r('tags_browser_collapse_at', gprefs)
        r('tags_browser_collapse_fl_at', gprefs)

        self.tb_categories_to_part_model = TBPartitionedFields(self.gui.current_db,
                                   self.tb_cats_to_partition,
                                   category_icons=self.gui.tags_view.model().category_custom_icons)
        self.tb_categories_to_part_model.dataChanged.connect(self.changed_signal)
        self.tb_cats_to_partition.setModel(self.tb_categories_to_part_model)
        self.tb_partition_reset_button.clicked.connect(partial(reset_layout, self,
                                                               model=self.tb_categories_to_part_model))
        self.tb_partition_export_layout_button.clicked.connect(partial(export_layout, self,
                                                                       model=self.tb_categories_to_part_model))
        self.tb_partition_import_layout_button.clicked.connect(partial(import_layout, self,
                                                                       model=self.tb_categories_to_part_model))

    def lazy_initialize(self):
        self.tb_categories_to_part_model.initialize()

    def commit(self):
        self.tb_categories_to_part_model.commit()
        return ConfigWidgetBase.commit(self)



