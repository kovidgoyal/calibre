__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'


import gc
import os
import sys
import weakref

from qt.core import QAction, QIcon, QKeySequence, QMainWindow, QMenu, QMenuBar, QObject, Qt, QTimer, pyqtSignal

from calibre import as_unicode, prepare_string_for_xml, prints
from calibre.constants import iswindows
from calibre.gui2 import error_dialog
from calibre.utils.config import OptionParser
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
            mw.display_unhandled_exception.emit(type, value, tb)
        else:
            sys.__excepthook__(type, value, tb)


class MainWindow(QMainWindow):

    ___menu_bar = None
    ___menu     = None
    __actions   = []
    display_unhandled_exception = pyqtSignal(object, object, object)

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

    def __init__(self, opts=None, parent=None, disable_automatic_gc=False):
        QMainWindow.__init__(self, parent)
        self.display_unhandled_exception.connect(self.unhandled_exception, type=Qt.ConnectionType.QueuedConnection)
        if disable_automatic_gc:
            self._gc = GarbageCollector(self, debug=False)

    def enable_garbage_collection(self, enabled=True):
        if hasattr(self, '_gc'):
            self._gc.timer.blockSignals(not enabled)
        else:
            gc.enable() if enabled else gc.disable()

    def set_exception_handler(self):
        sys.excepthook = ExceptionHandler(self)

    def show_possible_sharing_violation(self, e: Exception, det_msg: str = '') -> bool:
        if not iswindows or not isinstance(e, OSError):
            return False
        import errno

        from calibre_extensions import winutil
        if not (e.winerror == winutil.ERROR_SHARING_VIOLATION or e.errno == errno.EACCES or isinstance(e, PermissionError)):
            return False
        msg = getattr(e, 'locking_violation_msg', '')
        if msg:
            msg = msg.strip() + ' '
        fname = e.filename

        def no_processes_found() -> bool:
            is_folder = fname and os.path.isdir(fname)
            if e.winerror == winutil.ERROR_SHARING_VIOLATION:
                if fname:
                    if is_folder:
                        dmsg = _('The folder "{}" is opened in another program, so calibre cannot access it.').format(fname)
                    else:
                        dmsg = _('The file "{}" is opened in another program, so calibre cannot access it.').format(fname)
                else:
                    if is_folder:
                        dmsg = _('A folder is open in another program so calibre cannot access it.')
                    else:
                        dmsg = _('A file is open in another program so calibre cannot access it.')
                if is_folder:
                    dmsg += _('This is usually caused by leaving Windows explorer or a similar file manager open'
                              ' to a folder in the calibre library. Close Windows explorer and retry.')
                else:
                    dmsg += _('This is usually caused by software such as antivirus or file sync (aka DropBox and similar)'
                              ' accessing files in the calibre library folder at the same time as calibre. Try excluding'
                              ' the calibre library folder from such software.')
                error_dialog(self, _('Cannot open file or folder as it is in use'), msg + dmsg, det_msg=det_msg, show=True)
                return True
            if msg:
                if fname:
                    dmsg = _('Permission was denied by the operating system when calibre tried to access the file: "{0}".').format(fname)
                else:
                    dmsg = _('Permission was denied by the operating system when calibre tried to access a file.')
                dmsg += ' ' + _('This means either that the permissions on the file or its parent folder are incorrect or the file is'
                ' open in another program.')
                error_dialog(self, _('Cannot open file or folder'), msg + dmsg, det_msg=det_msg, show=True)
                return True
            return False

        if not hasattr(winutil, 'get_processes_using_files'):
            return no_processes_found()  # running from source
        if not e.filename and not e.filename2:
            return no_processes_found()
        if e.filename and isinstance(e.filename, str):
            if os.path.isdir(e.filename):
                return no_processes_found()
            try:
                p = winutil.get_processes_using_files(e.filename)
            except OSError:
                return no_processes_found()
        if not p and e.filename2 and isinstance(e.filename2, str):
            if os.path.isdir(e.filename2):
                return no_processes_found()
            try:
                p = winutil.get_processes_using_files(e.filename2)
            except OSError:
                return no_processes_found()
            fname = e.filename2
        if not p:
            return no_processes_found()

        path_map = {x['path']: x for x in p}
        is_folder = fname and os.path.isdir(fname)
        if is_folder:
            dmsg = _('Could not open the folder: "{}". It is already opened in the following programs:').format(fname)
        else:
            dmsg = _('Could not open the file: "{}". It is already opened in the following programs:').format(fname)
        for path, x in path_map.items():
            dmsg += '<div>' + prepare_string_for_xml(f'{x["app_name"]}: {path}')
        msg = prepare_string_for_xml(msg)
        error_dialog(self, _('Cannot open file or folder as it is in use'), '<p>' + msg + dmsg, det_msg=det_msg, show=True)
        return True

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
            prints(fe, file=sys.stderr)
            try:
                if self.show_possible_sharing_violation(value, det_msg=fe):
                    return
            except Exception:
                traceback.print_exc()
            msg = '<b>%s</b>:'%exc_type.__name__ + prepare_string_for_xml(as_unicode(value))
            error_dialog(self, _('Unhandled exception'), msg, det_msg=fe,
                    show=True)
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
