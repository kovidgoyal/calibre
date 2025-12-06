#!/usr/bin/env python
# License: GPLv3 Copyright: 2025, Kovid Goyal <kovid at kovidgoyal.net>


from functools import partial

from calibre.gui2 import error_dialog
from calibre.gui2.actions import InterfaceAction


class LLMBookAction(InterfaceAction):

    name = 'Discuss book with AI'
    action_spec = (_('Discuss book with AI'), 'ai.png', _('Ask AI about books'), 'Ctrl+Alt+A')
    action_type = 'current'
    action_add_menu = True
    dont_add_to = frozenset(('context-menu-device', 'toolbar-device', 'menubar-device'))

    def genesis(self):
        self.qaction.triggered.connect(self.ask_ai)
        self.ask_action = self.menuless_qaction
        self.ask_menu = self.qaction.menu()
        self.ask_menu.aboutToShow.connect(self.about_to_show_menu)

    def initialization_complete(self):
        self.gui.iactions['View'].llm_action.setShortcut(self.menuless_qaction.shortcut())

    def about_to_show_menu(self):
        from calibre.utils.icu import primary_sort_key
        m = self.ask_menu
        m.clear()
        from calibre.gui2.dialogs.llm_book import current_actions
        for ac in sorted(current_actions(), key=lambda a: primary_sort_key(a.human_name)):
            a = m.addAction(ac.human_name)
            a.triggered.connect(partial(self.ask_ai_with_action, ac))

    def ask_ai_with_action(self, action=None):
        from calibre.gui2.dialogs.llm_book import LLMBookDialog
        rows = list(self.gui.library_view.selectionModel().selectedRows())
        if not rows or len(rows) == 0:
            d = error_dialog(self.gui, _('Cannot ask AI'), _('No book selected'))
            d.exec()
            return
        db = self.gui.library_view.model().db
        rows = [r.row() for r in rows]
        book_ids = [db.id(r) for r in rows]
        d = LLMBookDialog([db.new_api.get_metadata(bid) for bid in book_ids], parent=self.gui)
        if action is not None:
            d.llm.activate_action(action)
        d.exec()

    def ask_ai(self):
        self.ask_ai_with_action()
