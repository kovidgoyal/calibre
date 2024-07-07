#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from qt.core import QLineEdit

from calibre import prints
from calibre.gui2.dialogs.template_dialog import TemplateDialog


class TemplateLineEditor(QLineEdit):

    '''
    Extend the context menu of a QLineEdit to include more actions.
    '''

    def __init__(self, parent):
        QLineEdit.__init__(self, parent)
        try:
            from calibre.gui2.ui import get_gui
            gui = get_gui()
            view = gui.library_view
            db = gui.current_db
            mi = []
            for _id in view.get_selected_ids()[:5]:
                mi.append(db.new_api.get_metadata(_id))
            self.mi = mi
        except Exception as e:
            prints(f'TemplateLineEditor: exception fetching metadata: {str(e)}')
            self.mi = None
        self.setClearButtonEnabled(True)

    def set_mi(self, mi):
        self.mi = mi

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()

        action_clear_field = menu.addAction(_('Remove any template from the box'))
        action_clear_field.triggered.connect(self.clear_field)
        action_open_editor = menu.addAction(_('Open template editor'))
        action_open_editor.triggered.connect(self.open_editor)
        menu.exec(event.globalPos())

    def clear_field(self):
        self.setText('')

    def open_editor(self):
        t = TemplateDialog(self, self.text(), mi=self.mi)
        t.setWindowTitle(_('Edit template'))
        if t.exec():
            self.setText(t.rule[1])
