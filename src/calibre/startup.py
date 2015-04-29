__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Perform various initialization tasks.
'''

import locale, sys, os, re

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
    base_dir()

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
    if not iswindows:
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
                locale.setlocale(dl[0])
        except:
            pass

    #

    def local_open(name, mode='r', bufsize=-1):
        '''
        Open a file that wont be inherited by child processes

        Only supports the following modes:
            r, w, a, rb, wb, ab, r+, w+, a+, r+b, w+b, a+b
        '''
        if iswindows:
            class fwrapper(object):

                def __init__(self, name, fobject):
                    object.__setattr__(self, 'fobject', fobject)
                    object.__setattr__(self, 'name', name)

                def __getattribute__(self, attr):
                    if attr in ('name', '__enter__', '__str__', '__unicode__',
                            '__repr__', '__exit__'):
                        return object.__getattribute__(self, attr)
                    fobject = object.__getattribute__(self, 'fobject')
                    return getattr(fobject, attr)

                def __setattr__(self, attr, val):
                    fobject = object.__getattribute__(self, 'fobject')
                    return setattr(fobject, attr, val)

                def __repr__(self):
                    fobject = object.__getattribute__(self, 'fobject')
                    name = object.__getattribute__(self, 'name')
                    return re.sub(r'''['"]<fdopen>['"]''', repr(name),
                            repr(fobject))

                def __str__(self):
                    return repr(self)

                def __unicode__(self):
                    return repr(self).decode('utf-8')

                def __enter__(self):
                    fobject = object.__getattribute__(self, 'fobject')
                    fobject.__enter__()
                    return self

                def __exit__(self, *args):
                    fobject = object.__getattribute__(self, 'fobject')
                    return fobject.__exit__(*args)

            m = mode[0]
            random = len(mode) > 1 and mode[1] == '+'
            binary = mode[-1] == 'b'

            if m == 'a':
                flags = os.O_APPEND| os.O_RDWR
                flags |= os.O_RANDOM if random else os.O_SEQUENTIAL
            elif m == 'r':
                if random:
                    flags = os.O_RDWR | os.O_RANDOM
                else:
                    flags = os.O_RDONLY | os.O_SEQUENTIAL
            elif m == 'w':
                if random:
                    flags = os.O_RDWR | os.O_RANDOM
                else:
                    flags = os.O_WRONLY | os.O_SEQUENTIAL
                flags |= os.O_TRUNC | os.O_CREAT
            if binary:
                flags |= os.O_BINARY
            else:
                flags |= os.O_TEXT
            flags |= os.O_NOINHERIT
            fd = os.open(name, flags)
            ans = os.fdopen(fd, mode, bufsize)
            ans = fwrapper(name, ans)
        else:
            import fcntl
            try:
                cloexec_flag = fcntl.FD_CLOEXEC
            except AttributeError:
                cloexec_flag = 1
            # Python 2.x uses fopen which on recent glibc/linux kernel at least
            # respects the 'e' mode flag. On OS X the e is ignored. So to try
            # to get atomicity where possible we pass 'e' and then only use
            # fcntl only if CLOEXEC was not set.
            if islinux:
                mode += 'e'
            ans = open(name, mode, bufsize)
            old = fcntl.fcntl(ans, fcntl.F_GETFD)
            if not (old & cloexec_flag):
                fcntl.fcntl(ans, fcntl.F_SETFD, old | cloexec_flag)
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

    with TemporaryDirectory() as tdir:
        with CurrentDir(tdir):
            with lopen(n, 'w') as f:
                f.write('one')
            print 'O_CREAT tested'
            with lopen(n, 'w+b') as f:
                f.write('two')
            with lopen(n, 'r') as f:
                if f.read() == 'two':
                    print 'O_TRUNC tested'
                else:
                    raise Exception('O_TRUNC failed')
            with lopen(n, 'ab') as f:
                f.write('three')
            with lopen(n, 'r+') as f:
                if f.read() == 'twothree':
                    print 'O_APPEND tested'
                else:
                    raise Exception('O_APPEND failed')
            with lopen(n, 'r+') as f:
                f.seek(3)
                f.write('xxxxx')
                f.seek(0)
                if f.read() == 'twoxxxxx':
                    print 'O_RANDOM tested'
                else:
                    raise Exception('O_RANDOM failed')



