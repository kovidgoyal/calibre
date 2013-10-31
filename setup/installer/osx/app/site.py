"""
Append module search paths for third-party packages to sys.path.

This is stripped down and customized for use in py2app applications
"""

import sys
import os

def makepath(*paths):
    dir = os.path.abspath(os.path.join(*paths))
    return dir, os.path.normcase(dir)

def abs__file__():
    """Set all module __file__ attribute to an absolute path"""
    for m in sys.modules.values():
        if hasattr(m, '__loader__'):
            continue   # don't mess with a PEP 302-supplied __file__
        try:
            m.__file__ = os.path.abspath(m.__file__)
        except AttributeError:
            continue

# This ensures that the initial path provided by the interpreter contains
# only absolute pathnames, even if we're running from the build directory.
L = []
_dirs_in_sys_path = {}
dir = dircase = None  # sys.path may be empty at this point
for dir in sys.path:
    # Filter out duplicate paths (on case-insensitive file systems also
    # if they only differ in case); turn relative paths into absolute
    # paths.
    dir, dircase = makepath(dir)
    if not dircase in _dirs_in_sys_path:
        L.append(dir)
        _dirs_in_sys_path[dircase] = 1
sys.path[:] = L
del dir, dircase, L
_dirs_in_sys_path = None

def _init_pathinfo():
    global _dirs_in_sys_path
    _dirs_in_sys_path = d = {}
    for dir in sys.path:
        if dir and not os.path.isdir(dir):
            continue
        dir, dircase = makepath(dir)
        d[dircase] = 1

def addsitedir(sitedir):
    global _dirs_in_sys_path
    if _dirs_in_sys_path is None:
        _init_pathinfo()
        reset = 1
    else:
        reset = 0
    sitedir, sitedircase = makepath(sitedir)
    if not sitedircase in _dirs_in_sys_path:
        sys.path.append(sitedir)        # Add path component
    try:
        names = os.listdir(sitedir)
    except os.error:
        return
    names.sort()
    for name in names:
        if name[-4:] == os.extsep + "pth":
            addpackage(sitedir, name)
    if reset:
        _dirs_in_sys_path = None

def addpackage(sitedir, name):
    global _dirs_in_sys_path
    if _dirs_in_sys_path is None:
        _init_pathinfo()
        reset = 1
    else:
        reset = 0
    fullname = os.path.join(sitedir, name)
    try:
        f = open(fullname)
    except IOError:
        return
    while True:
        dir = f.readline()
        if not dir:
            break
        if dir[0] == '#':
            continue
        if dir.startswith("import"):
            exec dir
            continue
        if dir[-1] == '\n':
            dir = dir[:-1]
        dir, dircase = makepath(sitedir, dir)
        if not dircase in _dirs_in_sys_path and os.path.exists(dir):
            sys.path.append(dir)
            _dirs_in_sys_path[dircase] = 1
    if reset:
        _dirs_in_sys_path = None


# Remove sys.setdefaultencoding() so that users cannot change the
# encoding after initialization.  The test for presence is needed when
# this module is run as a script, because this code is executed twice.
#
if hasattr(sys, "setdefaultencoding"):
    sys.setdefaultencoding('utf-8')
    del sys.setdefaultencoding

def run_entry_point():
    bname, mod, func = sys.calibre_basename, sys.calibre_module, sys.calibre_function
    sys.argv[0] = bname
    pmod = __import__(mod, fromlist=[1], level=0)
    return getattr(pmod, func)()

def add_calibre_vars(base):
    sys.frameworks_dir = os.path.join(os.path.dirname(base), 'Frameworks')
    sys.resources_location = os.path.abspath(os.path.join(base, 'resources'))
    sys.extensions_location = os.path.join(sys.frameworks_dir, 'plugins')
    sys.binaries_path = os.path.join(os.path.dirname(base), 'MacOS')
    sys.console_binaries_path = os.path.join(os.path.dirname(base),
        'console.app', 'Contents', 'MacOS')

    dv = os.environ.get('CALIBRE_DEVELOP_FROM', None)
    if dv and os.path.exists(dv):
        sys.path.insert(0, os.path.abspath(dv))

def setup_asl():
    # On Mac OS X 10.8 or later the contents of stdout and stderr
    # do not end up in Console.app
    # This function detects if "asl_log_descriptor" is available
    # (introduced in 10.8), and if it is configures ASL to redirect
    # all writes to stdout/stderr to Console.app
    import ctypes
    try:
        syslib = ctypes.CDLL("/usr/lib/libSystem.dylib")
    except EnvironmentError:
        import ctypes.util
        syslib = ctypes.CDLL(ctypes.util.find_library('System'))

    asl_log_descriptor_proto = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_uint32)
    try:
        asl_log_descriptor = asl_log_descriptor_proto(('asl_log_descriptor', syslib), ((1, 'asl'), (1, 'msg'), (1, 'level'), (1, 'descriptor'), (1, 'fd_type')))
    except AttributeError:
        # OS X < 10.8 no need to redirect
        return
    asl_open_proto = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint32)
    asl_open = asl_open_proto(('asl_open', syslib), ((1, "ident"), (1, "facility"), (1, 'opts')))
    asl_new_proto = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_uint32)
    asl_new = asl_new_proto(('asl_new', syslib), ((1, "type"),))
    asl_set_proto = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p)
    asl_set = asl_set_proto(('asl_set', syslib), ((1, "msg"), (1, "key"), (1, "value")))

    CONSOLE = b'com.apple.console'
    # Taken from asl.h
    ASL_OPT_NO_DELAY = 2
    ASL_TYPE_MSG = 0
    ASL_KEY_FACILITY = b'Facility'
    ASL_KEY_LEVEL = b'Level'
    ASL_KEY_READ_UID = b'ReadUID'
    ASL_STRING_NOTICE = b'Notice'
    ASL_LEVEL_NOTICE = 4
    ASL_LOG_DESCRIPTOR_WRITE = 2

    cl = asl_open(ident=getattr(sys, 'calibre_basename', b'calibre'), facility=CONSOLE, opts=ASL_OPT_NO_DELAY)
    if cl is None:
        return

    # Create an ASL template message for the STDOUT/STDERR redirection.
    msg = asl_new(ASL_TYPE_MSG)
    if msg is None:
        return
    if asl_set(msg, ASL_KEY_FACILITY, CONSOLE) != 0:
        return
    if asl_set(msg, ASL_KEY_LEVEL, ASL_STRING_NOTICE) != 0:
        return
    if asl_set(msg, ASL_KEY_READ_UID, bytes('%d' % os.getuid())) != 0:
        return
    # Redirect the STDOUT/STDERR file descriptors to ASL
    if asl_log_descriptor(cl, msg, ASL_LEVEL_NOTICE, sys.stdout.fileno(), ASL_LOG_DESCRIPTOR_WRITE) != 0:
        return
    if asl_log_descriptor(cl, msg, ASL_LEVEL_NOTICE, sys.stderr.fileno(), ASL_LOG_DESCRIPTOR_WRITE) != 0:
        return

def main():
    global __file__
    base = sys.resourcepath

    sys.frozen = 'macosx_app'
    sys.new_app_bundle = True
    abs__file__()

    add_calibre_vars(base)
    addsitedir(sys.site_packages)

    launched_by_launch_services = False

    for arg in tuple(sys.argv[1:]):
        if arg.startswith('-psn_'):
            sys.argv.remove(arg)
            launched_by_launch_services = True
    if launched_by_launch_services:
        try:
            setup_asl()
        except:
            pass  # Failure to log to Console.app is not critical

    return run_entry_point()
