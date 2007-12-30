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
__version__   = "0.4.31"
__docformat__ = "epytext"
__author__    = "Kovid Goyal <kovid@kovidgoyal.net>"
__appname__   = 'libprs500'

import sys, os, logging, mechanize, locale, cStringIO, re
from gettext import GNUTranslations
from math import floor

from ttfquery import findsystem, describe

from libprs500.translations.msgfmt import make

iswindows = 'win32' in sys.platform.lower()
isosx     = 'darwin' in sys.platform.lower()
islinux   = not(iswindows or isosx) 

def osx_version():
    if isosx:
        import platform
        src = platform.mac_ver()[0]
        m = re.match(r'(\d+)\.(\d+)\.(\d+)', src)
        if m:
            return int(m.group(1)), int(m.group(2)), int(m.group(3))
        

# Default translation is NOOP
import __builtin__
__builtin__.__dict__['_'] = lambda s: s

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
    if isinstance(name, unicode):
        return name.encode('utf8')
    codec = 'cp1252' if iswindows else 'utf8'
    return name.decode(codec, 'replace').encode('utf8')

def extract(path, dir):
    ext = os.path.splitext(path)[1][1:].lower()
    extractor = None
    if ext == 'zip':
        from libprs500.libunzip import extract as zipextract
        extractor = zipextract
    elif ext == 'rar':
        from libprs500.libunrar import extract as rarextract
        extractor = rarextract
    if extractor is None:
        raise Exception('Unknown archive type')
    extractor(path, dir)

def browser():
    opener = mechanize.Browser()
    opener.set_handle_refresh(True)
    opener.set_handle_robots(False)
    opener.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; i686 Linux; en_US; rv:1.8.0.4) Gecko/20060508 Firefox/1.5.0.4')]
    return opener

def fit_image(width, height, pwidth, pheight):
    '''
    Fit image in box of width pwidth and height pheight. 
    @param width: Width of image
    @param height: Height of image
    @param pwidth: Width of box 
    @param pheight: Height of box
    @return: scaled, new_width, new_height. scaled is True iff new_widdth and/or new_height is different from width or height.  
    '''
    scaled = height > pheight or width > pwidth
    if height > pheight:
        corrf = pheight/float(height)
        width, height = floor(corrf*width), pheight                        
    if width > pwidth:
        corrf = pwidth/float(width)
        width, height = pwidth, floor(corrf*height)
    if height > pheight:
        corrf = pheight/float(height)
        width, height = floor(corrf*width), pheight
                            
    return scaled, int(width), int(height)      

def set_translator():
    # To test different translations invoke as
    # LC_ALL=de_DE.utf8 program
    from libprs500.translations.data import translations
    lang = locale.getdefaultlocale()[0]
    if lang is None and os.environ.has_key('LANG'): # Needed for OS X
        try:
            lang = os.environ['LANG'][:2]
        except:
            pass 
    if lang:
        lang = lang[:2]
        buf = None
        if os.access(lang+'.po', os.R_OK):
            buf = cStringIO.StringIO()
            make(lang+'.po', buf)
            buf = cStringIO.StringIO(buf.getvalue())
        elif translations.has_key(lang):
            buf = cStringIO.StringIO(translations[lang])
        if buf is not None:
            t = GNUTranslations(buf)
            t.install(unicode=True)
        
set_translator()

font_families = {}
def get_font_families():
    global font_families
    if not font_families:
        ffiles = findsystem.findFonts()
        zlist = []
        for ff in ffiles:
            try:
                font = describe.openFont(ff)
            except: # Some font files cause ttfquery to raise an exception, in which case they are ignored
                continue
            try:
                wt, italic = describe.modifiers(font)
            except:
                wt, italic = 0, 0
            if wt == 400 and italic == 0:
                family = describe.shortName(font)[1].strip()
                zlist.append((family, ff))
        font_families = dict(zlist)
    return font_families

def sanitize_file_name(name):
    '''
    Remove characters that are illegal in filenames from name. 
    Also remove path separators. All illegal characters are replaced by
    underscores.
    '''
    return re.sub(r'\s', ' ', re.sub(r'["\'\|\~\:\?\\\/]|^-', '_', name.strip()))