__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'


import sys, gc, weakref

from qt.core import (QMainWindow, QTimer, QAction, QMenu, QMenuBar, QIcon,
                      QObject, QKeySequence)
from calibre.utils.config import OptionParser
from calibre.gui2 import error_dialog
from calibre import prints, as_unicode, prepare_string_for_xml
from polyglot.io import PolyglotStringIO


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
        # gc.set_debug(gc.DEBUG_SAVEALL)

    def check(self):
        # return self.debug_cycles()
        l0, l1, l2 = gc.get_count()
        if self.debug:
            print('gc_check called:', l0, l1, l2)
        if l0 > self.threshold[0]:
            num = gc.collect(0)
            if self.debug:
                print('collecting gen 0, found:', num, 'unreachable')
            if l1 > self.threshold[1]:
                num = gc.collect(1)
                if self.debug:
                    print('collecting gen 1, found:', num, 'unreachable')
                if l2 > self.threshold[2]:
                    num = gc.collect(2)
                    if self.debug:
                        print('collecting gen 2, found:', num, 'unreachable')

    def debug_cycles(self):
        gc.collect()
        for obj in gc.garbage:
            print(obj, repr(obj), type(obj))


class ExceptionHandler:

    def __init__(self, main_window):
        self.wref = weakref.ref(main_window)

    def __call__(self, type, value, tb):
        mw = self.wref()
        if mw is not None:
            mw.unhandled_exception(type, value, tb)
        else:
            sys.__excepthook__(type, value, tb)


class MainWindow(QMainWindow):

    ___menu_bar = None
    ___menu     = None
    __actions   = []

    @classmethod
    def create_application_menubar(cls):
        if not cls.__actions:
            mb = QMenuBar(None)
            menu = QMenu()
            for action in cls.get_menubar_actions():
                menu.addAction(action)
                cls.__actions.append(action)
            mb.addMenu(menu)
            cls.___menu_bar = mb
            cls.___menu = menu
        return cls.__actions

    @classmethod
    def get_menubar_actions(cls):
        preferences_action = QAction(QIcon.ic('config.png'), _('&Preferences'), None)
        quit_action        = QAction(QIcon.ic('window-close.png'), _('&Quit'), None)
        preferences_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        quit_action.setMenuRole(QAction.MenuRole.QuitRole)
        return preferences_action, quit_action

    @property
    def native_menubar(self):
        return self.___menu_bar

    def __init__(self, opts, parent=None, disable_automatic_gc=False):
        QMainWindow.__init__(self, parent)
        if disable_automatic_gc:
            self._gc = GarbageCollector(self, debug=False)

    def enable_garbage_collection(self, enabled=True):
        if hasattr(self, '_gc'):
            self._gc.timer.blockSignals(not enabled)
        else:
            gc.enable() if enabled else gc.disable()

    def set_exception_handler(self):
        sys.excepthook = ExceptionHandler(self)

    def unhandled_exception(self, exc_type, value, tb):
        if exc_type is KeyboardInterrupt:
            return
        import traceback
        try:
            sio = PolyglotStringIO(errors='replace')
            try:
                from calibre.debug import print_basic_debug_info
                print_basic_debug_info(out=sio)
            except:
                pass
            traceback.print_exception(exc_type, value, tb, file=sio)
            if getattr(value, 'locking_debug_msg', None):
                prints(value.locking_debug_msg, file=sio)
            fe = sio.getvalue()
            msg = '<b>%s</b>:'%exc_type.__name__ + prepare_string_for_xml(as_unicode(value))
            error_dialog(self, _('Unhandled exception'), msg, det_msg=fe,
                    show=True)
            prints(fe, file=sys.stderr)
        except BaseException:
            pass
        except:
            pass


def clone_menu(menu):
    # This is needed to workaround a bug in Qt 5.5+ and Unity. When the same
    # QAction object is used in both a QMenuBar and a QMenu, sub-menus of the
    # QMenu flicker when rendered under Unity.

    def clone_action(ac, parent):
        if ac.isSeparator():
            ans = QAction(parent)
            ans.setSeparator(True)
            return ans
        sc = ac.shortcut()
        sc = '' if sc.isEmpty() else sc.toString(QKeySequence.SequenceFormat.NativeText)
        text = ac.text()
        if '\t' not in text:
            text += '\t' + sc
        ans = QAction(ac.icon(), text, parent)
        ans.triggered.connect(ac.trigger)
        ans.setEnabled(ac.isEnabled())
        ans.setStatusTip(ac.statusTip())
        ans.setVisible(ac.isVisible())
        return ans

    def clone_one_menu(m):
        m.aboutToShow.emit()
        ans = QMenu(m.parent())
        for ac in m.actions():
            cac = clone_action(ac, ans)
            ans.addAction(cac)
            m = ac.menu()
            if m is not None:
                cac.setMenu(clone_menu(m))
        return ans
    return clone_one_menu(menu)
