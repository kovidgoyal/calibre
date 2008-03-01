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
__version__   = "0.4.39"
__docformat__ = "epytext"
__author__    = "Kovid Goyal <kovid@kovidgoyal.net>"
__appname__   = 'libprs500'

import sys, os, logging, mechanize, locale, cStringIO, re, subprocess, textwrap
from gettext import GNUTranslations
from math import floor
from optparse import OptionParser as _OptionParser
from optparse import IndentedHelpFormatter

from ttfquery import findsystem, describe

from libprs500.translations.msgfmt import make
from libprs500.ebooks.chardet import detect
from libprs500.terminfo import TerminalController
terminal_controller = TerminalController()

iswindows = 'win32' in sys.platform.lower() or 'win64' in sys.platform.lower()
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

class CustomHelpFormatter(IndentedHelpFormatter):
    
    def format_usage(self, usage):
        return _("%sUsage%s: %s\n") % (terminal_controller.BLUE, terminal_controller.NORMAL, usage)
    
    def format_heading(self, heading):
        return "%*s%s%s%s:\n" % (self.current_indent, terminal_controller.BLUE, 
                                 "", heading, terminal_controller.NORMAL)
        
    def format_option(self, option):
        result = []
        opts = self.option_strings[option]
        opt_width = self.help_position - self.current_indent - 2
        if len(opts) > opt_width:
            opts = "%*s%s\n" % (self.current_indent, "", 
                                    terminal_controller.GREEN+opts+terminal_controller.NORMAL)
            indent_first = self.help_position
        else:                       # start help on same line as opts
            opts = "%*s%-*s  " % (self.current_indent, "", opt_width + len(terminal_controller.GREEN + terminal_controller.NORMAL), 
                                  terminal_controller.GREEN + opts + terminal_controller.NORMAL)
            indent_first = 0
        result.append(opts)
        if option.help:
            help_text = self.expand_default(option).split('\n')
            help_lines = []
            
            for line in help_text:
                help_lines.extend(textwrap.wrap(line, self.help_width))
            result.append("%*s%s\n" % (indent_first, "", help_lines[0]))
            result.extend(["%*s%s\n" % (self.help_position, "", line)
                           for line in help_lines[1:]])
        elif opts[-1] != "\n":
            result.append("\n")
        return "".join(result)+'\n'

class OptionParser(_OptionParser):
    
    def __init__(self,
                 usage='%prog [options] filename',
                 version='%%prog (%s %s)'%(__appname__, __version__),
                 epilog=_('Created by ')+terminal_controller.RED+__author__+terminal_controller.NORMAL,
                 gui_mode=False,
                 **kwds):
        usage += '''\n\nWhenever you pass arguments to %prog that have spaces in them, '''\
                 '''enclose the arguments in quotation marks.'''
        _OptionParser.__init__(self, usage=usage, version=version, epilog=epilog, 
                               formatter=CustomHelpFormatter(), **kwds)
        self.gui_mode = gui_mode
        
    def error(self, msg):
        if self.gui_mode:
            raise Exception(msg)
        _OptionParser.error(self, msg)

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
def get_font_families(cached=None):
    global font_families
    if cached is not None:
        font_families = cached
    if not font_families:
        try:
            ffiles = findsystem.findFonts()
        except Exception, err:
            print 'WARNING: Could not find fonts on your system.'
            print err
        else:
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
                    try:
                        family = describe.shortName(font)[1].strip()
                    except: # Windows strikes again!
                        continue
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

def detect_ncpus():
    """Detects the number of effective CPUs in the system"""
    #for Linux, Unix and MacOS
    if hasattr(os, "sysconf"):
        if os.sysconf_names.has_key("SC_NPROCESSORS_ONLN"):
            #Linux and Unix
            ncpus = os.sysconf("SC_NPROCESSORS_ONLN")
            if isinstance(ncpus, int) and ncpus > 0:
                return ncpus
        else:
            #MacOS X
            return int(os.popen2("sysctl -n hw.ncpu")[1].read())
    #for Windows
    if os.environ.has_key("NUMBER_OF_PROCESSORS"):
        ncpus = int(os.environ["NUMBER_OF_PROCESSORS"]);
        if ncpus > 0:
            return ncpus
    #return the default value
    return 1


def launch(path_or_url):
    if islinux:
        subprocess.Popen(('xdg-open', path_or_url))
    elif isosx:
        subprocess.Popen(('open', path_or_url))
    elif iswindows:
        import win32api
        win32api.ShellExecute(0, 'open', path_or_url, None, os.getcwd(), 1)
