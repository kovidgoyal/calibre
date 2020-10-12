#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import time

from PyQt5.Qt import (
    QApplication, QMainWindow, QVBoxLayout, Qt, QKeySequence, QAction,
    QActionGroup, QMenu, QPushButton, QWidget, QTimer, QMessageBox, pyqtSignal)

from calibre.gui2.dbus_export.utils import setup_for_cli_run
from calibre.gui2.dbus_export.widgets import factory
from polyglot.builtins import range

setup_for_cli_run()


def make_checkable(ac, checked=True):
    ac.setCheckable(True), ac.setChecked(checked)


class MainWindow(QMainWindow):

    window_blocked = pyqtSignal()
    window_unblocked = pyqtSignal()

    def __init__(self):
        QMainWindow.__init__(self)
        f = factory()
        self.setMinimumWidth(400)
        self.setWindowTitle('Demo of DBUS menu exporter and systray integration')
        self.statusBar().showMessage(self.windowTitle())
        w = QWidget(self)
        self.setCentralWidget(w)
        self.l = l = QVBoxLayout(w)
        mb = self.menu_bar = f.create_window_menubar(self)
        m = self.menu_one = mb.addMenu('&One')
        m.aboutToShow.connect(self.about_to_show_one)
        s = self.style()
        self.q = q = QAction('&Quit', self)
        q.setShortcut(QKeySequence.Quit), q.setIcon(s.standardIcon(s.SP_DialogCancelButton))
        q.triggered.connect(QApplication.quit)
        self.addAction(q)
        QApplication.instance().setWindowIcon(s.standardIcon(s.SP_ComputerIcon))
        for i, icon in zip(range(3), map(s.standardIcon, (s.SP_DialogOkButton, s.SP_DialogHelpButton, s.SP_ArrowUp))):
            ac = m.addAction('One - &%d' % (i + 1))
            ac.setShortcut(QKeySequence(Qt.CTRL | (Qt.Key_1 + i), Qt.SHIFT | (Qt.Key_1 + i)))
            ac.setIcon(icon)
        m.addSeparator()
        self.menu_two = m2 = m.addMenu('A &submenu')
        for i, icon in zip(range(3), map(s.standardIcon, (s.SP_DialogOkButton, s.SP_DialogCancelButton, s.SP_ArrowUp))):
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
            self.cib = b = QPushButton('Change system tray icon')
            l.addWidget(b), b.clicked.connect(self.change_icon)
            self.hib = b = QPushButton('Show/Hide system tray icon')
            l.addWidget(b), b.clicked.connect(self.systray.toggle)
            self.update_tooltip_timer = t = QTimer(self)
            t.setInterval(1000), t.timeout.connect(self.update_tooltip), t.start()
        self.ab = b = QPushButton('Add a new menu')
        b.clicked.connect(self.add_menu), l.addWidget(b)
        self.rb = b = QPushButton('Remove a created menu')
        b.clicked.connect(self.remove_menu), l.addWidget(b)
        self.sd = b = QPushButton('Show modal dialog')
        b.clicked.connect(self.show_dialog), l.addWidget(b)
        print('DBUS connection unique name:', f.bus.get_unique_name())

    def update_tooltip(self):
        self.systray.setToolTip(time.strftime('A dynamically updated tooltip [%H:%M:%S]'))

    def add_menu(self):
        mb = self.menu_bar
        m = mb.addMenu('Created menu %d' % len(mb.actions()))
        for i in range(3):
            m.addAction('Some action %d' % i)
        for ac in m.findChildren(QAction):
            ac.triggered.connect(self.action_triggered)
        m.aboutToShow.connect(self.about_to_show)

    def remove_menu(self):
        mb = self.menu_bar
        if len(mb.actions()) > 1:
            mb.removeAction(mb.actions()[-1])

    def change_icon(self):
        import random
        s = self.style()
        num = s.SP_ComputerIcon
        while num == s.SP_ComputerIcon:
            num = random.choice(range(20))
        self.systray.setIcon(self.style().standardIcon(num))

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

    def tray_activated(self, reason):
        self.setVisible(not self.isVisible())

    def action_triggered(self, checked=False):
        ac=self.sender()
        text='Action triggered: %s' % ac.text()
        self.statusBar().showMessage(text)

    def about_to_show(self):
        self.statusBar().showMessage('About to show menu: %s' % self.sender().title())

    def about_to_show_one(self):
        self.as_count += 1
        self.about_to_show_sentinel.setText('About to show handled: %d' % self.as_count)

    def about_to_show_two(self):
        self.menu_two.addAction('Action added by about to show')

    def show_dialog(self):
        QMessageBox.information(self, 'A test dialog', 'While this dialog is shown, the global menu should be hidden')

    def event(self, ev):
        if ev.type() in (ev.WindowBlocked, ev.WindowUnblocked):
            if ev.type() == ev.WindowBlocked:
                self.window_blocked.emit()
            else:
                self.window_unblocked.emit()
        return QMainWindow.event(self, ev)


app=QApplication([])
app.setAttribute(Qt.AA_DontUseNativeMenuBar, False)
app.setApplicationName('com.calibre-ebook.DBusExportDemo')
mw=MainWindow()
mw.show()
app.exec_()
