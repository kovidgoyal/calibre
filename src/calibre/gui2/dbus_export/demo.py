#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt5.Qt import (
    QApplication, QMainWindow, QVBoxLayout, Qt, QKeySequence)

from calibre.gui2.dbus_export.utils import setup_for_cli_run
from calibre.gui2.dbus_export.widgets import factory

setup_for_cli_run()

class MainWindow(QMainWindow):

    def action_triggered(self, checked=False):
        self.statusBar().showMessage('Action triggered: %s' % self.sender().text())

app = QApplication([])
f = factory()
mw = MainWindow()
mw.setWindowTitle('Demo of DBUS menu exporter and systray integration')
mw.statusBar().showMessage(mw.windowTitle())
w = mw.centralWidget()
mw.l = l = QVBoxLayout(w)
mb = f.create_window_menubar(mw)
mw.setMenuBar(mb)
m = mb.addMenu('&One')
s = mw.style()
for i, icon in zip(xrange(3), map(s.standardIcon, (s.SP_DialogOkButton, s.SP_DialogCancelButton, s.SP_ArrowUp))):
    ac = m.addAction('One - &%d' % (i + 1))
    ac.triggered.connect(mw.action_triggered)
    k = getattr(Qt, 'Key_%d' % (i + 1))
    ac.setShortcut(QKeySequence(Qt.CTRL | (Qt.Key_1 + i), Qt.SHIFT | (Qt.Key_1 + i)))
    ac.setIcon(icon)
m.addSeparator()
m.addAction('&Disabled action').setEnabled(False)
mw.show()
print ('DBUS connection unique name:', f.bus.get_unique_name())
app.exec_()
