#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


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

    def show_template_editor(self, *args):
        view = self.gui.current_view()
        if view is not self.gui.library_view:
            return error_dialog(self.gui, _('No template tester available'),
                _('Template tester is not available for books '
                  'on the device.')).exec_()

        rows = view.selectionModel().selectedRows()
        if not rows:
            return error_dialog(self.gui, _('No books selected'),
                    _('One book must be selected'), show=True)
        if len(rows) > 1:
            return error_dialog(self.gui, _('Selected multiple books'),
                    _('Only one book can be selected'), show=True)

        index = rows[0]
        if index.isValid():
            db = view.model().db
            t = TemplateDialog(self.gui, self.previous_text,
                   mi=db.get_metadata(index.row(), index_is_id=False, get_cover=False),
                   text_is_placeholder=self.first_time)
            t.setWindowTitle(_('Template tester'))
            if t.exec_() == t.Accepted:
                self.previous_text = t.rule[1]
                self.first_time = False
