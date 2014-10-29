#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt5.Qt import (
    QApplication, QMainWindow, QVBoxLayout, Qt, QKeySequence, QAction, QActionGroup)

from calibre.gui2.dbus_export.utils import setup_for_cli_run
from calibre.gui2.dbus_export.widgets import factory

setup_for_cli_run()

def make_checkable(ac, checked=True):
    ac.setCheckable(True), ac.setChecked(checked)

class MainWindow(QMainWindow):

    def __init__(self):
        QMainWindow.__init__(self)
        self.setMinimumWidth(400)
        self.setWindowTitle('Demo of DBUS menu exporter and systray integration')
        self.statusBar().showMessage(self.windowTitle())
        w = self.centralWidget()
        self.l = QVBoxLayout(w)
        mb = f.create_window_menubar(self)
        self.setMenuBar(mb)
        m = mb.addMenu('&One')
        s = self.style()
        for i, icon in zip(xrange(3), map(s.standardIcon, (s.SP_DialogOkButton, s.SP_DialogCancelButton, s.SP_ArrowUp))):
            ac = m.addAction('One - &%d' % (i + 1))
            ac.setShortcut(QKeySequence(Qt.CTRL | (Qt.Key_1 + i), Qt.SHIFT | (Qt.Key_1 + i)))
            ac.setIcon(icon)
        m.addSeparator()
        m.addAction('&Disabled action').setEnabled(False)
        ac = m.addAction('A checkable action')
        make_checkable(ac)
        g = QActionGroup(self)
        make_checkable(g.addAction(m.addAction('Exclusive 1')))
        make_checkable(g.addAction(m.addAction('Exclusive 2')), False)
        for ac in mb.findChildren(QAction):
            ac.triggered.connect(self.action_triggered)

    def action_triggered(self, checked=False):
        ac = self.sender()
        text = 'Action triggered: %s' % ac.text()
        self.statusBar().showMessage(text)

app = QApplication([])
f = factory()
mw = MainWindow()
mw.show()
print ('DBUS connection unique name:', f.bus.get_unique_name())
app.exec_()
