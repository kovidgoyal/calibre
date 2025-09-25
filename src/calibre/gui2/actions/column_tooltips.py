#!/usr/bin/env python
# License: GPLv3 Copyright: 2022, Charles Haley
#

from qt.core import QDialogButtonBox, Qt, QVBoxLayout

from calibre.gui2 import error_dialog, safe_open_url
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2.widgets2 import Dialog, HTMLDisplay


def column_template_placeholder_text():
    return _(
            'Notes:\n'
            '• The template global variable "{0}" contains the column lookup name.\n'
            '• The global variable "{1}" contains the original tooltip text').format('column_lookup_name',
                                                                                     'original_text')


class ToolTipDialog(Dialog):

    def __init__(self, title, prefs):
        super().__init__(title, 'show_tooltip_dialog',
                         prefs=prefs,
                         default_buttons=QDialogButtonBox.StandardButton.Ok)

    def setup_ui(self):
        l = QVBoxLayout(self)
        d = self.display = HTMLDisplay()
        l.addWidget(d)
        l.addWidget(self.bb)
        d.anchor_clicked.connect(safe_open_url)

    def set_html(self, tt_text):
        self.display.setHtml(tt_text)


class ColumnTooltipsAction(InterfaceAction):

    name = 'Column tooltips'
    action_spec = (_('Column tooltips'), 'edit_input.png',
                   _('Define a custom tooltip for values in a column'), ())
    action_type = 'current'
    action_add_menu = True
    action_menu_clone_qaction = _('Edit/define column tooltip')
    dont_add_to = frozenset(('context-menu-device', 'menubar-device'))

    def genesis(self):
        self.qaction.triggered.connect(self.show_template_editor)
        m = self.qaction.menu()
        ac = self.create_menu_action(m, 'tooltip_in_dialog_box', _('Show item tooltip in a dialog'),
            icon='dialog_information.png', triggered=self.show_tooltip_in_dialog, shortcut=None)
        m.addAction(ac)

    def check_errors(self, only_one_row=False):
        view = self.gui.current_view()
        if view is not self.gui.library_view:
            error_dialog(self.gui, _('No library view available'),
                _("You can't set custom tooltips for books on the device.")).exec()
            return (None, None, None, None)
        idx = view.currentIndex()
        if not idx.isValid():
            error_dialog(self.gui, _('No column selected'),
                    _('A column (cell) must be selected'), show=True)
            return (None, None, None, None)
        column = view.model().column_map[idx.column()]
        rows = view.selectionModel().selectedRows()
        if not rows:
            error_dialog(self.gui, _('No books selected'),
                    _('At least one book must be selected'), show=True)
            return (None, None, None, None)
        if only_one_row and len(rows) != 1:
            error_dialog(self.gui, _('Only one book'),
                    _('Only one book can be selected'), show=True)
            return (None, None, None, None)
        return view, idx, column, rows

    def show_tooltip_in_dialog(self):
        view, idx, column, rows = self.check_errors(only_one_row=True)
        if view is None:
            return
        from calibre.gui2.ui import get_gui
        db = get_gui().current_db.new_api
        fm = db.field_metadata.get(column)
        col_name = fm['name']
        d = ToolTipDialog(
            _('Tooltip for column {name}, row {row_num}').format(name=col_name, row_num=rows[0].row()+1),
            prefs=db.backend.prefs)
        d.set_html(idx.data(Qt.ItemDataRole.ToolTipRole))
        d.exec()

    def show_template_editor(self):
        view, _, column, rows = self.check_errors()
        if view is None:
            return
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
