#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'


from PyQt5.Qt import QLineEdit

from calibre.gui2.dialogs.template_dialog import TemplateDialog


class TemplateLineEditor(QLineEdit):

    '''
    Extend the context menu of a QLineEdit to include more actions.
    '''

    def __init__(self, parent):
        QLineEdit.__init__(self, parent)
        self.mi   = None

    def set_mi(self, mi):
        self.mi = mi

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        menu.addSeparator()

        action_clear_field = menu.addAction(_('Remove any template from the box'))
        action_clear_field.triggered.connect(self.clear_field)
        action_open_editor = menu.addAction(_('Open template editor'))
        action_open_editor.triggered.connect(self.open_editor)
        menu.exec_(event.globalPos())

    def clear_field(self):
        self.setText('')

    def open_editor(self):
        t = TemplateDialog(self, self.text(), mi=self.mi)
        t.setWindowTitle(_('Edit template'))
        if t.exec_():
            self.setText(t.rule[1])
