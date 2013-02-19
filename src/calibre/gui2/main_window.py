from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'


import StringIO, traceback, sys, gc

from PyQt4.Qt import (QMainWindow, QTimer, QAction, QMenu, QMenuBar, QIcon,
                      pyqtSignal, QObject)
from calibre.utils.config import OptionParser
from calibre.gui2 import error_dialog
from calibre import prints

def option_parser(usage='''\
Usage: %prog [options]

Launch the Graphical User Interface
'''):
    parser = OptionParser(usage)
    return parser

class GarbageCollector(QObject):

    '''
    Disable automatic garbage collection and instead collect manually
    every INTERVAL milliseconds.

    This is done to ensure that garbage collection only happens in the GUI
    thread, as otherwise Qt can crash.
    '''

    INTERVAL = 5000

    def __init__(self, parent, debug=False):
        QObject.__init__(self, parent)
        self.debug = debug

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check)

        self.threshold = gc.get_threshold()
        gc.disable()
        self.timer.start(self.INTERVAL)
        #gc.set_debug(gc.DEBUG_SAVEALL)

    def check(self):
        #return self.debug_cycles()
        l0, l1, l2 = gc.get_count()
        if self.debug:
            print ('gc_check called:', l0, l1, l2)
        if l0 > self.threshold[0]:
            num = gc.collect(0)
            if self.debug:
                print ('collecting gen 0, found:', num, 'unreachable')
            if l1 > self.threshold[1]:
                num = gc.collect(1)
                if self.debug:
                    print ('collecting gen 1, found:', num, 'unreachable')
                if l2 > self.threshold[2]:
                    num = gc.collect(2)
                    if self.debug:
                        print ('collecting gen 2, found:', num, 'unreachable')

    def debug_cycles(self):
        gc.collect()
        for obj in gc.garbage:
            print (obj, repr(obj), type(obj))

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

    def __init__(self, opts, parent=None, disable_automatic_gc=False):
        QMainWindow.__init__(self, parent)
        if disable_automatic_gc:
            self._gc = GarbageCollector(self, debug=False)

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
        except:
            pass
