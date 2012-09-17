from future_builtins import map

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__appname__   = u'calibre'
numeric_version = (0, 8, 69)
__version__   = u'.'.join(map(unicode, numeric_version))
__author__    = u"Kovid Goyal <kovid@kovidgoyal.net>"

'''
Various run time constants.
'''

import sys, locale, codecs, os, importlib, collections

_tc = None
def terminal_controller():
    global _tc
    if _tc is None:
        from calibre.utils.terminfo import TerminalController
        _tc = TerminalController(sys.stdout)
    return _tc

_plat = sys.platform.lower()
iswindows = 'win32' in _plat or 'win64' in _plat
isosx     = 'darwin' in _plat
isnewosx  = isosx and getattr(sys, 'new_app_bundle', False)
isfreebsd = 'freebsd' in _plat
isnetbsd = 'netbsd' in _plat
isdragonflybsd = 'dragonfly' in _plat
isbsd = isfreebsd or isnetbsd or isdragonflybsd
islinux   = not(iswindows or isosx or isbsd)
isfrozen  = hasattr(sys, 'frozen')
isunix = isosx or islinux
isportable = os.environ.get('CALIBRE_PORTABLE_BUILD', None) is not None
ispy3 = sys.version_info.major > 2
isxp = iswindows and sys.getwindowsversion().major < 6

try:
    preferred_encoding = locale.getpreferredencoding()
    codecs.lookup(preferred_encoding)
except:
    preferred_encoding = 'utf-8'

win32event = importlib.import_module('win32event') if iswindows else None
winerror   = importlib.import_module('winerror') if iswindows else None
win32api   = importlib.import_module('win32api') if iswindows else None
fcntl      = None if iswindows else importlib.import_module('fcntl')

filesystem_encoding = sys.getfilesystemencoding()
if filesystem_encoding is None: filesystem_encoding = 'utf-8'
else:
    try:
        if codecs.lookup(filesystem_encoding).name == 'ascii':
            filesystem_encoding = 'utf-8'
            # On linux, unicode arguments to os file functions are coerced to an ascii
            # bytestring if sys.getfilesystemencoding() == 'ascii', which is
            # just plain dumb. So issue a warning.
            print ('WARNING: You do not have the LANG environment variable set correctly. '
                    'This will cause problems with non-ascii filenames. '
                    'Set it to something like en_US.UTF-8.\n')
    except:
        filesystem_encoding = 'utf-8'


DEBUG = False

def debug():
    global DEBUG
    DEBUG = True

# plugins {{{

class Plugins(collections.Mapping):

    def __init__(self):
        self._plugins = {}
        plugins = [
                'pictureflow',
                'lzx',
                'msdes',
                'magick',
                'podofo',
                'cPalmdoc',
                'fontconfig',
                'progress_indicator',
                'chmlib',
                'chm_extra',
                'icu',
                'speedup',
            ]
        if iswindows:
            plugins.extend(['winutil', 'wpd'])
        if isosx:
            plugins.append('usbobserver')
        if islinux or isosx:
            plugins.append('libusb')
            plugins.append('libmtp')
        self.plugins = frozenset(plugins)

    def load_plugin(self, name):
        if name in self._plugins:
            return
        sys.path.insert(0, sys.extensions_location)
        try:
            p, err = importlib.import_module(name), ''
        except Exception as err:
            p = None
            err = str(err)
        self._plugins[name] = (p, err)
        sys.path.remove(sys.extensions_location)

    def __iter__(self):
        return iter(self.plugins)

    def __len__(self):
        return len(self.plugins)

    def __contains__(self, name):
        return name in self.plugins

    def __getitem__(self, name):
        if name not in self.plugins:
            raise KeyError('No plugin named %r'%name)
        self.load_plugin(name)
        return self._plugins[name]


plugins = None
if plugins is None:
    plugins = Plugins()
# }}}

# config_dir {{{

CONFIG_DIR_MODE = 0700

if os.environ.has_key('CALIBRE_CONFIG_DIRECTORY'):
    config_dir = os.path.abspath(os.environ['CALIBRE_CONFIG_DIRECTORY'])
elif iswindows:
    if plugins['winutil'][0] is None:
        raise Exception(plugins['winutil'][1])
    config_dir = plugins['winutil'][0].special_folder_path(plugins['winutil'][0].CSIDL_APPDATA)
    if not os.access(config_dir, os.W_OK|os.X_OK):
        config_dir = os.path.expanduser('~')
    config_dir = os.path.join(config_dir, 'calibre')
elif isosx:
    config_dir = os.path.expanduser('~/Library/Preferences/calibre')
else:
    bdir = os.path.abspath(os.path.expanduser(os.environ.get('XDG_CONFIG_HOME', '~/.config')))
    config_dir = os.path.join(bdir, 'calibre')
    try:
        os.makedirs(config_dir, mode=CONFIG_DIR_MODE)
    except:
        pass
    if not os.path.exists(config_dir) or \
            not os.access(config_dir, os.W_OK) or not \
            os.access(config_dir, os.X_OK):
        print 'No write acces to', config_dir, 'using a temporary dir instead'
        import tempfile, atexit
        config_dir = tempfile.mkdtemp(prefix='calibre-config-')
        def cleanup_cdir():
            try:
                import shutil
                shutil.rmtree(config_dir)
            except:
                pass
        atexit.register(cleanup_cdir)
# }}}

def get_version():
    '''Return version string that indicates if we are running in a dev env'''
    dv = os.environ.get('CALIBRE_DEVELOP_FROM', None)
    v = __version__
    if getattr(sys, 'frozen', False) and dv and os.path.abspath(dv) in sys.path:
        v += '*'
    return v

def get_portable_base():
    'Return path to the directory that contains calibre-portable.exe or None'
    if isportable:
        return os.path.dirname(os.path.dirname(os.environ['CALIBRE_PORTABLE_BUILD']))

def get_unicode_windows_env_var(name):
    import ctypes
    name = unicode(name)
    n = ctypes.windll.kernel32.GetEnvironmentVariableW(name, None, 0)
    if n == 0:
        return None
    buf = ctypes.create_unicode_buffer(u'\0'*n)
    ctypes.windll.kernel32.GetEnvironmentVariableW(name, buf, n)
    return buf.value

def get_windows_username():
    '''
    Return the user name of the currently loggen in user as a unicode string.
    Note that usernames on windows are case insensitive, the case of the value
    returned depends on what the user typed into the login box at login time.
    '''
    import ctypes
    try:
        advapi32 = ctypes.windll.advapi32
        GetUserName = getattr(advapi32, u'GetUserNameW')
    except AttributeError:
        pass
    else:
        buf = ctypes.create_unicode_buffer(257)
        n = ctypes.c_int(257)
        if GetUserName(buf, ctypes.byref(n)):
            return buf.value

    return get_unicode_windows_env_var(u'USERNAME')

def get_windows_temp_path():
    import ctypes
    n = ctypes.windll.kernel32.GetTempPathW(0, None)
    if n == 0:
        return None
    buf = ctypes.create_unicode_buffer(u'\0'*n)
    ctypes.windll.kernel32.GetTempPathW(n, buf)
    ans = buf.value
    return ans if ans else None

def get_windows_user_locale_name():
    import ctypes
    k32 = ctypes.windll.kernel32
    n = 200
    buf = ctypes.create_unicode_buffer(u'\0'*n)
    n = k32.GetUserDefaultLocaleName(buf, n)
    if n == 0:
        return None
    return u'_'.join(buf.value.split(u'-')[:2])

