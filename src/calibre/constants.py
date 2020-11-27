#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>
from polyglot.builtins import map, unicode_type, environ_item, hasenv, getenv
import sys, locale, codecs, os, collections

__appname__   = 'calibre'
numeric_version = (5, 6, 0)
__version__   = '.'.join(map(unicode_type, numeric_version))
git_version   = None
__author__    = "Kovid Goyal <kovid@kovidgoyal.net>"

'''
Various run time constants.
'''


_plat = sys.platform.lower()
iswindows = 'win32' in _plat or 'win64' in _plat
ismacos = isosx = 'darwin' in _plat
isnewosx  = ismacos and getattr(sys, 'new_app_bundle', False)
isfreebsd = 'freebsd' in _plat
isnetbsd = 'netbsd' in _plat
isdragonflybsd = 'dragonfly' in _plat
isbsd = isfreebsd or isnetbsd or isdragonflybsd
ishaiku = 'haiku1' in _plat
islinux   = not(iswindows or ismacos or isbsd or ishaiku)
isfrozen  = hasattr(sys, 'frozen')
isunix = ismacos or islinux or ishaiku
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

dark_link_color = '#6cb4ee'
builtin_colors_light = {
    'yellow': '#ffeb6b',
    'green': '#c0ed72',
    'blue': '#add8ff',
    'red': '#ffb0ca',
    'purple': '#d9b2ff',
}
builtin_colors_dark = {
    'yellow': '#c18d18',
    'green': '#306f50',
    'blue': '#265589',
    'red': '#a23e5a',
    'purple': '#505088',
}
builtin_decorations = {
    'wavy': {'text-decoration-style': 'wavy', 'text-decoration-color': 'red', 'text-decoration-line': 'underline'},
    'strikeout': {'text-decoration-line': 'line-through', 'text-decoration-color': 'red'},
}


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
        try:
            candidate = os.path.join(winutil.special_folder_path(winutil.CSIDL_LOCAL_APPDATA), '%s-cache'%__appname__)
        except ValueError:
            return confcache
    elif ismacos:
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


# plugins {{{
plugins_loc = sys.extensions_location
from importlib.machinery import ModuleSpec, EXTENSION_SUFFIXES, ExtensionFileLoader
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


class ExtensionsPackageLoader:

    def __init__(self, calibre_extensions):
        self.calibre_extensions = calibre_extensions

    def is_package(self, fullname=None):
        return True

    def get_resource_reader(self, fullname=None):
        return self

    def get_source(self, fullname=None):
        return ''

    def contents(self):
        return iter(self.calibre_extensions)

    def create_module(self, spec):
        pass

    def exec_module(self, spec):
        pass


class ExtensionsImporter:

    def __init__(self):
        extensions = (
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
        )
        if iswindows:
            extra = ('winutil', 'wpd', 'winfonts', 'winsapi')
        elif ismacos:
            extra = ('usbobserver', 'cocoa', 'libusb', 'libmtp')
        elif isfreebsd or ishaiku or islinux:
            extra = ('libusb', 'libmtp')
        else:
            extra = ()
        self.calibre_extensions = frozenset(extensions + extra)

    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith('calibre_extensions'):
            return
        parts = fullname.split('.')
        if parts[0] != 'calibre_extensions':
            return
        if len(parts) > 2:
            return
        is_package = len(parts) == 1
        extension_name = None if is_package else parts[1]
        path = os.path.join(plugins_loc, '__init__.py')
        if extension_name:
            if extension_name not in self.calibre_extensions:
                return
            for suffix in EXTENSION_SUFFIXES:
                path = os.path.join(plugins_loc, extension_name + suffix)
                if os.path.exists(path):
                    break
            else:
                return
            return ModuleSpec(fullname, ExtensionFileLoader(fullname, path), is_package=is_package, origin=path)
        return ModuleSpec(fullname, ExtensionsPackageLoader(self.calibre_extensions), is_package=is_package, origin=path)


sys.meta_path.insert(0, DeVendor())
sys.meta_path.append(ExtensionsImporter())
if iswindows:
    from calibre_extensions import winutil


class Plugins(collections.Mapping):

    def __iter__(self):
        from importlib.resources import contents
        return contents('calibre_extensions')

    def __len__(self):
        from importlib.resources import contents
        ans = 0
        for x in contents('calibre_extensions'):
            ans += 1
        return ans

    def __contains__(self, name):
        from importlib.resources import contents
        for x in contents('calibre_extensions'):
            if x == name:
                return True
        return False

    def __getitem__(self, name):
        from importlib import import_module
        try:
            return import_module('calibre_extensions.' + name), ''
        except ModuleNotFoundError:
            raise KeyError('No plugin named %r'%name)
        except Exception as err:
            return None, str(err)


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
    try:
        config_dir = winutil.special_folder_path(winutil.CSIDL_APPDATA)
    except ValueError:
        config_dir = None
    if not config_dir or not os.access(config_dir, os.W_OK|os.X_OK):
        config_dir = os.path.expanduser('~')
    config_dir = os.path.join(config_dir, 'calibre')
elif ismacos:
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


is_running_from_develop = False
if getattr(sys, 'frozen', False):
    try:
        from bypy_importer import running_in_develop_mode
    except ImportError:
        pass
    else:
        is_running_from_develop = running_in_develop_mode()

in_develop_mode = getenv('CALIBRE_ENABLE_DEVELOP_MODE') == '1'


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
    return winutil.username()


def get_windows_temp_path():
    return winutil.temp_path()


def get_windows_user_locale_name():
    return winutil.locale_name()


def get_windows_number_formats():
    ans = getattr(get_windows_number_formats, 'ans', None)
    if ans is None:
        d = winutil.localeconv()
        thousands_sep, decimal_point = d['thousands_sep'], d['decimal_point']
        ans = get_windows_number_formats.ans = thousands_sep, decimal_point
    return ans
