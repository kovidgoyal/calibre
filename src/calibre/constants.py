#!/usr/bin/env python2
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

from future_builtins import map
import sys, locale, codecs, os, importlib, collections

__appname__   = u'calibre'
numeric_version = (3, 18, 0)
__version__   = u'.'.join(map(unicode, numeric_version))
__author__    = u"Kovid Goyal <kovid@kovidgoyal.net>"

'''
Various run time constants.
'''


_plat = sys.platform.lower()
iswindows = 'win32' in _plat or 'win64' in _plat
isosx     = 'darwin' in _plat
isnewosx  = isosx and getattr(sys, 'new_app_bundle', False)
isfreebsd = 'freebsd' in _plat
isnetbsd = 'netbsd' in _plat
isdragonflybsd = 'dragonfly' in _plat
isbsd = isfreebsd or isnetbsd or isdragonflybsd
ishaiku = 'haiku1' in _plat
islinux   = not(iswindows or isosx or isbsd or ishaiku)
isfrozen  = hasattr(sys, 'frozen')
isunix = isosx or islinux or ishaiku
isportable = os.environ.get('CALIBRE_PORTABLE_BUILD', None) is not None
ispy3 = sys.version_info.major > 2
isxp = isoldvista = False
if iswindows:
    wver = sys.getwindowsversion()
    isxp = wver.major < 6
    isoldvista = wver.build < 6002
is64bit = sys.maxsize > (1 << 32)
isworker = 'CALIBRE_WORKER' in os.environ or 'CALIBRE_SIMPLE_WORKER' in os.environ
if isworker:
    os.environ.pop('CALIBRE_FORCE_ANSI', None)
FAKE_PROTOCOL, FAKE_HOST = 'https', 'calibre-internal.invalid'
VIEWER_APP_UID = u'com.calibre-ebook.viewer'
EDITOR_APP_UID = u'com.calibre-ebook.edit-book'
MAIN_APP_UID = u'com.calibre-ebook.main-gui'
try:
    preferred_encoding = locale.getpreferredencoding()
    codecs.lookup(preferred_encoding)
except:
    preferred_encoding = 'utf-8'

win32event = importlib.import_module('win32event') if iswindows else None
winerror   = importlib.import_module('winerror') if iswindows else None
win32api   = importlib.import_module('win32api') if iswindows else None
fcntl      = None if iswindows else importlib.import_module('fcntl')

_osx_ver = None


def get_osx_version():
    global _osx_ver
    if _osx_ver is None:
        import platform
        from collections import namedtuple
        OSX = namedtuple('OSX', 'major minor tertiary')
        try:
            ver = platform.mac_ver()[0].split('.')
            if len(ver) == 2:
                ver.append(0)
            _osx_ver = OSX(*(map(int, ver)))
        except:
            _osx_ver = OSX(0, 0, 0)
    return _osx_ver


filesystem_encoding = sys.getfilesystemencoding()
if filesystem_encoding is None:
    filesystem_encoding = 'utf-8'
else:
    try:
        if codecs.lookup(filesystem_encoding).name == 'ascii':
            filesystem_encoding = 'utf-8'
            # On linux, unicode arguments to os file functions are coerced to an ascii
            # bytestring if sys.getfilesystemencoding() == 'ascii', which is
            # just plain dumb. This is fixed by the icu.py module which, when
            # imported changes ascii to utf-8
    except:
        filesystem_encoding = 'utf-8'


DEBUG = b'CALIBRE_DEBUG' in os.environ


def debug():
    global DEBUG
    DEBUG = True


def _get_cache_dir():
    import errno
    confcache = os.path.join(config_dir, u'caches')
    try:
        os.makedirs(confcache)
    except EnvironmentError as err:
        if err.errno != errno.EEXIST:
            raise
    if isportable:
        return confcache
    if 'CALIBRE_CACHE_DIRECTORY' in os.environ:
        if iswindows:
            ans = get_unicode_windows_env_var(u'CALIBRE_CACHE_DIRECTORY')
        else:
            ans = os.path.abspath(os.environ['CALIBRE_CACHE_DIRECTORY'])
            if isinstance(ans, bytes):
                ans = ans.decode(filesystem_encoding)
        try:
            os.makedirs(ans)
            return ans
        except EnvironmentError as err:
            if err.errno == errno.EEXIST:
                return ans

    if iswindows:
        w = plugins['winutil'][0]
        try:
            candidate = os.path.join(w.special_folder_path(w.CSIDL_LOCAL_APPDATA), u'%s-cache'%__appname__)
        except ValueError:
            return confcache
    elif isosx:
        candidate = os.path.join(os.path.expanduser(u'~/Library/Caches'), __appname__)
    else:
        candidate = os.environ.get('XDG_CACHE_HOME', u'~/.cache')
        candidate = os.path.join(os.path.expanduser(candidate),
                                    __appname__)
        if isinstance(candidate, bytes):
            try:
                candidate = candidate.decode(filesystem_encoding)
            except ValueError:
                candidate = confcache
    try:
        os.makedirs(candidate)
    except EnvironmentError as err:
        if err.errno != errno.EEXIST:
            candidate = confcache
    return candidate


def cache_dir():
    ans = getattr(cache_dir, 'ans', None)
    if ans is None:
        ans = cache_dir.ans = _get_cache_dir()
    return ans

# plugins {{{


class Plugins(collections.Mapping):

    def __init__(self):
        self._plugins = {}
        plugins = [
                'pictureflow',
                'lzx',
                'msdes',
                'podofo',
                'cPalmdoc',
                'progress_indicator',
                'chmlib',
                'chm_extra',
                'icu',
                'speedup',
                'monotonic',
                'zlib2',
                'html',
                'freetype',
                'imageops',
                'qt_hack',
                'hunspell',
                '_patiencediff_c',
                'bzzdec',
                'matcher',
                'tokenizer',
                'certgen',
                'lzma_binding',
            ]
        if iswindows:
            plugins.extend(['winutil', 'wpd', 'winfonts'])
        if isosx:
            plugins.append('usbobserver')
        if isfreebsd or ishaiku or islinux or isosx:
            plugins.append('libusb')
            plugins.append('libmtp')
        self.plugins = frozenset(plugins)

    def load_plugin(self, name):
        if name in self._plugins:
            return
        sys.path.insert(0, sys.extensions_location)
        try:
            del sys.modules[name]
        except KeyError:
            pass
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

if 'CALIBRE_CONFIG_DIRECTORY' in os.environ:
    config_dir = os.path.abspath(os.environ['CALIBRE_CONFIG_DIRECTORY'])
elif iswindows:
    if plugins['winutil'][0] is None:
        raise Exception(plugins['winutil'][1])
    try:
        config_dir = plugins['winutil'][0].special_folder_path(plugins['winutil'][0].CSIDL_APPDATA)
    except ValueError:
        config_dir = None
    if not config_dir or not os.access(config_dir, os.W_OK|os.X_OK):
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


dv = os.environ.get('CALIBRE_DEVELOP_FROM')
is_running_from_develop = bool(getattr(sys, 'frozen', False) and dv and os.path.abspath(dv) in sys.path)
del dv


def get_version():
    '''Return version string for display to user '''
    v = __version__
    if numeric_version[-1] == 0:
        v = v[:-2]
    if is_running_from_develop:
        v += '*'
    if iswindows and is64bit:
        v += ' [64bit]'

    return v


def get_portable_base():
    'Return path to the directory that contains calibre-portable.exe or None'
    if isportable:
        return os.path.dirname(os.path.dirname(get_unicode_windows_env_var(u'CALIBRE_PORTABLE_BUILD')))


def get_unicode_windows_env_var(name):
    getenv = plugins['winutil'][0].getenv
    return getenv(unicode(name))


def get_windows_username():
    '''
    Return the user name of the currently logged in user as a unicode string.
    Note that usernames on windows are case insensitive, the case of the value
    returned depends on what the user typed into the login box at login time.
    '''
    username = plugins['winutil'][0].username
    return username()


def get_windows_temp_path():
    temp_path = plugins['winutil'][0].temp_path
    return temp_path()


def get_windows_user_locale_name():
    locale_name = plugins['winutil'][0].locale_name
    return locale_name()


def get_windows_number_formats():
    ans = getattr(get_windows_number_formats, 'ans', None)
    if ans is None:
        localeconv = plugins['winutil'][0].localeconv
        d = localeconv()
        thousands_sep, decimal_point = d['thousands_sep'], d['decimal_point']
        ans = get_windows_number_formats.ans = thousands_sep, decimal_point
    return ans
