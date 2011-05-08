from future_builtins import map

__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__appname__   = u'calibre'
numeric_version = (0, 8, 0)
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
islinux   = not(iswindows or isosx or isfreebsd)
isfrozen  = hasattr(sys, 'frozen')
isunix = isosx or islinux

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
                'pdfreflow',
                'progress_indicator',
                'chmlib',
                'chm_extra',
                'icu',
                'speedup',
            ]
        if iswindows:
            plugins.append('winutil')
        if isosx:
            plugins.append('usbobserver')
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

