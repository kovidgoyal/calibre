#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from qt.core import QDialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.gui2 import error_dialog


class ShowTemplateTesterAction(InterfaceAction):

    name = 'Template tester'
    action_spec = (_('Template tester'), 'debug.png', None, ())
    dont_add_to = frozenset(('context-menu-device',))
    action_type = 'current'

    def genesis(self):
        self.previous_text = _('Enter a template to test using data from the selected book')
        self.first_time = True
        self.qaction.triggered.connect(self.show_template_editor)

    def last_template_text(self):
        return self.previous_text

    def show_template_editor(self, *args):
        view = self.gui.current_view()
        if view is not self.gui.library_view:
            return error_dialog(self.gui, _('No template tester available'),
                _('Template tester is not available for books '
                  'on the device.')).exec()

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
            t = TemplateDialog(self.gui, self.previous_text,
                   mi, text_is_placeholder=self.first_time)
            t.setWindowTitle(_('Template tester'))
            if t.exec() == QDialog.DialogCode.Accepted:
                self.previous_text = t.rule[1]
                self.first_time = False
