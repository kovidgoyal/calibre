__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'
__appname__   = 'calibre'
__version__   = '0.4.84b5'
__author__    = "Kovid Goyal <kovid@kovidgoyal.net>"
'''
Various run time constants.
'''

import sys, locale, codecs
from calibre.utils.terminfo import TerminalController

terminal_controller = TerminalController(sys.stdout)

iswindows = 'win32' in sys.platform.lower() or 'win64' in sys.platform.lower()
isosx     = 'darwin' in sys.platform.lower()
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
