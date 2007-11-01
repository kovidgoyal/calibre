##    Copyright (C) 2006 Kovid Goyal kovid@kovidgoyal.net
##    This program is free software; you can redistribute it and/or modify
##    it under the terms of the GNU General Public License as published by
##    the Free Software Foundation; either version 2 of the License, or
##    (at your option) any later version.
##
##    This program is distributed in the hope that it will be useful,
##    but WITHOUT ANY WARRANTY; without even the implied warranty of
##    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##    GNU General Public License for more details.
##
##    You should have received a copy of the GNU General Public License along
##    with this program; if not, write to the Free Software Foundation, Inc.,
##    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
''' E-book management software'''
__version__   = "0.4.17"
__docformat__ = "epytext"
__author__    = "Kovid Goyal <kovid@kovidgoyal.net>"
__appname__   = 'libprs500'

import sys, os, logging, mechanize
iswindows = 'win32' in sys.platform.lower()
isosx     = 'darwin' in sys.platform.lower()
islinux   = not(iswindows or isosx) 

class CommandLineError(Exception):
    pass

def setup_cli_handlers(logger, level):
    logger.setLevel(level)
    if level == logging.WARNING:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        handler.setLevel(logging.WARNING)
    elif level == logging.INFO:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter())
        handler.setLevel(logging.INFO)
    elif level == logging.DEBUG:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter('[%(levelname)s] %(filename)s:%(lineno)s: %(message)s'))
    logger.addHandler(handler)


def load_library(name, cdll):
    if iswindows:
        return cdll.LoadLibrary(name)
    if isosx:
        name += '.dylib'
        if hasattr(sys, 'frameworks_dir'):
            return cdll.LoadLibrary(os.path.join(getattr(sys, 'frameworks_dir'), name))
        return cdll.LoadLibrary(name)
    return cdll.LoadLibrary(name+'.so')

def filename_to_utf8(name):
    '''Return C{name} encoded in utf8. Unhandled characters are replaced. '''
    codec = 'cp1252' if iswindows else 'utf8'
    return name.decode(codec, 'replace').encode('utf8')

def extract(path, dir):
    ext = os.path.splitext(path)[1][1:].lower()
    extractor = None
    if ext == 'zip':
        from libprs500.libunzip import extract
        extractor = extract
    elif ext == 'rar':
        from libprs500.libunrar import extract # In case the dll is not found
        extractor = extract
    if not extractor:
        raise Exception('Unknown archive type')
    extractor(path, dir)

def browser():
    opener = mechanize.Browser()
    opener.set_handle_refresh(True)
    opener.set_handle_robots(False)
    opener.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; i686 Linux; en_US; rv:1.8.0.4) Gecko/20060508 Firefox/1.5.0.4')]
    return opener

    