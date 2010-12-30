__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__appname__   = 'calibre'
__version__   = '0.7.33'
__author__    = "Kovid Goyal <kovid@kovidgoyal.net>"

import re
_ver = __version__.split('.')
_ver = [int(re.search(r'(\d+)', x).group(1)) for x in _ver]
numeric_version = tuple(_ver)

'''
Various run time constants.
'''

import sys, locale, codecs, os
from calibre.utils.terminfo import TerminalController

terminal_controller = TerminalController(sys.stdout)

iswindows = 'win32' in sys.platform.lower() or 'win64' in sys.platform.lower()
isosx     = 'darwin' in sys.platform.lower()
isnewosx = isosx and getattr(sys, 'new_app_bundle', False)
isfreebsd = 'freebsd' in sys.platform.lower()
islinux   = not(iswindows or isosx or isfreebsd)
isfrozen  = hasattr(sys, 'frozen')
isunix = isosx or islinux

try:
    preferred_encoding = locale.getpreferredencoding()
    codecs.lookup(preferred_encoding)
except:
    preferred_encoding = 'utf-8'

win32event = __import__('win32event') if iswindows else None
winerror   = __import__('winerror') if iswindows else None
win32api   = __import__('win32api') if iswindows else None
fcntl      = None if iswindows else __import__('fcntl')

filesystem_encoding = sys.getfilesystemencoding()
if filesystem_encoding is None: filesystem_encoding = 'utf-8'

DEBUG = False

def debug():
    global DEBUG
    DEBUG = True

# plugins {{{
plugins = None
if plugins is None:
    # Load plugins
    def load_plugins():
        plugins = {}
        plugin_path = sys.extensions_location
        sys.path.insert(0, plugin_path)

        for plugin in [
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
            ] + \
                    (['winutil'] if iswindows else []) + \
                    (['usbobserver'] if isosx else []):
            try:
                p, err = __import__(plugin), ''
            except Exception, err:
                p = None
                err = str(err)
            plugins[plugin] = (p, err)
        sys.path.remove(plugin_path)
        return plugins

    plugins = load_plugins()
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

