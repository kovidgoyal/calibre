''' E-book management software'''
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
__version__   = '0.4.50'
__docformat__ = "epytext"
__author__    = "Kovid Goyal <kovid at kovidgoyal.net>"
__appname__   = 'calibre'

import sys, os, logging, mechanize, locale, copy, cStringIO, re, subprocess, \
       textwrap, atexit, cPickle
from gettext import GNUTranslations
from math import floor
from optparse import OptionParser as _OptionParser
from optparse import IndentedHelpFormatter
from logging import Formatter

from ttfquery import findsystem, describe
from PyQt4.QtCore import QSettings, QVariant

from calibre.translations.msgfmt import make
from calibre.ebooks.chardet import detect
from calibre.terminfo import TerminalController
terminal_controller = TerminalController(sys.stdout)

iswindows = 'win32' in sys.platform.lower() or 'win64' in sys.platform.lower()
isosx     = 'darwin' in sys.platform.lower()
islinux   = not(iswindows or isosx)

try:
    locale.setlocale(locale.LC_ALL, '')
except:
    pass

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

class ColoredFormatter(Formatter):
    
    def format(self, record):
        ln = record.__dict__['levelname']
        col = ''
        if ln == 'CRITICAL':
            col = terminal_controller.YELLOW
        elif ln == 'ERROR':
            col = terminal_controller.RED
        elif ln in ['WARN', 'WARNING']:
            col = terminal_controller.BLUE
        elif ln == 'INFO':
            col = terminal_controller.GREEN
        elif ln == 'DEBUG':
            col = terminal_controller.CYAN
        record.__dict__['levelname'] = col + record.__dict__['levelname'] + terminal_controller.NORMAL
        return Formatter.format(self, record)
         

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
                 conflict_handler='resolve',
                 **kwds):
        usage += '''\n\nWhenever you pass arguments to %prog that have spaces in them, '''\
                 '''enclose the arguments in quotation marks.'''
        _OptionParser.__init__(self, usage=usage, version=version, epilog=epilog, 
                               formatter=CustomHelpFormatter(), 
                               conflict_handler=conflict_handler, **kwds)
        self.gui_mode = gui_mode
        
    def error(self, msg):
        if self.gui_mode:
            raise Exception(msg)
        _OptionParser.error(self, msg)
        
    def merge(self, parser):
        '''
        Add options from parser to self. In case of conflicts, confilicting options from
        parser are skipped.
        '''
        opts   = list(parser.option_list)
        groups = list(parser.option_groups)
        
        def merge_options(options, container):
            for opt in copy.deepcopy(options):
                if not self.has_option(opt.get_opt_string()):
                    container.add_option(opt)
                
        merge_options(opts, self)
        
        for group in groups:
            g = self.add_option_group(group.title)
            merge_options(group.option_list, g)
        
    def subsume(self, group_name, msg=''):
        '''
        Move all existing options into a subgroup named
        C{group_name} with description C{msg}.
        '''
        opts = [opt for opt in self.options_iter() if opt.get_opt_string() not in ('--version', '--help')]
        self.option_groups = []
        subgroup = self.add_option_group(group_name, msg)
        for opt in opts:
            self.remove_option(opt.get_opt_string())
            subgroup.add_option(opt)
        
    def options_iter(self):
        for opt in self.option_list:
            if str(opt).strip():
                yield opt
        for gr in self.option_groups:
            for opt in gr.option_list:
                if str(opt).strip():
                    yield opt
                
    def option_by_dest(self, dest):
        for opt in self.options_iter():
            if opt.dest == dest:
                return opt
    
    def merge_options(self, lower, upper):
        '''
        Merge options in lower and upper option lists into upper.
        Default values in upper are overriden by
        non default values in lower.
        '''
        for dest in lower.__dict__.keys():
            if not upper.__dict__.has_key(dest):
                continue
            opt = self.option_by_dest(dest)
            if lower.__dict__[dest] != opt.default and \
               upper.__dict__[dest] == opt.default:
                upper.__dict__[dest] = lower.__dict__[dest]
        

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
        from calibre.libunzip import extract as zipextract
        extractor = zipextract
    elif ext == 'rar':
        from calibre.libunrar import extract as rarextract
        extractor = rarextract
    if extractor is None:
        raise Exception('Unknown archive type')
    extractor(path, dir)

def browser(honor_time=False):
    http_proxy = os.environ.get('http_proxy', None)
    opener = mechanize.Browser()
    opener.set_handle_refresh(True, honor_time=honor_time)
    opener.set_handle_robots(False)
    opener.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; i686 Linux; en_US; rv:1.8.0.4) Gecko/20060508 Firefox/1.5.0.4')]
    if http_proxy:
        if http_proxy.startswith('http://'):
            http_proxy = http_proxy[7:]
        opener.set_proxies({'http':http_proxy})
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
    from calibre.translations.data import translations
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
                    if 'Optane' in str(ff):
                        font = describe.openFont(ff)
                        wt, italic = describe.modifiers(font)
                except:
                    pass
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
    try:
        from PyQt4.QtCore import QThread
        ans = QThread.idealThreadCount()
        if ans > 0:
            return ans
    except:
        pass
    #for Linux, Unix and MacOS
    if hasattr(os, "sysconf"):
        if os.sysconf_names.has_key("SC_NPROCESSORS_ONLN"):
            #Linux and Unix
            ncpus = os.sysconf("SC_NPROCESSORS_ONLN")
            if isinstance(ncpus, int) and ncpus > 0:
                return ncpus
        else:
            #MacOS X
            try:
                return int(subprocess.Popen(('sysctl', '-n', 'hw.cpu'), stdout=subprocess.PIPE).stdout.read())
            except IOError: # Occassionally the system call gets interrupted
                try:
                    return int(subprocess.Popen(('sysctl', '-n', 'hw.cpu'), stdout=subprocess.PIPE).stdout.read())
                except IOError:
                    return 1
            except ValueError: # On some systems the sysctl call fails
                return 1
                
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
        win32api = __import__('win32api', globals(), locals(), [], -1)
        win32api.ShellExecute(0, 'open', path_or_url, None, os.getcwd(), 1)
        
def relpath(target, base=os.curdir):
    """
    Return a relative path to the target from either the current dir or an optional base dir.
    Base can be a directory specified either as absolute or relative to current dir.
    """

    if not os.path.exists(target):
        raise OSError, 'Target does not exist: '+target

    if not os.path.isdir(base):
        raise OSError, 'Base is not a directory or does not exist: '+base

    base_list = (os.path.abspath(base)).split(os.sep)
    target_list = (os.path.abspath(target)).split(os.sep)

    # On the windows platform the target may be on a completely different drive from the base.
    if iswindows and base_list[0] <> target_list[0]:
        raise OSError, 'Target is on a different drive to base. Target: '+target_list[0].upper()+', base: '+base_list[0].upper()

    # Starting from the filepath root, work out how much of the filepath is
    # shared by base and target.
    for i in range(min(len(base_list), len(target_list))):
        if base_list[i] <> target_list[i]: break
    else:
        # If we broke out of the loop, i is pointing to the first differing path elements.
        # If we didn't break out of the loop, i is pointing to identical path elements.
        # Increment i so that in all cases it points to the first differing path elements.
        i+=1

    rel_list = [os.pardir] * (len(base_list)-i) + target_list[i:]
    return os.path.join(*rel_list)

def _clean_lock_file(file):
    try:
        file.close()
    except:
        pass
    try:
        os.remove(file.name)
    except:
        pass
    
def singleinstance(name):
    '''
    Return True if no other instance of the application identified by name is running, 
    False otherwise.
    @param name: The name to lock.
    @type name: string 
    '''
    if iswindows:
        from win32event import CreateMutex
        from win32api import CloseHandle, GetLastError
        from winerror import ERROR_ALREADY_EXISTS
        mutexname = 'mutexforsingleinstanceof'+__appname__+name
        mutex =  CreateMutex(None, False, mutexname)
        if mutex:
            atexit.register(CloseHandle, mutex)
        return not GetLastError() == ERROR_ALREADY_EXISTS
    else:
        import fcntl
        global _lock_file
        path = os.path.expanduser('~/.'+__appname__+'_'+name+'.lock')
        try:
            f = open(path, 'w')
            fcntl.lockf(f.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
            atexit.register(_clean_lock_file, f)
            return True
        except IOError:
            return False
        
    return False

class Settings(QSettings):
    
    def __init__(self):
        QSettings.__init__(self, QSettings.IniFormat, QSettings.UserScope,
                           'kovidgoyal.net', 'calibre')
        
    def migrate(self, settings):
        for key in settings.allKeys():
            self.setValue(key, settings.value(key, QVariant()))
                          
    def get(self, key, default=None):
        key = str(key)
        if not self.contains(key):
            return default
        val = str(self.value(key, QVariant()).toByteArray())
        if not val:
            return None
        return cPickle.loads(val)
    
    def set(self, key, val):
        val = cPickle.dumps(val, -1)
        self.setValue(str(key), QVariant(val))
        
_settings = Settings()
if not _settings.get('migrated from QSettings'):
    _settings.migrate(QSettings('KovidsBrain', 'libprs500'))
    _settings.set('migrated from QSettings', True)
    _settings.sync()
    
_spat = re.compile(r'^the\s+|^a\s+|^an\s+', re.IGNORECASE)
def english_sort(x, y):
    '''
    Comapare two english phrases ignoring starting prepositions.
    '''
    return cmp(_spat.sub('', x), _spat.sub('', y))
