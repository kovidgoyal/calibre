#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt4.Qt import (
    QDialog, QGridLayout, QStackedWidget, QDialogButtonBox, QListWidget,
    QListWidgetItem, QIcon)

from calibre.gui2.keyboard import ShortcutConfig
from calibre.gui2.tweak_book import tprefs

class Preferences(QDialog):

    def __init__(self, gui, initial_panel=None):
        QDialog.__init__(self, gui)
        self.l = l = QGridLayout(self)
        self.setLayout(l)
        self.setWindowTitle(_('Preferences for Tweak Book'))
        self.setWindowIcon(QIcon(I('config.png')))

        self.stacks = QStackedWidget(self)
        l.addWidget(self.stacks, 0, 1, 1, 1)

        self.categories_list = cl = QListWidget(self)
        cl.currentRowChanged.connect(self.stacks.setCurrentIndex)
        cl.clearPropertyFlags()
        cl.setViewMode(cl.IconMode)
        cl.setFlow(cl.TopToBottom)
        cl.setMovement(cl.Static)
        cl.setWrapping(False)
        cl.setSpacing(10)
        cl.setWordWrap(True)
        l.addWidget(cl, 0, 0, 1, 1)

        self.bb = bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        self.rdb = b = bb.addButton(_('Restore all defaults'), bb.ResetRole)
        b.clicked.connect(self.restore_all_defaults)
        l.addWidget(bb, 1, 0, 1, 2)

        self.resize(800, 600)
        geom = tprefs.get('preferences_geom', None)
        if geom is not None:
            self.restoreGeometry(geom)

        self.keyboard_panel = ShortcutConfig(self)
        self.keyboard_panel.initialize(gui.keyboard)

        for name, icon, panel in [(_('Keyboard Shortcuts'), 'keyboard-prefs.png', 'keyboard')]:
            i = QListWidgetItem(QIcon(I(icon)), name, cl)
            cl.addItem(i)
            self.stacks.addWidget(getattr(self, panel + '_panel'))

        cl.setCurrentRow(0)
        cl.item(0).setSelected(True)
        cl.setMaximumWidth(cl.sizeHintForColumn(0) + 30)
        l.setColumnStretch(1, 10)

    def restore_all_defaults(self):
        for i in xrange(self.stacks.count()):
            w = self.stacks.widget(i)
            w.restore_defaults()

    def accept(self):
        tprefs.set('preferences_geom', bytearray(self.saveGeometry()))
        for i in xrange(self.stacks.count()):
            w = self.stacks.widget(i)
            w.commit()
        QDialog.accept(self)

    def reject(self):
        tprefs.set('preferences_geom', bytearray(self.saveGeometry()))
        QDialog.reject(self)

if __name__ == '__main__':
    from calibre.gui2 import Application
    from calibre.gui2.tweak_book.main import option_parser
    from calibre.gui2.tweak_book.ui import Main
    app = Application([])
    opts = option_parser().parse_args(['dev'])
    main = Main(opts)
    d = Preferences(main)
    d.exec_()

