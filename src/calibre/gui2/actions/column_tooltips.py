#!/usr/bin/env python
# License: GPLv3 Copyright: 2022, Charles Haley
#

from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.template_dialog import TemplateDialog


def column_template_placeholder_text():
    return _(
            'Notes:\n'
            '• The template global variable "{0}" contains the column lookup name.\n'
            '• The global variable "{1}" contains the original tooltip text').format('column_lookup_name',

                                                                                     'original_text')
class ColumnTooltipsAction(InterfaceAction):

    name = 'Column tooltips'
    action_spec = (_('Column tooltips'), 'edit_input.png',
                   _('Define a custom tooltip for values in a column'), ())
    action_type = 'current'
    dont_add_to = frozenset(('context-menu-device', 'menubar-device'))

    def genesis(self):
        self.qaction.triggered.connect(self.show_template_editor)

    def show_template_editor(self):
        view = self.gui.current_view()
        if view is not self.gui.library_view:
            return error_dialog(self.gui, _('No template tester available'),
                _('Template tester is not available for books '
                  'on the device.')).exec()

        idx = view.currentIndex()
        if not idx.isValid():
            return error_dialog(self.gui, _('No column selected'),
                    _('A column (cell) must be selected'), show=True)
        column = view.model().column_map[idx.column()]
        rows = view.selectionModel().selectedRows()
        if not rows:
            return error_dialog(self.gui, _('No books selected'),
                    _('At least one book must be selected'), show=True)
        mi = []
        db = view.model().db
        for row in rows:
            if row.isValid():
                mi.append(db.new_api.get_proxy_metadata(db.data.index_to_id(row.row())))
        if mi:
            tt_dict = db.new_api.pref('column_tooltip_templates', {})
            for i in range(min(len(rows), 10)):
                mi.append(db.new_api.get_proxy_metadata(db.data.index_to_id(i)))
            template = tt_dict.get(column, '')
            text_is_placeholder = False
            if not template:
                text_is_placeholder = True
                template = column_template_placeholder_text()
            d = TemplateDialog(self.gui, template, mi=mi, text_is_placeholder=text_is_placeholder)
            if d.exec():
                tt_dict[column] = d.rule[1]
                db.new_api.set_pref('column_tooltip_templates', tt_dict)

    def location_selected(self, loc):
        enabled = loc == 'library'
        self.qaction.setEnabled(enabled)