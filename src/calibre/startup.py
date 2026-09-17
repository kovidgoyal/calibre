# License: GPLv3 Copyright: 2008, Kovid Goyal kovid@kovidgoyal.net

"""
Perform various initialization tasks.
"""

import builtins
import locale
import os
import sys
from collections.abc import Sequence
from typing import Any

# Default translation is NOOP
builtins.__dict__['_'] = lambda s: s

# For strings which belong in the translation tables, but which shouldn't be
# immediately translated to the environment language
builtins.__dict__['__'] = lambda s: s

# For backwards compat with some third party plugins
builtins.__dict__['dynamic_property'] = lambda func: func(None)

from calibre.constants import DEBUG, get_portable_base, isfreebsd, islinux, ismacos, iswindows


def get_debug_executable(headless=False, exe_name='calibre-debug'):
    exe_name = exe_name + ('.exe' if iswindows else '')
    if hasattr(sys, 'frameworks_dir'):
        base = os.path.dirname(sys.frameworks_dir)
        if headless:
            from calibre.utils.ipc.launch import headless_exe_path

            return [headless_exe_path(exe_name)]
        return [os.path.join(base, 'MacOS', exe_name)]
    if getattr(sys, 'run_local', None):
        return [sys.run_local, exe_name]  # type: ignore
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


def get_calibre_gui_command(args: Sequence[str] = ()) -> list[str]:
    """The command needed to start the main calibre GUI, passing it args. Note
    that when a calibre GUI is already running, starting another one simply
    causes the running one to be given args and raised, see
    calibre.gui2.main.communicate()."""
    if ismacos and hasattr(sys, 'frameworks_dir'):
        bundle = os.path.dirname(os.path.dirname(sys.frameworks_dir))
        # -n is needed as, without it, open() simply activates the already
        # running calibre, throwing away args. The extra instance it starts
        # hands args to the running one over a socket and exits immediately.
        return ['open', '-n', '-a', bundle, '--args'] + list(args)
    if iswindows and (base := get_portable_base()):
        # Go via the portable launcher rather than the executable it launches,
        # so that the settings and library of the portable install are used
        # even if the environment variables it sets have been lost.
        launcher = os.path.join(base, 'calibre-portable.exe')
        if os.path.exists(launcher):
            return [launcher] + list(args)
    cmd = get_debug_executable(exe_name='calibre')
    if islinux:
        # Run in a session of its own, so that the calibre GUI is unaffected by
        # whatever happens to the process that started it.
        cmd.append('--detach')
    return cmd + list(args)


def launch_calibre_gui(args: Sequence[str] = ()) -> None:
    "Start the main calibre GUI in a new process, passing it args. Raises an exception if the process cannot be started."
    import subprocess

    cmd = get_calibre_gui_command(args)
    if cmd[0] == 'open':
        from calibre.constants import sanitize_env_vars

        # open() is a program of the system, it must not be given the library
        # paths of the calibre bundle. It does not pass on our environment to
        # the calibre GUI it launches, anyway.
        with sanitize_env_vars():
            subprocess.Popen(cmd, close_fds=True)
        return
    # The calibre GUI is not a worker process and must not inherit the
    # temporary folder or other environment of one, in case we are.
    env = {k: v for k, v in os.environ.items() if not k.startswith('CALIBRE_WORKER')}
    creationflags = 0
    if iswindows:
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(cmd, env=env, close_fds=True, creationflags=creationflags)


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


_calibre_initialized = False


def initialize_calibre():
    global _calibre_initialized
    if _calibre_initialized:
        return
    _calibre_initialized = True
    # Ensure that all temp files/dirs are created under a calibre tmp dir
    from calibre.ptempfile import fix_tempfile_module

    fix_tempfile_module()

    # Ensure that the max number of open files is at least 1024
    if iswindows:
        # See https://msdn.microsoft.com/en-us/library/6e3b887c.aspx
        from calibre_extensions import winutil

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

    def get_executable() -> list[str]:
        return get_debug_executable(headless=True, exe_name='calibre-parallel')

    def get_command_line(**kwds: Any) -> list[str]:
        prog = ', '.join('{}={!r}'.format(*item) for item in kwds.items())
        prog = f'from multiprocessing.spawn import spawn_main; spawn_main({prog})'
        return get_executable() + ['__multiprocessing__', prog]

    spawn.get_command_line = get_command_line  # type: ignore
    spawn._fixup_main_from_path = lambda *a: None  # type: ignore
    if iswindows:
        # On windows multiprocessing does not run the result of
        # get_command_line directly, see popen_spawn_win32.py
        spawn.set_executable(get_executable()[-1])
    orig_spawn_passfds = util.spawnv_passfds
    orig_remove_temp_dir = util._remove_temp_dir  # type: ignore

    def safe_rmtree(rmtree):
        def r(tdir, *a, **kw):
            if tdir and os.path.exists(tdir):
                rmtree(tdir, *a, **kw)

        return r

    def safe_remove_temp_dir(rmtree, tdir):
        orig_remove_temp_dir(safe_rmtree(rmtree), tdir)

    def wrapped_orig_spawn_fds(args, passfds):
        # as of python 3.11 util.spawnv_passfds expects bytes args
        args = [x.encode('utf-8') if isinstance(x, str) else x for x in args]
        return orig_spawn_passfds(args[0], args, passfds)

    def spawnv_passfds(path, args, passfds):
        try:
            idx = args.index('-c')
        except ValueError:
            return wrapped_orig_spawn_fds(args, passfds)
        patched_args = get_executable() + ['__multiprocessing__'] + args[idx + 1 :]
        return wrapped_orig_spawn_fds(patched_args, passfds)

    util.spawnv_passfds = spawnv_passfds  # type: ignore
    util._remove_temp_dir = safe_remove_temp_dir  # type: ignore

    #
    # Setup resources
    from calibre.utils import resources

    resources

    #
    # Setup translations
    from calibre.utils.localization import getlangcode_from_envvars, set_translators

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
    except Exception:
        try:
            dl = getlangcode_from_envvars()
            if dl:
                locale.setlocale(locale.LC_ALL, dl)
        except Exception:
            pass

    builtins.__dict__['lopen'] = open  # legacy compatibility
    from calibre.utils.icu import lower as icu_lower
    from calibre.utils.icu import title_case
    from calibre.utils.icu import upper as icu_upper

    builtins.__dict__['icu_lower'] = icu_lower
    builtins.__dict__['icu_upper'] = icu_upper
    builtins.__dict__['icu_title'] = title_case

    builtins.__dict__['connect_lambda'] = connect_lambda

    if sys.version_info[:2] < (3, 14) and (islinux or ismacos or isfreebsd):
        # Name all threads at the OS level created using the threading module, see
        # https://github.com/python/cpython/issues/59705
        import threading

        from calibre_extensions import speedup

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
                    if isinstance(name, str):
                        name = name.encode('ascii', 'replace').decode('ascii')
                    speedup.set_thread_name(name[:15])
            except Exception:
                pass  # Don't care about failure to set name

        threading.Thread.start = new_start
