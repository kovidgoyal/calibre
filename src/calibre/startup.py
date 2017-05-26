__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Perform various initialization tasks.
'''

import locale, sys

# Default translation is NOOP
import __builtin__
__builtin__.__dict__['_'] = lambda s: s

# For strings which belong in the translation tables, but which shouldn't be
# immediately translated to the environment language
__builtin__.__dict__['__'] = lambda s: s

from calibre.constants import iswindows, preferred_encoding, plugins, isosx, islinux, isfrozen, DEBUG

_run_once = False
winutil = winutilerror = None

if not _run_once:
    _run_once = True

    if not isfrozen:
        # Prevent PyQt4 from being loaded
        class PyQt4Ban(object):

            def find_module(self, fullname, path=None):
                if fullname.startswith('PyQt4'):
                    return self

            def load_module(self, fullname):
                raise ImportError('Importing PyQt4 is not allowed as calibre uses PyQt5')

        sys.meta_path.insert(0, PyQt4Ban())

    #
    # Platform specific modules
    if iswindows:
        winutil, winutilerror = plugins['winutil']
        if not winutil:
            raise RuntimeError('Failed to load the winutil plugin: %s'%winutilerror)
        if len(sys.argv) > 1 and not isinstance(sys.argv[1], unicode):
            sys.argv[1:] = winutil.argv()[1-len(sys.argv):]

    #
    # Ensure that all temp files/dirs are created under a calibre tmp dir
    from calibre.ptempfile import base_dir
    try:
        base_dir()
    except EnvironmentError:
        pass  # Ignore this error during startup, so we can show a better error message to the user later.

    #
    # Convert command line arguments to unicode
    enc = preferred_encoding
    if isosx:
        enc = 'utf-8'
    for i in range(1, len(sys.argv)):
        if not isinstance(sys.argv[i], unicode):
            sys.argv[i] = sys.argv[i].decode(enc, 'replace')

    #
    # Ensure that the max number of open files is at least 1024
    if iswindows:
        # See https://msdn.microsoft.com/en-us/library/6e3b887c.aspx
        if hasattr(winutil, 'setmaxstdio'):
            winutil.setmaxstdio(max(1024, winutil.getmaxstdio()))
    else:
        import resource
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        if soft < 1024:
            try:
                resource.setrlimit(resource.RLIMIT_NOFILE, (min(1024, hard), hard))
            except Exception:
                if DEBUG:
                    import traceback
                    traceback.print_exc()

    #
    # Setup resources
    import calibre.utils.resources as resources
    resources

    #
    # Setup translations
    from calibre.utils.localization import set_translators

    set_translators()

    #
    # Initialize locale
    # Import string as we do not want locale specific
    # string.whitespace/printable, on windows especially, this causes problems.
    # Before the delay load optimizations, string was loaded before this point
    # anyway, so we preserve the old behavior explicitly.
    import string
    string
    try:
        locale.setlocale(locale.LC_ALL, '')  # set the locale to the user's default locale
    except:
        dl = locale.getdefaultlocale()
        try:
            if dl:
                locale.setlocale(locale.LC_ALL, dl[0])
        except:
            pass

    # local_open() opens a file that wont be inherited by child processes
    if iswindows:
        def local_open(name, mode='r', bufsize=-1):
            mode += 'N'
            return open(name, mode, bufsize)
    elif isosx:
        import fcntl
        FIOCLEX = 0x20006601

        def local_open(name, mode='r', bufsize=-1):
            ans = open(name, mode, bufsize)
            try:
                fcntl.ioctl(ans.fileno(), FIOCLEX)
            except EnvironmentError:
                fcntl.fcntl(ans, fcntl.F_SETFD, fcntl.fcntl(ans, fcntl.F_GETFD) | fcntl.FD_CLOEXEC)
            return ans
    else:
        import fcntl
        try:
            cloexec_flag = fcntl.FD_CLOEXEC
        except AttributeError:
            cloexec_flag = 1
        supports_mode_e = False

        def local_open(name, mode='r', bufsize=-1):
            global supports_mode_e
            mode += 'e'
            ans = open(name, mode, bufsize)
            if supports_mode_e:
                return ans
            old = fcntl.fcntl(ans, fcntl.F_GETFD)
            if not (old & cloexec_flag):
                fcntl.fcntl(ans, fcntl.F_SETFD, old | cloexec_flag)
            else:
                supports_mode_e = True
            return ans

    __builtin__.__dict__['lopen'] = local_open

    from calibre.utils.icu import title_case, lower as icu_lower, upper as icu_upper
    __builtin__.__dict__['icu_lower'] = icu_lower
    __builtin__.__dict__['icu_upper'] = icu_upper
    __builtin__.__dict__['icu_title'] = title_case

    if islinux:
        # Name all threads at the OS level created using the threading module, see
        # http://bugs.python.org/issue15500
        import ctypes, ctypes.util, threading
        libpthread_path = ctypes.util.find_library("pthread")
        if libpthread_path:
            libpthread = ctypes.CDLL(libpthread_path)
            if hasattr(libpthread, "pthread_setname_np"):
                pthread_setname_np = libpthread.pthread_setname_np
                pthread_setname_np.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
                pthread_setname_np.restype = ctypes.c_int
                orig_start = threading.Thread.start

                def new_start(self):
                    orig_start(self)
                    try:
                        name = self.name
                        if not name or name.startswith('Thread-'):
                            name = self.__class__.__name__
                            if name == 'Thread':
                                name = self.name
                        if name:
                            if isinstance(name, unicode):
                                name = name.encode('ascii', 'replace')
                            ident = getattr(self, "ident", None)
                            if ident is not None:
                                pthread_setname_np(ident, name[:15])
                    except Exception:
                        pass  # Don't care about failure to set name
                threading.Thread.start = new_start


def test_lopen():
    from calibre.ptempfile import TemporaryDirectory
    from calibre import CurrentDir
    n = u'f\xe4llen'
    print('testing lopen()')

    if iswindows:
        import msvcrt, win32api

        def assert_not_inheritable(f):
            if win32api.GetHandleInformation(msvcrt.get_osfhandle(f.fileno())) & 0b1:
                raise SystemExit('File handle is inheritable!')
    else:
        def assert_not_inheritable(f):
            if not fcntl.fcntl(f, fcntl.F_GETFD) & fcntl.FD_CLOEXEC:
                raise SystemExit('File handle is inheritable!')

    def copen(*args):
        ans = lopen(*args)
        assert_not_inheritable(ans)
        return ans

    with TemporaryDirectory() as tdir, CurrentDir(tdir):
        with copen(n, 'w') as f:
            f.write('one')

        print 'O_CREAT tested'
        with copen(n, 'w+b') as f:
            f.write('two')
        with copen(n, 'r') as f:
            if f.read() == 'two':
                print 'O_TRUNC tested'
            else:
                raise Exception('O_TRUNC failed')
        with copen(n, 'ab') as f:
            f.write('three')
        with copen(n, 'r+') as f:
            if f.read() == 'twothree':
                print 'O_APPEND tested'
            else:
                raise Exception('O_APPEND failed')
        with copen(n, 'r+') as f:
            f.seek(3)
            f.write('xxxxx')
            f.seek(0)
            if f.read() == 'twoxxxxx':
                print 'O_RANDOM tested'
            else:
                raise Exception('O_RANDOM failed')
