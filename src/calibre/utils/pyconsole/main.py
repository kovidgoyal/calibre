#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'
__version__   = '0.1.0'

from functools import partial

from PyQt4.Qt import QDialog, QToolBar, QStatusBar, QLabel, QFont, Qt, \
    QApplication, QIcon, QVBoxLayout, QAction

from calibre.utils.pyconsole import dynamic, __appname__, __version__
from calibre.utils.pyconsole.console import Console

class MainWindow(QDialog):

    def __init__(self,
            default_status_msg=_('Welcome to') + ' ' + __appname__+' console',
            parent=None):
        QDialog.__init__(self, parent)

        self.restart_requested = False
        self.l = QVBoxLayout()
        self.setLayout(self.l)

        self.resize(800, 600)
        geom = dynamic.get('console_window_geometry', None)
        if geom is not None:
            self.restoreGeometry(geom)

        # Setup tool bar {{{
        self.tool_bar = QToolBar(self)
        self.tool_bar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.l.addWidget(self.tool_bar)
        # }}}

        # Setup status bar {{{
        self.status_bar = QStatusBar(self)
        self.status_bar.defmsg = QLabel(__appname__ + _(' console ') +
                __version__)
        self.status_bar._font = QFont()
        self.status_bar._font.setBold(True)
        self.status_bar.defmsg.setFont(self.status_bar._font)
        self.status_bar.addWidget(self.status_bar.defmsg)
        # }}}

        self.console = Console(parent=self)
        self.console.running.connect(partial(self.status_bar.showMessage,
            _('Code is running')))
        self.console.running_done.connect(self.status_bar.clearMessage)
        self.l.addWidget(self.console)
        self.l.addWidget(self.status_bar)
        self.setWindowTitle(__appname__ + ' console')
        self.setWindowIcon(QIcon(I('console.png')))

        self.restart_action = QAction(_('Restart console'), self)
        self.restart_action.setShortcut(_('Ctrl+R'))
        self.addAction(self.restart_action)
        self.restart_action.triggered.connect(self.restart)
        self.console.context_menu.addAction(self.restart_action)

    def restart(self):
        self.restart_requested = True
        self.reject()

    def closeEvent(self, *args):
        dynamic.set('console_window_geometry',
                bytearray(self.saveGeometry()))
        self.console.shutdown()
        return QDialog.closeEvent(self, *args)


def show():
    while True:
        m = MainWindow()
        m.exec_()
        if not m.restart_requested:
            break

def main():
    QApplication.setApplicationName(__appname__+' console')
    QApplication.setOrganizationName('Kovid Goyal')
    app = QApplication([])
    app
    show()

if __name__ == '__main__':
    main()

