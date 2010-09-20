#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'
__version__   = '0.1.0'

from PyQt4.Qt import QMainWindow, QToolBar, QStatusBar, QLabel, QFont, Qt, \
    QApplication

from calibre.constants import __appname__, __version__
from calibre.utils.pyconsole.editor import Editor

class MainWindow(QMainWindow):

    def __init__(self, default_status_msg):

        QMainWindow.__init__(self)

        self.resize(600, 700)

        # Setup status bar {{{
        self.status_bar = QStatusBar(self)
        self.status_bar.defmsg = QLabel(__appname__ + _(' console ') +
                __version__)
        self.status_bar._font = QFont()
        self.status_bar._font.setBold(True)
        self.status_bar.defmsg.setFont(self.status_bar._font)
        self.status_bar.addWidget(self.status_bar.defmsg)
        self.setStatusBar(self.status_bar)
        # }}}

        # Setup tool bar {{{
        self.tool_bar = QToolBar(self)
        self.addToolBar(Qt.BottomToolBarArea, self.tool_bar)
        self.tool_bar.setToolButtonStyle(Qt.ToolButtonTextOnly)
        # }}}

        self.editor = Editor(parent=self)
        self.setCentralWidget(self.editor)



def main():
    QApplication.setApplicationName(__appname__+' console')
    QApplication.setOrganizationName('Kovid Goyal')
    app = QApplication([])
    m = MainWindow(_('Welcome to') + ' ' + __appname__+' console')
    m.show()
    app.exec_()


if __name__ == '__main__':
    main()

