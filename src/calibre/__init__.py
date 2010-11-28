''' E-book management software'''
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import uuid, sys, os, re, logging, time, mimetypes, \
       __builtin__, warnings, multiprocessing
from urllib import getproxies
__builtin__.__dict__['dynamic_property'] = lambda(func): func(None)
from htmlentitydefs import name2codepoint
from math import floor
from functools import partial

warnings.simplefilter('ignore', DeprecationWarning)


from calibre.constants import iswindows, isosx, islinux, isfreebsd, isfrozen, \
                              terminal_controller, preferred_encoding, \
                              __appname__, __version__, __author__, \
                              win32event, win32api, winerror, fcntl, \
                              filesystem_encoding, plugins, config_dir
from calibre.startup import winutil, winutilerror

uuid.uuid4() # Imported before PyQt4 to workaround PyQt4 util-linux conflict on gentoo

if False:
    winutil, winutilerror, __appname__, islinux, __version__
    fcntl, win32event, isfrozen, __author__, terminal_controller
    winerror, win32api, isfreebsd

mimetypes.add_type('application/epub+zip',                '.epub')
mimetypes.add_type('text/x-sony-bbeb+xml',                '.lrs')
mimetypes.add_type('application/xhtml+xml',               '.xhtml')
mimetypes.add_type('image/svg+xml',                       '.svg')
mimetypes.add_type('text/fb2+xml',                        '.fb2')
mimetypes.add_type('application/x-sony-bbeb',             '.lrf')
mimetypes.add_type('application/x-sony-bbeb',             '.lrx')
mimetypes.add_type('application/x-dtbncx+xml',            '.ncx')
mimetypes.add_type('application/adobe-page-template+xml', '.xpgt')
mimetypes.add_type('application/x-font-opentype',         '.otf')
mimetypes.add_type('application/x-font-truetype',         '.ttf')
mimetypes.add_type('application/oebps-package+xml',       '.opf')
mimetypes.add_type('application/vnd.palm',                '.pdb')
mimetypes.add_type('application/x-mobipocket-ebook',      '.mobi')
mimetypes.add_type('application/x-mobipocket-ebook',      '.prc')
mimetypes.add_type('application/x-mobipocket-ebook',      '.azw')
mimetypes.add_type('application/x-cbz',                   '.cbz')
mimetypes.add_type('application/x-cbr',                   '.cbr')
mimetypes.add_type('application/x-koboreader-ebook',      '.kobo')
mimetypes.add_type('image/wmf',                           '.wmf')
mimetypes.add_type('image/jpeg',                          '.jpg')
mimetypes.add_type('image/jpeg',                          '.jpeg')
mimetypes.add_type('image/png',                           '.png')
mimetypes.add_type('image/gif',                           '.gif')
mimetypes.add_type('image/bmp',                           '.bmp')
mimetypes.add_type('image/svg+xml',                       '.svg')

guess_type = mimetypes.guess_type
import cssutils
cssutils.log.setLevel(logging.WARN)

def to_unicode(raw, encoding='utf-8', errors='strict'):
    if isinstance(raw, unicode):
        return raw
    return raw.decode(encoding, errors)

def patheq(p1, p2):
    p = os.path
    d = lambda x : p.normcase(p.normpath(p.realpath(p.normpath(x))))
    if not p1 or not p2:
        return False
    return d(p1) == d(p2)

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


_filename_sanitize = re.compile(r'[\xae\0\\|\?\*<":>\+/]')

def sanitize_file_name(name, substitute='_', as_unicode=False):
    '''
    Sanitize the filename `name`. All invalid characters are replaced by `substitute`.
    The set of invalid characters is the union of the invalid characters in Windows,
    OS X and Linux. Also removes leading and trailing whitespace.
    **WARNING:** This function also replaces path separators, so only pass file names
    and not full paths to it.
    *NOTE:* This function always returns byte strings, not unicode objects. The byte strings
    are encoded in the filesystem encoding of the platform, or UTF-8.
    '''
    if isinstance(name, unicode):
        name = name.encode(filesystem_encoding, 'ignore')
    one = _filename_sanitize.sub(substitute, name)
    one = re.sub(r'\s', ' ', one).strip()
    one = re.sub(r'^\.+$', '_', one)
    if as_unicode:
        one = one.decode(filesystem_encoding)
    one = one.replace('..', substitute)
    # Windows doesn't like path components that end with a period
    if one.endswith('.'):
        one = one[:-1]+'_'
    return one


def prints(*args, **kwargs):
    '''
    Print unicode arguments safely by encoding them to preferred_encoding
    Has the same signature as the print function from Python 3, except for the
    additional keyword argument safe_encode, which if set to True will cause the
    function to use repr when encoding fails.
    '''
    file = kwargs.get('file', sys.stdout)
    sep  = kwargs.get('sep', ' ')
    end  = kwargs.get('end', '\n')
    enc = preferred_encoding
    safe_encode = kwargs.get('safe_encode', False)
    if 'CALIBRE_WORKER' in os.environ:
        enc = 'utf-8'
    for i, arg in enumerate(args):
        if isinstance(arg, unicode):
            try:
                arg = arg.encode(enc)
            except UnicodeEncodeError:
                try:
                    arg = arg.encode('utf-8')
                except:
                    if not safe_encode:
                        raise
                    arg = repr(arg)
        if not isinstance(arg, str):
            try:
                arg = str(arg)
            except ValueError:
                arg = unicode(arg)
            if isinstance(arg, unicode):
                try:
                    arg = arg.encode(enc)
                except UnicodeEncodeError:
                    try:
                        arg = arg.encode('utf-8')
                    except:
                        if not safe_encode:
                            raise
                        arg = repr(arg)

        try:
            file.write(arg)
        except:
            file.write(repr(arg))
        if i != len(args)-1:
            file.write(sep)
    file.write(end)

class CommandLineError(Exception):
    pass

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
    if ext in ['zip', 'cbz', 'epub', 'oebzip']:
        from calibre.libunzip import extract as zipextract
        extractor = zipextract
    elif ext in ['cbr', 'rar']:
        from calibre.libunrar import extract as rarextract
        extractor = rarextract
    if extractor is None:
        raise Exception('Unknown archive type')
    extractor(path, dir)

def get_proxies(debug=True):
    proxies = getproxies()
    for key, proxy in list(proxies.items()):
        if not proxy or '..' in proxy:
            del proxies[key]
            continue
        if proxy.startswith(key+'://'):
            proxy = proxy[len(key)+3:]
        if proxy.endswith('/'):
            proxy = proxy[:-1]
        if len(proxy) > 4:
            proxies[key] = proxy
        else:
            prints('Removing invalid', key, 'proxy:', proxy)
            del proxies[key]

    if proxies and debug:
        prints('Using proxies:', proxies)
    return proxies

def get_parsed_proxy(typ='http', debug=True):
    proxies = get_proxies(debug)
    proxy = proxies.get(typ, None)
    if proxy:
        pattern = re.compile((
            '(?:ptype://)?' \
            '(?:(?P<user>\w+):(?P<pass>.*)@)?' \
            '(?P<host>[\w\-\.]+)' \
            '(?::(?P<port>\d+))?').replace('ptype', typ)
        )

        match = pattern.match(proxies[typ])
        if match:
            try:
                ans = {
                        'host' : match.group('host'),
                        'port' : match.group('port'),
                        'user' : match.group('user'),
                        'pass' : match.group('pass')
                    }
                if ans['port']:
                    ans['port'] = int(ans['port'])
            except:
                if debug:
                    traceback.print_exc()
            else:
                if debug:
                    prints('Using http proxy', str(ans))
                return ans


def browser(honor_time=True, max_time=2, mobile_browser=False):
    '''
    Create a mechanize browser for web scraping. The browser handles cookies,
    refresh requests and ignores robots.txt. Also uses proxy if avaialable.

    :param honor_time: If True honors pause time in refresh requests
    :param max_time: Maximum time in seconds to wait during a refresh request
    '''
    from calibre.utils.browser import Browser
    opener = Browser()
    opener.set_handle_refresh(True, max_time=max_time, honor_time=honor_time)
    opener.set_handle_robots(False)
    opener.addheaders = [('User-agent', ' Mozilla/5.0 (Windows; U; Windows CE 5.1; rv:1.8.1a3) Gecko/20060610 Minimo/0.016' if mobile_browser else \
                          'Mozilla/5.0 (X11; U; i686 Linux; en_US; rv:1.8.0.4) Gecko/20060508 Firefox/1.5.0.4')]
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
    @return: scaled, new_width, new_height. scaled is True iff new_width and/or new_height is different from width or height.
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

class CurrentDir(object):

    def __init__(self, path):
        self.path = path
        self.cwd = None

    def __enter__(self, *args):
        self.cwd = os.getcwd()
        os.chdir(self.path)
        return self.cwd

    def __exit__(self, *args):
        os.chdir(self.cwd)


class StreamReadWrapper(object):
    '''
    Used primarily with pyPdf to ensure the stream is properly closed.
    '''

    def __init__(self, stream):
        for x in ('read', 'seek', 'tell'):
            setattr(self, x, getattr(stream, x))

    def __exit__(self, *args):
        for x in ('read', 'seek', 'tell'):
            setattr(self, x, None)

    def __enter__(self):
        return self


def detect_ncpus():
    """Detects the number of effective CPUs in the system"""
    ans = -1
    try:
        ans = multiprocessing.cpu_count()
    except:
        from PyQt4.Qt import QThread
        ans = QThread.idealThreadCount()
    if ans < 1:
        ans = 1
    return ans


relpath = os.path.relpath
_spat = re.compile(r'^the\s+|^a\s+|^an\s+', re.IGNORECASE)
def english_sort(x, y):
    '''
    Comapare two english phrases ignoring starting prepositions.
    '''
    return cmp(_spat.sub('', x), _spat.sub('', y))

def walk(dir):
    ''' A nice interface to os.walk '''
    for record in os.walk(dir):
        for f in record[-1]:
            yield os.path.join(record[0], f)

def strftime(fmt, t=None):
    ''' A version of strftime that returns unicode strings and tries to handle dates
    before 1900 '''
    if not fmt:
        return u''
    if t is None:
        t = time.localtime()
    if hasattr(t, 'timetuple'):
        t = t.timetuple()
    early_year = t[0] < 1900
    if early_year:
        replacement = 1900 if t[0]%4 == 0 else 1901
        fmt = fmt.replace('%Y', '_early year hack##')
        t = list(t)
        orig_year = t[0]
        t[0] = replacement
    ans = None
    if iswindows:
        if isinstance(fmt, unicode):
            fmt = fmt.encode('mbcs')
        ans = plugins['winutil'][0].strftime(fmt, t)
    else:
        ans = time.strftime(fmt, t).decode(preferred_encoding, 'replace')
    if early_year:
        ans = ans.replace('_early year hack##', str(orig_year))
    return ans

def my_unichr(num):
    try:
        return unichr(num)
    except ValueError:
        return u'?'

def entity_to_unicode(match, exceptions=[], encoding='cp1252',
        result_exceptions={}):
    '''
    :param match: A match object such that '&'+match.group(1)';' is the entity.

    :param exceptions: A list of entities to not convert (Each entry is the name of the entity, for e.g. 'apos' or '#1234'

    :param encoding: The encoding to use to decode numeric entities between 128 and 256.
    If None, the Unicode UCS encoding is used. A common encoding is cp1252.

    :param result_exceptions: A mapping of characters to entities. If the result
    is in result_exceptions, result_exception[result] is returned instead.
    Convenient way to specify exception for things like < or > that can be
    specified by various actual entities.
    '''
    def check(ch):
        return result_exceptions.get(ch, ch)

    ent = match.group(1)
    if ent in exceptions:
        return '&'+ent+';'
    if ent == 'apos':
        return check("'")
    if ent == 'hellips':
        ent = 'hellip'
    if ent.startswith('#'):
        try:
            if ent[1] in ('x', 'X'):
                num = int(ent[2:], 16)
            else:
                num = int(ent[1:])
        except:
            return '&'+ent+';'
        if encoding is None or num > 255:
            return check(my_unichr(num))
        try:
            return check(chr(num).decode(encoding))
        except UnicodeDecodeError:
            return check(my_unichr(num))
    try:
        return check(my_unichr(name2codepoint[ent]))
    except KeyError:
        return '&'+ent+';'

_ent_pat = re.compile(r'&(\S+?);')
xml_entity_to_unicode = partial(entity_to_unicode, result_exceptions = {
    '"' : '&quot;',
    "'" : '&apos;',
    '<' : '&lt;',
    '>' : '&gt;',
    '&' : '&amp;'})

def replace_entities(raw):
    return _ent_pat.sub(entity_to_unicode, raw)

def xml_replace_entities(raw):
    return _ent_pat.sub(xml_entity_to_unicode, raw)

def prepare_string_for_xml(raw, attribute=False):
    raw = _ent_pat.sub(entity_to_unicode, raw)
    raw = raw.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if attribute:
        raw = raw.replace('"', '&quot;').replace("'", '&apos;')
    return raw

def isbytestring(obj):
    return isinstance(obj, (str, bytes))

def force_unicode(obj, enc=preferred_encoding):
    if isbytestring(obj):
        try:
            obj = obj.decode(enc)
        except:
            try:
                obj = obj.decode(filesystem_encoding if enc ==
                        preferred_encoding else preferred_encoding)
            except:
                try:
                    obj = obj.decode('utf-8')
                except:
                    obj = repr(obj)
                    if isbytestring(obj):
                        obj = obj.decode('utf-8')
    return obj


def human_readable(size):
    """ Convert a size in bytes into a human readable form """
    divisor, suffix = 1, "B"
    for i, candidate in enumerate(('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB')):
        if size < 1024**(i+1):
            divisor, suffix = 1024**(i), candidate
            break
    size = str(float(size)/divisor)
    if size.find(".") > -1:
        size = size[:size.find(".")+2]
    if size.endswith('.0'):
        size = size[:-2]
    return size + " " + suffix

if isosx:
    import glob, shutil
    fdir = os.path.expanduser('~/.fonts')
    try:
        if not os.path.exists(fdir):
            os.makedirs(fdir)
        if not os.path.exists(os.path.join(fdir, 'LiberationSans_Regular.ttf')):
            base = P('fonts/liberation/*.ttf')
            for f in glob.glob(base):
                shutil.copy2(f, fdir)
    except:
        import traceback
        traceback.print_exc()

def ipython(user_ns=None):
    old_argv = sys.argv
    sys.argv = ['ipython']
    if user_ns is None:
        user_ns = locals()
    ipydir = os.path.join(config_dir, ('_' if iswindows else '.')+'ipython')
    os.environ['IPYTHONDIR'] = ipydir
    if not os.path.exists(ipydir):
        os.makedirs(ipydir)
    for x in ('', '.ini'):
        rc = os.path.join(ipydir, 'ipythonrc'+x)
        if not os.path.exists(rc):
            open(rc, 'wb').write(' ')
    UC = '''
import IPython.ipapi
ip = IPython.ipapi.get()

# You probably want to uncomment this if you did %upgrade -nolegacy
import ipy_defaults

import os, re, sys

def main():
    # Handy tab-completers for %cd, %run, import etc.
    # Try commenting this out if you have completion problems/slowness
    import ipy_stock_completers

    # uncomment if you want to get ipython -p sh behaviour
    # without having to use command line switches

    import ipy_profile_sh


    # Configure your favourite editor?
    # Good idea e.g. for %edit os.path.isfile

    import ipy_editors

    # Choose one of these:

    #ipy_editors.scite()
    #ipy_editors.scite('c:/opt/scite/scite.exe')
    #ipy_editors.komodo()
    #ipy_editors.idle()
    # ... or many others, try 'ipy_editors??' after import to see them

    # Or roll your own:
    #ipy_editors.install_editor("c:/opt/jed +$line $file")

    ipy_editors.kate()

    o = ip.options
    # An example on how to set options
    #o.autocall = 1
    o.system_verbose = 0
    o.confirm_exit = 0

main()
    '''
    uc = os.path.join(ipydir, 'ipy_user_conf.py')
    if not os.path.exists(uc):
        open(uc, 'wb').write(UC)
    from IPython.Shell import IPShellEmbed
    ipshell = IPShellEmbed(user_ns=user_ns)
    ipshell()
    sys.argv = old_argv


