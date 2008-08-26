''' E-book management software'''
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, re, logging, time, subprocess, mechanize, atexit
from htmlentitydefs import name2codepoint
from math import floor
from logging import Formatter

from PyQt4.QtCore import QUrl
from PyQt4.QtGui  import QDesktopServices
from calibre.startup import plugins, winutil, winutilerror
from calibre.constants import iswindows, isosx, islinux, isfrozen, \
                              terminal_controller, preferred_encoding, \
                              __appname__, __version__, __author__, \
                              win32event, win32api, winerror, fcntl


def unicode_path(path, abs=False):
    if not isinstance(path, unicode):
        path = path.decode(sys.getfilesystemencoding())
    if abs:
        path = os.path.abspath(path)
    return path

def osx_version():
    if isosx:
        import platform
        src = platform.mac_ver()[0]
        m = re.match(r'(\d+)\.(\d+)\.(\d+)', src)
        if m:
            return int(m.group(1)), int(m.group(2)), int(m.group(3))


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
    if os.environ.get('CALIBRE_WORKER', None) is not None and logger.handlers:
        return
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
    if ext in ['zip', 'cbz', 'epub']:
        from calibre.libunzip import extract as zipextract
        extractor = zipextract
    elif ext in ['cbr', 'rar']:
        from calibre.libunrar import extract as rarextract
        extractor = rarextract
    if extractor is None:
        raise Exception('Unknown archive type')
    extractor(path, dir)

def get_proxies():
    proxies = {}
    
    for q in ('http', 'ftp'):
        proxy =  os.environ.get(q+'_proxy', None)
        if not proxy: continue
        if proxy.startswith(q+'://'):
            proxy = proxy[7:]
        proxies[q] = proxy

    if iswindows:
        try:
            winreg = __import__('_winreg')
            settings = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                      'Software\\Microsoft\\Windows'
                                      '\\CurrentVersion\\Internet Settings')
            proxy = winreg.QueryValueEx(settings, "ProxyEnable")[0]
            if proxy:
                server = str(winreg.QueryValueEx(settings, 'ProxyServer')[0])
                if ';' in server:
                    for p in server.split(';'):
                        protocol, address = p.split('=')
                        proxies[protocol] = address
                else:
                    proxies['http'] = server
                    proxies['ftp'] =  server
            settings.Close()
        except Exception, e:
            print('Unable to detect proxy settings: %s' % str(e))
    if proxies:
        print('Using proxies: %s' % proxies)
    return proxies


def browser(honor_time=False):
    opener = mechanize.Browser()
    opener.set_handle_refresh(True, honor_time=honor_time)
    opener.set_handle_robots(False)
    opener.addheaders = [('User-agent', 'Mozilla/5.0 (X11; U; i686 Linux; en_US; rv:1.8.0.4) Gecko/20060508 Firefox/1.5.0.4')]
    http_proxy = get_proxies().get('http', None)
    if http_proxy:
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
    if os.path.exists(path_or_url):
        path_or_url = 'file:'+path_or_url
    QDesktopServices.openUrl(QUrl(path_or_url))

def relpath(target, base=os.curdir):
    """
    Return a relative path to the target from either the current dir or an optional base dir.
    Base can be a directory specified either as absolute or relative to current dir.
    """

    #if not os.path.exists(target):
    #    raise OSError, 'Target does not exist: '+target
    if target == base:
        raise ValueError('target and base are both: %s'%target)
    if not os.path.isdir(base):
        raise OSError, 'Base is not a directory or does not exist: '+base

    base_list = (os.path.abspath(base)).split(os.sep)
    target_list = (os.path.abspath(target)).split(os.sep)

    # On the windows platform the target may be on a completely different drive from the base.
    if iswindows and base_list[0].upper() != target_list[0].upper():
        raise OSError, 'Target is on a different drive to base. Target: '+repr(target)+', base: '+repr(base)

    # Starting from the filepath root, work out how much of the filepath is
    # shared by base and target.
    for i in range(min(len(base_list), len(target_list))):
        if base_list[i] != target_list[i]: break
    else:
        # If we broke out of the loop, i is pointing to the first differing path elements.
        # If we didn't break out of the loop, i is pointing to identical path elements.
        # Increment i so that in all cases it points to the first differing path elements.
        i+=1

    rel_list = [os.pardir] * (len(base_list)-i) + target_list[i:]
    return os.path.join(*rel_list)

_spat = re.compile(r'^the\s+|^a\s+|^an\s+', re.IGNORECASE)
def english_sort(x, y):
    '''
    Comapare two english phrases ignoring starting prepositions.
    '''
    return cmp(_spat.sub('', x), _spat.sub('', y))

class LoggingInterface:

    def __init__(self, logger):
        self.__logger = logger
        
    def setup_cli_handler(self, verbosity):
        for handler in self.__logger.handlers:
            if isinstance(handler, logging.StreamHandler):
                return
        if os.environ.get('CALIBRE_WORKER', None) is not None and self.__logger.handlers:
            return
        stream    = sys.stdout
        formatter = logging.Formatter()
        level     = logging.INFO
        if verbosity > 0:
            formatter = ColoredFormatter('[%(levelname)s] %(filename)s:%(lineno)s: %(message)s') if verbosity > 1 else \
                        ColoredFormatter('%(levelname)s: %(message)s')
            level     = logging.DEBUG
            if verbosity > 1:
                stream = sys.stderr
        
        handler = logging.StreamHandler(stream)
        handler.setFormatter(formatter)
        handler.setLevel(level)
        self.__logger.addHandler(handler)
        self.__logger.setLevel(level)


    def ___log(self, func, msg, args, kwargs):
        args = [msg] + list(args)
        for i in range(len(args)):
            if isinstance(args[i], unicode):
                args[i] = args[i].encode(preferred_encoding, 'replace')
        func(*args, **kwargs)

    def log_debug(self, msg, *args, **kwargs):
        self.___log(self.__logger.debug, msg, args, kwargs)

    def log_info(self, msg, *args, **kwargs):
        self.___log(self.__logger.info, msg, args, kwargs)

    def log_warning(self, msg, *args, **kwargs):
        self.___log(self.__logger.warning, msg, args, kwargs)

    def log_warn(self, msg, *args, **kwargs):
        self.___log(self.__logger.warning, msg, args, kwargs)

    def log_error(self, msg, *args, **kwargs):
        self.___log(self.__logger.error, msg, args, kwargs)

    def log_critical(self, msg, *args, **kwargs):
        self.___log(self.__logger.critical, msg, args, kwargs)

    def log_exception(self, msg, *args):
        self.___log(self.__logger.exception, msg, args, {})


def strftime(fmt, t=time.localtime()):
    '''
    A version of strtime that returns unicode strings.
    '''
    result = time.strftime(fmt, t)
    return unicode(result, preferred_encoding, 'replace')
    
def entity_to_unicode(match, exceptions=[], encoding='cp1252'):
    '''
    @param match: A match object such that '&'+match.group(1)';' is the entity.
    @param exceptions: A list of entities to not convert (Each entry is the name of the entity, for e.g. 'apos' or '#1234'
    @param encoding: The encoding to use to decode numeric entities between 128 and 256.
    If None, the Unicode UCS encoding is used. A common encoding is cp1252.
    '''
    ent = match.group(1)
    if ent in exceptions:
        return '&'+ent+';'
    if ent == 'apos':
        return "'"
    if ent.startswith(u'#x'):
        num = int(ent[2:], 16)
        if encoding is None or num > 255:
            return unichr(num)
        return chr(num).decode(encoding)
    if ent.startswith(u'#'):
        try:
            num = int(ent[1:])
        except ValueError:
            return '&'+ent+';'
        if encoding is None or num > 255:
            return unichr(num)
        try:
            return chr(num).decode(encoding)
        except UnicodeDecodeError:
            return unichr(num)
    try:
        return unichr(name2codepoint[ent])
    except KeyError:
        return '&'+ent+';'

if isosx:
    fdir = os.path.expanduser('~/.fonts')
    if not os.path.exists(fdir):
        os.makedirs(fdir)
    if not os.path.exists(os.path.join(fdir, 'LiberationSans_Regular.ttf')):
        from calibre.ebooks.lrf.fonts.liberation import __all__ as fonts
        for font in fonts:
            l = {}
            exec 'from calibre.ebooks.lrf.fonts.liberation.'+font+' import font_data' in l
            open(os.path.join(fdir, font+'.ttf'), 'wb').write(l['font_data'])
            
# Migrate from QSettings based config system
from calibre.utils.config import migrate
migrate()
