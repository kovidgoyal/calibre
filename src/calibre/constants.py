__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__appname__   = 'calibre'
__version__   = '0.6.11'
__author__    = "Kovid Goyal <kovid@kovidgoyal.net>"

import re
_ver = __version__.split('.')
_ver = [int(re.search(r'(\d+)', x).group(1)) for x in _ver]
numeric_version = tuple(_ver)

'''
Various run time constants.
'''

import sys, locale, codecs
from calibre.utils.terminfo import TerminalController

terminal_controller = TerminalController(sys.stdout)

iswindows = 'win32' in sys.platform.lower() or 'win64' in sys.platform.lower()
isosx     = 'darwin' in sys.platform.lower()
isnewosx = isosx and getattr(sys, 'new_app_bundle', False)
islinux   = not(iswindows or isosx)
isfrozen  = hasattr(sys, 'frozen')

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

################################################################################
plugins = None
if plugins is None:
    # Load plugins
    def load_plugins():
        plugins = {}
        plugin_path = sys.extensions_location
        sys.path.insert(0, plugin_path)

        for plugin in ['pictureflow', 'lzx', 'msdes', 'podofo', 'cPalmdoc',
            'fontconfig', 'calibre_poppler'] + \
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
