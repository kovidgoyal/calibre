#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from PyQt5.Qt import (
    QApplication, QMainWindow, QVBoxLayout, Qt, QKeySequence, QAction,
    QActionGroup, QMenu, QIcon)

from calibre.gui2.dbus_export.utils import setup_for_cli_run
from calibre.gui2.dbus_export.widgets import factory

setup_for_cli_run()

def make_checkable(ac, checked=True):
    ac.setCheckable(True), ac.setChecked(checked)

class MainWindow(QMainWindow):

    def __init__(self):
        QMainWindow.__init__(self)
        f = factory()
        self.setMinimumWidth(400)
        self.setWindowTitle('Demo of DBUS menu exporter and systray integration')
        self.statusBar().showMessage(self.windowTitle())
        w = self.centralWidget()
        self.l = QVBoxLayout(w)
        mb = f.create_window_menubar(self)
        self.setMenuBar(mb)
        m = self.menu_one = mb.addMenu('&One')
        m.aboutToShow.connect(self.about_to_show_one)
        s = self.style()
        self.q = q = QAction('&Quit', self)
        q.setShortcut(QKeySequence.Quit)
        q.triggered.connect(QApplication.quit)
        self.addAction(q)
        QApplication.instance().setWindowIcon(QIcon(I('debug.png')))
        for i, icon in zip(xrange(3), map(s.standardIcon, (s.SP_DialogOkButton, s.SP_DialogCancelButton, s.SP_ArrowUp))):
            ac = m.addAction('One - &%d' % (i + 1))
            ac.setShortcut(QKeySequence(Qt.CTRL | (Qt.Key_1 + i), Qt.SHIFT | (Qt.Key_1 + i)))
            ac.setIcon(icon)
        m.addSeparator()
        self.menu_two = m2 = m.addMenu('A &submenu')
        for i, icon in zip(xrange(3), map(s.standardIcon, (s.SP_DialogOkButton, s.SP_DialogCancelButton, s.SP_ArrowUp))):
            ac = m2.addAction('Two - &%d' % (i + 1))
            ac.setShortcut(QKeySequence(Qt.CTRL | (Qt.Key_A + i)))
            ac.setIcon(icon)
        m2.aboutToShow.connect(self.about_to_show_two)
        m2.addSeparator(), m.addSeparator()
        m.addAction('&Disabled action').setEnabled(False)
        ac = m.addAction('A checkable action')
        make_checkable(ac)
        g = QActionGroup(self)
        make_checkable(g.addAction(m.addAction('Exclusive 1')))
        make_checkable(g.addAction(m.addAction('Exclusive 2')), False)
        m.addSeparator()
        self.about_to_show_sentinel = m.addAction('This action\'s text should change before menu is shown')
        self.as_count = 0
        for ac in mb.findChildren(QAction):
            ac.triggered.connect(self.action_triggered)
        for m in mb.findChildren(QMenu):
            m.aboutToShow.connect(self.about_to_show)
        self.systray = f.create_system_tray_icon(parent=self, title=self.windowTitle())
        if self.systray is not None:
            self.systray.activated.connect(self.tray_activated)
            self.sm = m = QMenu()
            m.addAction('Show/hide main window').triggered.connect(self.tray_activated)
            m.addAction(q)
            self.systray.setContextMenu(m)
            self.update_tray_toggle_action()
        print ('DBUS connection unique name:', f.bus.get_unique_name())

    def update_tray_toggle_action(self):
        if hasattr(self, 'sm'):
            self.sm.actions()[0].setText('Hide main window' if self.isVisible() else 'Show main window')

    def hideEvent(self, ev):
        if not ev.spontaneous():
            self.update_tray_toggle_action()
        return QMainWindow.hideEvent(self, ev)

    def showEvent(self, ev):
        if not ev.spontaneous():
            self.update_tray_toggle_action()
        return QMainWindow.showEvent(self, ev)

    def tray_activated(self):
        self.setVisible(not self.isVisible())

    def action_triggered(self, checked=False):
        ac = self.sender()
        text = 'Action triggered: %s' % ac.text()
        self.statusBar().showMessage(text)

    def about_to_show(self):
        self.statusBar().showMessage('About to show menu: %s' % self.sender().title())

    def about_to_show_one(self):
        self.as_count += 1
        self.about_to_show_sentinel.setText('About to show handled: %d' % self.as_count)

    def about_to_show_two(self):
        self.menu_two.addAction('Action added by about to show')

app = QApplication([])
app.setApplicationName('com.calibre-ebook.DBusExportDemo')
mw = MainWindow()
mw.show()
app.exec_()
