#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid@kovidgoyal.net>

from functools import partial
from typing import TYPE_CHECKING

from calibre.gui2 import gprefs
from calibre.gui2.custom_column_widgets import get_field_list as em_get_field_list
from calibre.gui2.preferences import LazyConfigWidgetBase
from calibre.gui2.preferences.look_feel_tabs import DisplayedFields, export_layout, import_layout, move_field_down, move_field_up, reset_layout
from calibre.gui2.preferences.look_feel_tabs.edit_metadata_ui import Ui_Form
from calibre.gui2.widgets import BusyCursor
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Iterable

    from qt.core import QObject

    from calibre.db.legacy import LibraryDatabase
    from calibre.gui2.ui import Main


class EMDisplayedFields(DisplayedFields):
    def __init__(self, db: LibraryDatabase, parent: QObject | None = None) -> None:
        DisplayedFields.__init__(self, db, parent)

    def initialize(self, use_defaults: bool = False, pref_data_override: Iterable[tuple[str, bool]] | None = None) -> None:
        self.beginResetModel()
        self.fields = [[x[0], x[1]] for x in em_get_field_list(self.db, use_defaults=use_defaults, pref_data_override=pref_data_override)]
        self.endResetModel()
        self.changed = True

    def commit(self) -> None:
        if self.changed:
            self.db.new_api.set_pref('edit_metadata_custom_columns_to_display', self.fields)


class EditMetadataTab(LazyConfigWidgetBase, Ui_Form):
    def genesis(self, gui: Main) -> None:
        self.gui = gui
        db = self.gui.library_view.model().db
        assert db is not None
        r = self.register

        r(
            'edit_metadata_single_layout',
            gprefs,
            choices=[(_('Default'), 'default'), (_('Compact metadata'), 'alt1'), (_('All on 1 tab'), 'alt2')],
        )
        r('edit_metadata_ignore_display_order', db.prefs)
        r(
            'edit_metadata_elision_point',
            gprefs,
            choices=[(_('Left'), 'left'), (_('Middle'), 'middle'), (_('Right'), 'right')],
        )
        r('edit_metadata_elide_labels', gprefs)
        r('edit_metadata_single_use_2_cols_for_custom_fields', gprefs)
        r('edit_metadata_bulk_cc_label_length', gprefs)
        r('edit_metadata_single_cc_label_length', gprefs)
        r('edit_metadata_templates_only_F2_on_booklist', gprefs, restart_required=True)

        self.em_display_model = EMDisplayedFields(self.gui.current_db, self.em_display_order)
        self.em_display_model.dataChanged.connect(self.changed_signal)
        self.em_display_order.setModel(self.em_display_model)
        mu = partial(move_field_up, self.em_display_order, self.em_display_model)
        md = partial(move_field_down, self.em_display_order, self.em_display_model)
        self.em_display_order.set_movement_functions(mu, md)
        self.em_up_button.clicked.connect(partial(mu, use_kbd_modifiers=True))
        self.em_down_button.clicked.connect(partial(md, use_kbd_modifiers=True))
        self.em_export_layout_button.clicked.connect(partial(export_layout, self, model=self.em_display_model))
        self.em_import_layout_button.clicked.connect(partial(import_layout, self, model=self.em_display_model))
        self.em_reset_layout_button.clicked.connect(partial(reset_layout, model=self.em_display_model))

    def lazy_initialize(self) -> None:
        self.em_display_model.initialize()

    def commit(self, *args: object) -> bool:
        with BusyCursor():
            self.em_display_model.commit()
        return LazyConfigWidgetBase.commit(self)

    def restore_defaults(self, *args: object) -> None:
        LazyConfigWidgetBase.restore_defaults(self)
        self.em_display_model.restore_defaults()
        self.changed_signal.emit()
