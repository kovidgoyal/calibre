#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from functools import partial

from qt.core import QIcon, QKeySequence, QListWidgetItem, Qt

from calibre.gui2 import gprefs
from calibre.gui2.custom_column_widgets import get_field_list as em_get_field_list
from calibre.gui2.preferences import ConfigWidgetBase, test_widget
from calibre.gui2.preferences.coloring import EditRules
from calibre.gui2.preferences.look_feel_tabs import (
    DisplayedFields,
    export_layout,
    import_layout,
    move_field_down,
    move_field_up,
    reset_layout,
    selected_rows_metadatas,
)
from calibre.gui2.preferences.look_feel_ui import Ui_Form
from calibre.gui2.widgets import BusyCursor


class EMDisplayedFields(DisplayedFields):  # {{{
    def __init__(self, db, parent=None):
        DisplayedFields.__init__(self, db, parent)

    def initialize(self, use_defaults=False, pref_data_override=None):
        self.beginResetModel()
        self.fields = [[x[0], x[1]] for x in
                em_get_field_list(self.db, use_defaults=use_defaults, pref_data_override=pref_data_override)]
        self.endResetModel()
        self.changed = True

    def commit(self):
        if self.changed:
            self.db.new_api.set_pref('edit_metadata_custom_columns_to_display', self.fields)
# }}}


class ConfigWidget(ConfigWidgetBase, Ui_Form):

    def genesis(self, gui):
        self.gui = gui

        db = gui.library_view.model().db

        r = self.register

        choices = [(_('Default'), 'default'), (_('Compact metadata'), 'alt1'),
                   (_('All on 1 tab'), 'alt2')]
        r('edit_metadata_single_layout', gprefs,
          choices=[(_('Default'), 'default'), (_('Compact metadata'), 'alt1'),
                   (_('All on 1 tab'), 'alt2')])
        r('edit_metadata_ignore_display_order', db.prefs)
        r('edit_metadata_elision_point', gprefs,
          choices=[(_('Left'), 'left'), (_('Middle'), 'middle'),
                   (_('Right'), 'right')])
        r('edit_metadata_elide_labels', gprefs)
        r('edit_metadata_single_use_2_cols_for_custom_fields', gprefs)
        r('edit_metadata_bulk_cc_label_length', gprefs)
        r('edit_metadata_single_cc_label_length', gprefs)
        r('edit_metadata_templates_only_F2_on_booklist', gprefs)

        self.em_display_model = EMDisplayedFields(self.gui.current_db, self.em_display_order)
        self.em_display_model.dataChanged.connect(self.changed_signal)
        self.em_display_order.setModel(self.em_display_model)
        mu = partial(move_field_up, self.em_display_order, self.em_display_model)
        md = partial(move_field_down, self.em_display_order, self.em_display_model)
        self.em_display_order.set_movement_functions(mu, md)
        self.em_up_button.clicked.connect(mu)
        self.em_down_button.clicked.connect(md)
        self.em_export_layout_button.clicked.connect(partial(export_layout, self, model=self.em_display_model))
        self.em_import_layout_button.clicked.connect(partial(import_layout, self, model=self.em_display_model))
        self.em_reset_layout_button.clicked.connect(partial(reset_layout, model=self.em_display_model))

        self.edit_rules = EditRules(self.tabWidget)
        self.edit_rules.changed.connect(self.changed_signal)
        self.tabWidget.addTab(self.edit_rules, QIcon.ic('format-fill-color.png'), _('Column &coloring'))

        self.icon_rules = EditRules(self.tabWidget)
        self.icon_rules.changed.connect(self.changed_signal)
        self.tabWidget.addTab(self.icon_rules, QIcon.ic('icon_choose.png'), _('Column &icons'))

        self.tabWidget.setCurrentIndex(0)
        self.tabWidget.tabBar().setVisible(False)
        keys = [QKeySequence('F11', QKeySequence.SequenceFormat.PortableText), QKeySequence(
            'Ctrl+Shift+F', QKeySequence.SequenceFormat.PortableText)]
        keys = [str(x.toString(QKeySequence.SequenceFormat.NativeText)) for x in keys]

        for i in range(self.tabWidget.count()):
            self.sections_view.addItem(QListWidgetItem(self.tabWidget.tabIcon(i), self.tabWidget.tabText(i).replace('&', '')))
        self.sections_view.setCurrentRow(self.tabWidget.currentIndex())
        self.sections_view.currentRowChanged.connect(self.tabWidget.setCurrentIndex)
        self.sections_view.setMaximumWidth(self.sections_view.sizeHintForColumn(0) + 16)
        self.sections_view.setSpacing(4)
        self.sections_view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tabWidget.currentWidget().setFocus(Qt.FocusReason.OtherFocusReason)

    def initial_tab_changed(self):
        self.sections_view.setCurrentRow(self.tabWidget.currentIndex())

    def initialize(self):
        ConfigWidgetBase.initialize(self)

        self.em_display_model.initialize()
        db = self.gui.current_db
        mi = selected_rows_metadatas()
        self.edit_rules.initialize(db.field_metadata, db.prefs, mi, 'column_color_rules')
        self.icon_rules.initialize(db.field_metadata, db.prefs, mi, 'column_icon_rules')

    def restore_defaults(self):
        ConfigWidgetBase.restore_defaults(self)
        self.em_display_model.restore_defaults()
        self.edit_rules.clear()
        self.icon_rules.clear()
        self.changed_signal.emit()

    def commit(self, *args):
        with BusyCursor():
            self.em_display_model.commit()
            self.edit_rules.commit(self.gui.current_db.prefs)
            self.icon_rules.commit(self.gui.current_db.prefs)

    def refresh_gui(self, gui):
        m = gui.library_view.model()
        m.update_db_prefs_cache()
        m.beginResetModel(), m.endResetModel()
        gui.tags_view.model().reset_tag_browser()


if __name__ == '__main__':
    from calibre.gui2 import Application
    app = Application([])
    test_widget('Interface', 'Look & Feel')
