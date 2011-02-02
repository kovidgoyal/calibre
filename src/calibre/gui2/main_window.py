__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'

import StringIO, traceback, sys

from PyQt4.Qt import QMainWindow, QString, Qt, QFont, QCoreApplication, SIGNAL,\
                     QAction, QMenu, QMenuBar, QIcon, pyqtSignal
from calibre.gui2.dialogs.conversion_error import ConversionErrorDialog
from calibre.utils.config import OptionParser
from calibre.gui2 import error_dialog
from calibre import prints

def option_parser(usage='''\
Usage: %prog [options]

Launch the Graphical User Interface
'''):
    parser = OptionParser(usage)
    parser.add_option('--redirect-console-output', default=False, action='store_true', dest='redirect',
                      help=_('Redirect console output to a dialog window (both stdout and stderr). Useful on windows where GUI apps do not have a output streams.'))
    return parser

class DebugWindow(ConversionErrorDialog):

    def __init__(self, parent):
        ConversionErrorDialog.__init__(self, parent, 'Console output', '')
        self.setModal(Qt.NonModal)
        font = QFont()
        font.setStyleHint(QFont.TypeWriter)
        self.text.setFont(font)

    def write(self, msg):
        self.text.setPlainText(self.text.toPlainText()+QString(msg))

    def flush(self):
        pass

class MainWindow(QMainWindow):

    ___menu_bar = None
    ___menu     = None
    __actions   = []

    keyboard_interrupt = pyqtSignal()

    @classmethod
    def create_application_menubar(cls):
        mb = QMenuBar(None)
        menu = QMenu()
        for action in cls.get_menubar_actions():
            menu.addAction(action)
            cls.__actions.append(action)
            yield action
        mb.addMenu(menu)
        cls.___menu_bar = mb
        cls.___menu = menu


    @classmethod
    def get_menubar_actions(cls):
        preferences_action = QAction(QIcon(I('config.png')), _('&Preferences'), None)
        quit_action        = QAction(QIcon(I('window-close.png')), _('&Quit'), None)
        preferences_action.setMenuRole(QAction.PreferencesRole)
        quit_action.setMenuRole(QAction.QuitRole)
        return preferences_action, quit_action

    def __init__(self, opts, parent=None):
        QMainWindow.__init__(self, parent)
        app = QCoreApplication.instance()
        if app is not None:
            self.connect(app, SIGNAL('unixSignal(int)'), self.unix_signal)
        if getattr(opts, 'redirect', False):
            self.__console_redirect = DebugWindow(self)
            sys.stdout = sys.stderr = self.__console_redirect
            self.__console_redirect.show()

    def unix_signal(self, signal):
        print 'Received signal:', repr(signal)

    def unhandled_exception(self, type, value, tb):
        if type == KeyboardInterrupt:
            self.keyboard_interrupt.emit()
            return
        try:
            sio = StringIO.StringIO()
            traceback.print_exception(type, value, tb, file=sio)
            fe = sio.getvalue()
            prints(fe, file=sys.stderr)
            msg = '<b>%s</b>:'%type.__name__ + unicode(str(value), 'utf8', 'replace')
            error_dialog(self, _('Unhandled exception'), msg, det_msg=fe,
                    show=True)
        except BaseException:
            pass
