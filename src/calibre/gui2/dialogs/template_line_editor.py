#!/usr/bin/env python
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid@kovidgoyal.net>

from qt.core import QLineEdit

from calibre import prints
from calibre.gui2.dialogs.template_dialog import TemplateDialog
from calibre.utils.localization import _


class TemplateLineEditor(QLineEdit):
    """
    Extend the context menu of a QLineEdit to include more actions.
    """

    def __init__(self, parent):
        QLineEdit.__init__(self, parent)
        try:
            from calibre.gui2.ui import get_gui

            gui = get_gui(fail_if_absent=True)
            view = gui.library_view
            db = gui.current_db
            mi = []
            for _id in view.get_selected_ids()[:5]:
                mi.append(db.new_api.get_proxy_metadata(_id))
            self.mi = mi
        except Exception as e:
            prints(f'TemplateLineEditor: exception fetching metadata: {e}')
            self.mi = None
        self.setClearButtonEnabled(True)

    def set_mi(self, mi):
        self.mi = mi

    def contextMenuEvent(self, a0):
        menu = self.createStandardContextMenu()
        assert menu is not None
        menu.addSeparator()

        action_clear_field = menu.addAction(_('Remove any template from the box'))
        assert action_clear_field is not None
        action_clear_field.triggered.connect(self.clear_field)
        action_open_editor = menu.addAction(_('Open template editor'))
        assert action_open_editor is not None
        action_open_editor.triggered.connect(self.open_editor)
        menu.exec(a0.globalPos())

    def clear_field(self):
        self.setText('')

    def open_editor(self):
        t = TemplateDialog(self, self.text(), mi=self.mi)
        t.setWindowTitle(_('Edit template'))
        if t.exec():
            self.setText(t.rule[1])
