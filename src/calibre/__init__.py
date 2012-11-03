''' E-book management software'''
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, re, time, random, __builtin__, warnings
__builtin__.__dict__['dynamic_property'] = lambda func: func(None)
from math import floor
from functools import partial

warnings.simplefilter('ignore', DeprecationWarning)
try:
    os.getcwdu()
except:
    os.chdir(os.path.expanduser('~'))

from calibre.constants import (iswindows, isosx, islinux, isfrozen,
        isbsd, preferred_encoding, __appname__, __version__, __author__,
        win32event, win32api, winerror, fcntl,
        filesystem_encoding, plugins, config_dir)
from calibre.startup import winutil, winutilerror

if False and islinux and not getattr(sys, 'frozen', False):
    # Imported before PyQt4 to workaround PyQt4 util-linux conflict discovered on gentoo
    # See http://bugs.gentoo.org/show_bug.cgi?id=317557
    # Importing uuid is slow so get rid of this at some point, maybe in a few
    # years when even Debian has caught up
    # Also remember to remove it from site.py in the binary builds
    import uuid
    uuid.uuid4()

if False:
    # Prevent pyflakes from complaining
    winutil, winutilerror, __appname__, islinux, __version__
    fcntl, win32event, isfrozen, __author__
    winerror, win32api, isbsd, config_dir

_mt_inited = False
def _init_mimetypes():
    global _mt_inited
    import mimetypes
    mimetypes.init([P('mime.types')])
    _mt_inited = True

def guess_type(*args, **kwargs):
    import mimetypes
    if not _mt_inited:
        _init_mimetypes()
    return mimetypes.guess_type(*args, **kwargs)

def guess_all_extensions(*args, **kwargs):
    import mimetypes
    if not _mt_inited:
        _init_mimetypes()
    return mimetypes.guess_all_extensions(*args, **kwargs)


def guess_extension(*args, **kwargs):
    import mimetypes
    if not _mt_inited:
        _init_mimetypes()
    ext = mimetypes.guess_extension(*args, **kwargs)
    if not ext and args and args[0] == 'application/x-palmreader':
        ext = '.pdb'
    return ext

def get_types_map():
    import mimetypes
    if not _mt_inited:
        _init_mimetypes()
    return mimetypes.types_map

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

def confirm_config_name(name):
    return name + '_again'

_filename_sanitize = re.compile(r'[\xae\0\\|\?\*<":>\+/]')
_filename_sanitize_unicode = frozenset([u'\\', u'|', u'?', u'*', u'<',
    u'"', u':', u'>', u'+', u'/'] + list(map(unichr, xrange(32))))

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
    bname, ext = os.path.splitext(one)
    one = re.sub(r'^\.+$', '_', bname)
    if as_unicode:
        one = one.decode(filesystem_encoding)
    one = one.replace('..', substitute)
    one += ext
    # Windows doesn't like path components that end with a period
    if one and one[-1] in ('.', ' '):
        one = one[:-1]+'_'
    # Names starting with a period are hidden on Unix
    if one.startswith('.'):
        one = '_' + one[1:]
    return one

def sanitize_file_name_unicode(name, substitute='_'):
    '''
    Sanitize the filename `name`. All invalid characters are replaced by `substitute`.
    The set of invalid characters is the union of the invalid characters in Windows,
    OS X and Linux. Also removes leading and trailing whitespace.
    **WARNING:** This function also replaces path separators, so only pass file names
    and not full paths to it.
    '''
    if isbytestring(name):
        return sanitize_file_name(name, substitute=substitute, as_unicode=True)
    chars = [substitute if c in _filename_sanitize_unicode else c for c in
            name]
    one = u''.join(chars)
    one = re.sub(r'\s', ' ', one).strip()
    bname, ext = os.path.splitext(one)
    one = re.sub(r'^\.+$', '_', bname)
    one = one.replace('..', substitute)
    one += ext
    # Windows doesn't like path components that end with a period or space
    if one and one[-1] in ('.', ' '):
        one = one[:-1]+'_'
    # Names starting with a period are hidden on Unix
    if one.startswith('.'):
        one = '_' + one[1:]
    return one

def sanitize_file_name2(name, substitute='_'):
    '''
    Sanitize filenames removing invalid chars. Keeps unicode names as unicode
    and bytestrings as bytestrings
    '''
    if isbytestring(name):
        return sanitize_file_name(name, substitute=substitute)
    return sanitize_file_name_unicode(name, substitute=substitute)

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
            import repr as reprlib
            file.write(reprlib.repr(arg))
        if i != len(args)-1:
            file.write(bytes(sep))
    file.write(bytes(end))

class CommandLineError(Exception):
    pass

def setup_cli_handlers(logger, level):
    import logging
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
    extractor = None
    # First use the file header to identify its type
    with open(path, 'rb') as f:
        id_ = f.read(3)
    if id_ == b'Rar':
        from calibre.libunrar import extract as rarextract
        extractor = rarextract
    elif id_.startswith(b'PK'):
        from calibre.libunzip import extract as zipextract
        extractor = zipextract
    if extractor is None:
        # Fallback to file extension
        ext = os.path.splitext(path)[1][1:].lower()
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
    from urllib import getproxies
    proxies = getproxies()
    for key, proxy in list(proxies.items()):
        if not proxy or '..' in proxy:
            del proxies[key]
            continue
        if proxy.startswith(key+'://'):
            proxy = proxy[len(key)+3:]
        if key == 'https' and proxy.startswith('http://'):
            proxy = proxy[7:]
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
                    import traceback
                    traceback.print_exc()
            else:
                if debug:
                    prints('Using http proxy', str(ans))
                return ans

def get_proxy_info(proxy_scheme, proxy_string):
    '''
    Parse all proxy information from a proxy string (as returned by
    get_proxies). The returned dict will have members set to None when the info
    is not available in the string. If an exception occurs parsing the string
    this method returns None.
    '''
    import urlparse
    try:
        proxy_url = u'%s://%s'%(proxy_scheme, proxy_string)
        urlinfo = urlparse.urlparse(proxy_url)
        ans = {
            u'scheme': urlinfo.scheme,
            u'hostname': urlinfo.hostname,
            u'port': urlinfo.port,
            u'username': urlinfo.username,
            u'password': urlinfo.password,
        }
    except:
        return None
    return ans

USER_AGENT = 'Mozilla/5.0 (X11; U; Linux x86_64; en-US; rv:1.9.2.13) Gecko/20101210 Gentoo Firefox/3.6.13'
USER_AGENT_MOBILE = 'Mozilla/5.0 (Windows; U; Windows CE 5.1; rv:1.8.1a3) Gecko/20060610 Minimo/0.016'

def random_user_agent(choose=None):
    choices = [
        'Mozilla/5.0 (Windows NT 5.2; rv:2.0.1) Gecko/20100101 Firefox/4.0.1',
        'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:2.0.1) Gecko/20100101 Firefox/4.0.1',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.6; rv:2.0.1) Gecko/20100101 Firefox/4.0.1',
        'Mozilla/5.0 (Windows NT 6.1; rv:6.0) Gecko/20110814 Firefox/6.0',
        'Mozilla/5.0 (Windows NT 6.2; rv:9.0.1) Gecko/20100101 Firefox/9.0.1',
        'Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US) AppleWebKit/534.3 (KHTML, like Gecko) Chrome/6.0.472.63 Safari/534.3',
        'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-US) AppleWebKit/532.5 (KHTML, like Gecko) Chrome/4.0.249.78 Safari/532.5',
        'Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; WOW64; Trident/5.0)',
    ]
    if choose is None:
        choose = random.randint(0, len(choices)-1)
    return choices[choose]

def browser(honor_time=True, max_time=2, mobile_browser=False, user_agent=None):
    '''
    Create a mechanize browser for web scraping. The browser handles cookies,
    refresh requests and ignores robots.txt. Also uses proxy if available.

    :param honor_time: If True honors pause time in refresh requests
    :param max_time: Maximum time in seconds to wait during a refresh request
    '''
    from calibre.utils.browser import Browser
    opener = Browser()
    opener.set_handle_refresh(True, max_time=max_time, honor_time=honor_time)
    opener.set_handle_robots(False)
    if user_agent is None:
        user_agent = USER_AGENT_MOBILE if mobile_browser else USER_AGENT
    opener.addheaders = [('User-agent', user_agent)]
    proxies = get_proxies()
    to_add = {}
    http_proxy = proxies.get('http', None)
    if http_proxy:
        to_add['http'] = http_proxy
    https_proxy = proxies.get('https', None)
    if https_proxy:
        to_add['https'] = https_proxy
    if to_add:
        opener.set_proxies(to_add)

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
        self.cwd = os.getcwdu()
        os.chdir(self.path)
        return self.cwd

    def __exit__(self, *args):
        try:
            os.chdir(self.cwd)
        except:
            # The previous CWD no longer exists
            pass


def detect_ncpus():
    """Detects the number of effective CPUs in the system"""
    import multiprocessing
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
    except (ValueError, OverflowError):
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
    if ent in {'apos', 'squot'}: # squot is generated by some broken CMS software
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
    from calibre.utils.html5_entities import entity_map
    try:
        return check(entity_map[ent])
    except KeyError:
        pass
    from htmlentitydefs import name2codepoint
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

def replace_entities(raw, encoding='cp1252'):
    return _ent_pat.sub(partial(entity_to_unicode, encoding=encoding), raw)

def xml_replace_entities(raw, encoding='cp1252'):
    return _ent_pat.sub(partial(xml_entity_to_unicode, encoding=encoding), raw)

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

def as_unicode(obj, enc=preferred_encoding):
    if not isbytestring(obj):
        try:
            obj = unicode(obj)
        except:
            try:
                obj = str(obj)
            except:
                obj = repr(obj)
    return force_unicode(obj, enc=enc)

def url_slash_cleaner(url):
    '''
    Removes redundant /'s from url's.
    '''
    return re.sub(r'(?<!:)/{2,}', '/', url)

def get_download_filename(url, cookie_file=None):
    '''
    Get a local filename for a URL using the content disposition header
    Returns empty string if no content disposition header present
    '''
    from contextlib import closing
    from urllib2 import unquote as urllib2_unquote

    filename = ''

    br = browser()
    if cookie_file:
        from mechanize import MozillaCookieJar
        cj = MozillaCookieJar()
        cj.load(cookie_file)
        br.set_cookiejar(cj)

    last_part_name = ''
    try:
        with closing(br.open(url)) as r:
            last_part_name = r.geturl().split('/')[-1]
            disposition = r.info().get('Content-disposition', '')
            for p in disposition.split(';'):
                if 'filename' in p:
                    if '*=' in disposition:
                        parts = disposition.split('*=')[-1]
                        filename = parts.split('\'')[-1]
                    else:
                        filename = disposition.split('=')[-1]
                    if filename[0] in ('\'', '"'):
                        filename = filename[1:]
                    if filename[-1] in ('\'', '"'):
                        filename = filename[:-1]
                    filename = urllib2_unquote(filename)
                    break
    except:
        import traceback
        traceback.print_exc()

    if not filename:
        filename = last_part_name

    return filename

def human_readable(size, sep=' '):
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
    return size + sep + suffix

def remove_bracketed_text(src,
        brackets={u'(':u')', u'[':u']', u'{':u'}'}):
    from collections import Counter
    counts = Counter()
    buf = []
    src = force_unicode(src)
    rmap = dict([(v, k) for k, v in brackets.iteritems()])
    for char in src:
        if char in brackets:
            counts[char] += 1
        elif char in rmap:
            idx = rmap[char]
            if counts[idx] > 0:
                counts[idx] -= 1
        elif sum(counts.itervalues()) < 1:
            buf.append(char)
    return u''.join(buf)

def ipython(user_ns=None):
    from calibre.utils.ipython import ipython
    ipython(user_ns=user_ns)

