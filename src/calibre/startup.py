
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Perform various initialization tasks.
'''

import locale, sys, os

# Default translation is NOOP
from polyglot.builtins import builtins, unicode_type
builtins.__dict__['_'] = lambda s: s

# For strings which belong in the translation tables, but which shouldn't be
# immediately translated to the environment language
builtins.__dict__['__'] = lambda s: s

# For backwards compat with some third party plugins
builtins.__dict__['dynamic_property'] = lambda func: func(None)


from calibre.constants import iswindows, preferred_encoding, plugins, ismacos, islinux, DEBUG, isfreebsd

_run_once = False
winutil = winutilerror = None


def get_debug_executable():
    exe_name = 'calibre-debug' + ('.exe' if iswindows else '')
    if hasattr(sys, 'frameworks_dir'):
        base = os.path.dirname(sys.frameworks_dir)
        return [os.path.join(base, 'MacOS', exe_name)]
    if getattr(sys, 'run_local', None):
        return [sys.run_local, exe_name]
    nearby = os.path.join(os.path.dirname(os.path.abspath(sys.executable)), exe_name)
    if getattr(sys, 'frozen', False):
        return [nearby]
    exloc = getattr(sys, 'executables_location', None)
    if exloc:
        ans = os.path.join(exloc, exe_name)
        if os.path.exists(ans):
            return [ans]
    if os.path.exists(nearby):
        return [nearby]
    return [exe_name]


if not _run_once:
    _run_once = True
    from importlib.machinery import ModuleSpec
    from importlib.util import find_spec
    from importlib import import_module

    class DeVendorLoader:

        def __init__(self, aliased_name):
            self.aliased_module = import_module(aliased_name)
            try:
                self.path = self.aliased_module.__loader__.path
            except Exception:
                self.path = aliased_name

        def create_module(self, spec):
            return self.aliased_module

        def exec_module(self, module):
            return module

        def __repr__(self):
            return repr(self.path)

    class DeVendor:

        def find_spec(self, fullname, path=None, target=None):
            if fullname == 'calibre.web.feeds.feedparser':
                return find_spec('feedparser')
            if fullname.startswith('calibre.ebooks.markdown'):
                return ModuleSpec(fullname, DeVendorLoader(fullname[len('calibre.ebooks.'):]))

    sys.meta_path.insert(0, DeVendor())

    # Ensure that all temp files/dirs are created under a calibre tmp dir
    from calibre.ptempfile import base_dir
    try:
        base_dir()
    except EnvironmentError:
        pass  # Ignore this error during startup, so we can show a better error message to the user later.

    #
    # Convert command line arguments to unicode
    enc = preferred_encoding
    if ismacos:
        enc = 'utf-8'
    for i in range(1, len(sys.argv)):
        if not isinstance(sys.argv[i], unicode_type):
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
    # Fix multiprocessing
    from multiprocessing import spawn, util

    def get_command_line(**kwds):
        prog = 'from multiprocessing.spawn import spawn_main; spawn_main(%s)'
        prog %= ', '.join('%s=%r' % item for item in kwds.items())
        return get_debug_executable() + ['--fix-multiprocessing', '--', prog]
    spawn.get_command_line = get_command_line
    orig_spawn_passfds = util.spawnv_passfds

    def spawnv_passfds(path, args, passfds):
        try:
            idx = args.index('-c')
        except ValueError:
            return orig_spawn_passfds(args[0], args, passfds)
        patched_args = get_debug_executable() + ['--fix-multiprocessing', '--'] + args[idx + 1:]
        return orig_spawn_passfds(patched_args[0], patched_args, passfds)
    util.spawnv_passfds = spawnv_passfds

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
    local_open = open  # PEP 446
    builtins.__dict__['lopen'] = local_open

    from calibre.utils.icu import title_case, lower as icu_lower, upper as icu_upper
    builtins.__dict__['icu_lower'] = icu_lower
    builtins.__dict__['icu_upper'] = icu_upper
    builtins.__dict__['icu_title'] = title_case

    def connect_lambda(bound_signal, self, func, **kw):
        import weakref
        r = weakref.ref(self)
        del self
        num_args = func.__code__.co_argcount - 1
        if num_args < 0:
            raise TypeError('lambda must take at least one argument')

        def slot(*args):
            ctx = r()
            if ctx is not None:
                if len(args) != num_args:
                    args = args[:num_args]
                func(ctx, *args)

        bound_signal.connect(slot, **kw)
    builtins.__dict__['connect_lambda'] = connect_lambda

    if islinux or ismacos or isfreebsd:
        # Name all threads at the OS level created using the threading module, see
        # http://bugs.python.org/issue15500
        import threading

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
                    if isinstance(name, unicode_type):
                        name = name.encode('ascii', 'replace').decode('ascii')
                    plugins['speedup'][0].set_thread_name(name[:15])
            except Exception:
                pass  # Don't care about failure to set name
        threading.Thread.start = new_start
