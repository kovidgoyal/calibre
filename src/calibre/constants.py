#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>
from polyglot.builtins import map, unicode_type, environ_item, hasenv, getenv, as_unicode, native_string_type
import sys, locale, codecs, os, importlib, collections

__appname__   = 'calibre'
numeric_version = (4, 99, 3)
__version__   = '.'.join(map(unicode_type, numeric_version))
git_version   = None
__author__    = "Kovid Goyal <kovid@kovidgoyal.net>"

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
isportable = hasenv('CALIBRE_PORTABLE_BUILD')
ispy3 = sys.version_info.major > 2
isxp = isoldvista = False
if iswindows:
    wver = sys.getwindowsversion()
    isxp = wver.major < 6
    isoldvista = wver.build < 6002
is64bit = sys.maxsize > (1 << 32)
isworker = hasenv('CALIBRE_WORKER') or hasenv('CALIBRE_SIMPLE_WORKER')
if isworker:
    os.environ.pop(environ_item('CALIBRE_FORCE_ANSI'), None)
FAKE_PROTOCOL, FAKE_HOST = 'clbr', 'internal.invalid'
VIEWER_APP_UID = 'com.calibre-ebook.viewer'
EDITOR_APP_UID = 'com.calibre-ebook.edit-book'
MAIN_APP_UID = 'com.calibre-ebook.main-gui'
STORE_DIALOG_APP_UID = 'com.calibre-ebook.store-dialog'
TOC_DIALOG_APP_UID = 'com.calibre-ebook.toc-editor'
try:
    preferred_encoding = locale.getpreferredencoding()
    codecs.lookup(preferred_encoding)
except:
    preferred_encoding = 'utf-8'

win32event = importlib.import_module('win32event') if iswindows else None
winerror   = importlib.import_module('winerror') if iswindows else None
win32api   = importlib.import_module('win32api') if iswindows else None
fcntl      = None if iswindows else importlib.import_module('fcntl')
dark_link_color = '#6cb4ee'

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
            _osx_ver = OSX(*map(int, ver))  # no2to3
        except Exception:
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
    except Exception:
        filesystem_encoding = 'utf-8'


DEBUG = hasenv('CALIBRE_DEBUG')


def debug():
    global DEBUG
    DEBUG = True


def _get_cache_dir():
    import errno
    confcache = os.path.join(config_dir, 'caches')
    try:
        os.makedirs(confcache)
    except EnvironmentError as err:
        if err.errno != errno.EEXIST:
            raise
    if isportable:
        return confcache
    ccd = getenv('CALIBRE_CACHE_DIRECTORY')
    if ccd is not None:
        ans = os.path.abspath(ccd)
        try:
            os.makedirs(ans)
            return ans
        except EnvironmentError as err:
            if err.errno == errno.EEXIST:
                return ans

    if iswindows:
        w = plugins['winutil'][0]
        try:
            candidate = os.path.join(w.special_folder_path(w.CSIDL_LOCAL_APPDATA), '%s-cache'%__appname__)
        except ValueError:
            return confcache
    elif isosx:
        candidate = os.path.join(os.path.expanduser('~/Library/Caches'), __appname__)
    else:
        candidate = getenv('XDG_CACHE_HOME', '~/.cache')
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
        ans = cache_dir.ans = os.path.realpath(_get_cache_dir())
    return ans


plugins_loc = sys.extensions_location


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
                'icu',
                'speedup',
                'html_as_json',
                'unicode_names',
                'html_syntax_highlighter',
                'hyphen',
                'freetype',
                'imageops',
                'hunspell',
                '_patiencediff_c',
                'bzzdec',
                'matcher',
                'tokenizer',
                'certgen',
            ]
        if iswindows:
            plugins.extend(['winutil', 'wpd', 'winfonts'])
        if isosx:
            plugins.append('usbobserver')
            plugins.append('cocoa')
        if isfreebsd or ishaiku or islinux or isosx:
            plugins.append('libusb')
            plugins.append('libmtp')
        self.plugins = frozenset(plugins)

    def load_plugin(self, name):
        if name in self._plugins:
            return
        sys.path.insert(0, plugins_loc)
        try:
            del sys.modules[name]
        except KeyError:
            pass
        plugin_err = ''
        try:
            p = importlib.import_module(name)
        except Exception as err:
            p = None
            try:
                plugin_err = unicode_type(err)
            except Exception:
                plugin_err = as_unicode(native_string_type(err), encoding=preferred_encoding, errors='replace')
        self._plugins[name] = p, plugin_err
        sys.path.remove(plugins_loc)

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

CONFIG_DIR_MODE = 0o700

cconfd = getenv('CALIBRE_CONFIG_DIRECTORY')
if cconfd is not None:
    config_dir = os.path.abspath(cconfd)
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
    bdir = os.path.abspath(os.path.expanduser(getenv('XDG_CONFIG_HOME', '~/.config')))
    config_dir = os.path.join(bdir, 'calibre')
    try:
        os.makedirs(config_dir, mode=CONFIG_DIR_MODE)
    except:
        pass
    if not os.path.exists(config_dir) or \
            not os.access(config_dir, os.W_OK) or not \
            os.access(config_dir, os.X_OK):
        print('No write acces to', config_dir, 'using a temporary dir instead')
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


dv = getenv('CALIBRE_DEVELOP_FROM')
is_running_from_develop = bool(getattr(sys, 'frozen', False) and dv and os.path.abspath(dv) in sys.path)
del dv


def get_version():
    '''Return version string for display to user '''
    if git_version is not None:
        v = git_version
    else:
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
        return os.path.dirname(os.path.dirname(getenv('CALIBRE_PORTABLE_BUILD')))


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
