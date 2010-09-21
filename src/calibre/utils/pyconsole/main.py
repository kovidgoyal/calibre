#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'
__version__   = '0.1.0'

from functools import partial

from PyQt4.Qt import QDialog, QToolBar, QStatusBar, QLabel, QFont, Qt, \
    QApplication, QIcon, QVBoxLayout

from calibre.constants import __appname__, __version__
from calibre.utils.pyconsole.console import Console

class MainWindow(QDialog):

    def __init__(self,
            default_status_msg=_('Welcome to') + ' ' + __appname__+' console',
            parent=None):

        QDialog.__init__(self, parent)
        self.l = QVBoxLayout()
        self.setLayout(self.l)

        self.resize(800, 600)

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


def main():
    QApplication.setApplicationName(__appname__+' console')
    QApplication.setOrganizationName('Kovid Goyal')
    app = QApplication([])
    m = MainWindow()
    m.show()
    app.exec_()


if __name__ == '__main__':
    main()

