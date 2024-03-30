#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceAction
from calibre.gui2.dialogs.template_dialog import TemplateDialog


class ShowTemplateTesterAction(InterfaceAction):

    name = 'Template tester'
    action_spec = (_('Template tester'), 'debug.png', None, ())
    dont_add_to = frozenset(('context-menu-device',))
    action_type = 'current'

    def genesis(self):
        self.previous_text = _('Enter a template to test using data from the selected book')
        self.first_time = True
        self.qaction.triggered.connect(self.show_template_editor)
        self.window_title = self.action_spec[0]

        # self.hidden_menu = QMenu()
        # self.non_modal_window_title = _('Template tester -- separate dialog')
        # self.shortcut_action = self.create_menu_action(
        #                 menu=self.hidden_menu,
        #                 unique_name='Template tester',
        #                 text=self.non_modal_window_title,
        #                 icon='debug.png',
        #                 triggered=partial(self.show_template_editor, modal=False))
        self.non_modal_dialogs = list()

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
            for dn in range(-1, len(self.non_modal_dialogs)):
                if dn < 0:
                    continue
                if self.non_modal_dialogs[dn] is None:
                    break
            else:
                dn = len(self.non_modal_dialogs)
            if dn == len(self.non_modal_dialogs):
                self.non_modal_dialogs.append(True)
            else:
                self.non_modal_dialogs[dn] = True
            t = TemplateDialog(self.gui, self.previous_text,
                               mi, text_is_placeholder=self.first_time,
                               dialog_number=dn)
            self.non_modal_dialogs[dn] = t
            t.setWindowTitle(self.window_title, dialog_number=dn+1)
            t.tester_closed.connect(self.save_template_text)
            t.show()

    def save_template_text(self, txt, dialog_number):
        if txt is not None:
            self.previous_text = txt
            self.first_time = False
        self.non_modal_dialogs[dialog_number] = None
