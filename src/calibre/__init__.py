''' E-book management software'''
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, re, time, warnings
from polyglot.builtins import codepoint_to_chr, hasenv, native_string_type
from math import floor
from functools import partial

if not hasenv('CALIBRE_SHOW_DEPRECATION_WARNINGS'):
    warnings.simplefilter('ignore', DeprecationWarning)
try:
    os.getcwd()
except OSError:
    os.chdir(os.path.expanduser('~'))

from calibre.constants import (iswindows, ismacos, islinux, isfrozen,
        isbsd, preferred_encoding, __appname__, __version__, __author__,
        plugins, filesystem_encoding, config_dir)
from calibre.startup import initialize_calibre
initialize_calibre()
from calibre.utils.icu import safe_chr
from calibre.prints import prints

if False:
    # Prevent pyflakes from complaining
    __appname__, islinux, __version__
    isfrozen, __author__, isbsd, config_dir, plugins

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
    if isinstance(raw, str):
        return raw
    return raw.decode(encoding, errors)


def patheq(p1, p2):
    p = os.path
    d = lambda x : p.normcase(p.normpath(p.realpath(p.normpath(x))))
    if not p1 or not p2:
        return False
    return d(p1) == d(p2)


def unicode_path(path, abs=False):
    if isinstance(path, bytes):
        path = path.decode(filesystem_encoding)
    if abs:
        path = os.path.abspath(path)
    return path


def osx_version():
    if ismacos:
        import platform
        src = platform.mac_ver()[0]
        m = re.match(r'(\d+)\.(\d+)\.(\d+)', src)
        if m:
            return int(m.group(1)), int(m.group(2)), int(m.group(3))


def confirm_config_name(name):
    return name + '_again'


_filename_sanitize_unicode = frozenset(('\\', '|', '?', '*', '<',        # no2to3
    '"', ':', '>', '+', '/') + tuple(map(codepoint_to_chr, range(32))))  # no2to3


def sanitize_file_name(name, substitute='_'):
    '''
    Sanitize the filename `name`. All invalid characters are replaced by `substitute`.
    The set of invalid characters is the union of the invalid characters in Windows,
    macOS and Linux. Also removes leading and trailing whitespace.
    **WARNING:** This function also replaces path separators, so only pass file names
    and not full paths to it.
    '''
    if isbytestring(name):
        name = name.decode(filesystem_encoding, 'replace')
    if isbytestring(substitute):
        substitute = substitute.decode(filesystem_encoding, 'replace')
    chars = (substitute if c in _filename_sanitize_unicode else c for c in name)
    one = ''.join(chars)
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


sanitize_file_name2 = sanitize_file_name_unicode = sanitize_file_name


class CommandLineError(Exception):
    pass


def setup_cli_handlers(logger, level):
    import logging
    if hasenv('CALIBRE_WORKER') and logger.handlers:
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
    if ismacos:
        name += '.dylib'
        if hasattr(sys, 'frameworks_dir'):
            return cdll.LoadLibrary(os.path.join(getattr(sys, 'frameworks_dir'), name))
        return cdll.LoadLibrary(name)
    return cdll.LoadLibrary(name+'.so')


def extract(path, dir):
    extractor = None
    # First use the file header to identify its type
    with open(path, 'rb') as f:
        id_ = f.read(3)
    if id_ == b'Rar':
        from calibre.utils.unrar import extract as rarextract
        extractor = rarextract
    elif id_.startswith(b'PK'):
        from calibre.libunzip import extract as zipextract
        extractor = zipextract
    elif id_.startswith(b'7z'):
        from calibre.utils.seven_zip import extract as seven_extract
        extractor = seven_extract
    if extractor is None:
        # Fallback to file extension
        ext = os.path.splitext(path)[1][1:].lower()
        if ext in ('zip', 'cbz', 'epub', 'oebzip'):
            from calibre.libunzip import extract as zipextract
            extractor = zipextract
        elif ext in ('cbr', 'rar'):
            from calibre.utils.unrar import extract as rarextract
            extractor = rarextract
        elif ext in ('cb7', '7z'):
            from calibre.utils.seven_zip import extract as seven_extract
            extractor = seven_extract
    if extractor is None:
        raise Exception('Unknown archive type')
    extractor(path, dir)


def get_proxies(debug=True):
    from polyglot.urllib import getproxies
    proxies = getproxies()
    for key, proxy in list(proxies.items()):
        if not proxy or '..' in proxy or key == 'auto':
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
            '(?:ptype://)?'
            '(?:(?P<user>\\w+):(?P<pass>.*)@)?'
            '(?P<host>[\\w\\-\\.]+)'
            '(?::(?P<port>\\d+))?').replace('ptype', typ)
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
    from polyglot.urllib import urlparse
    try:
        proxy_url = '%s://%s'%(proxy_scheme, proxy_string)
        urlinfo = urlparse(proxy_url)
        ans = {
            'scheme': urlinfo.scheme,
            'hostname': urlinfo.hostname,
            'port': urlinfo.port,
            'username': urlinfo.username,
            'password': urlinfo.password,
        }
    except Exception:
        return None
    return ans


def is_mobile_ua(ua):
    return 'Mobile/' in ua or 'Mobile ' in ua


def random_user_agent(choose=None, allow_ie=True):
    from calibre.utils.random_ua import common_user_agents, choose_randomly_by_popularity
    ua_list = common_user_agents()
    ua_list = tuple(x for x in ua_list if not is_mobile_ua(x))
    if not allow_ie:
        ua_list = tuple(x for x in ua_list if 'Trident/' not in x)
    if choose is not None:
        return ua_list[choose]
    return choose_randomly_by_popularity(ua_list)


def browser(honor_time=True, max_time=2, user_agent=None, verify_ssl_certificates=True, handle_refresh=True, **kw):
    '''
    Create a mechanize browser for web scraping. The browser handles cookies,
    refresh requests and ignores robots.txt. Also uses proxy if available.

    :param honor_time: If True honors pause time in refresh requests
    :param max_time: Maximum time in seconds to wait during a refresh request
    :param verify_ssl_certificates: If false SSL certificates errors are ignored
    '''
    from calibre.utils.browser import Browser
    opener = Browser(verify_ssl=verify_ssl_certificates)
    opener.set_handle_refresh(handle_refresh, max_time=max_time, honor_time=honor_time)
    opener.set_handle_robots(False)
    if user_agent is None:
        user_agent = random_user_agent(0, allow_ie=False)
    elif user_agent == 'common_words/based':
        from calibre.utils.random_ua import common_english_word_ua
        user_agent = common_english_word_ua()
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
        corrf = pheight / float(height)
        width, height = floor(corrf*width), pheight
    if width > pwidth:
        corrf = pwidth / float(width)
        width, height = pwidth, floor(corrf*height)
    if height > pheight:
        corrf = pheight / float(height)
        width, height = floor(corrf*width), pheight

    return scaled, int(width), int(height)


class CurrentDir:

    def __init__(self, path):
        self.path = path
        self.cwd = None

    def __enter__(self, *args):
        self.cwd = os.getcwd()
        os.chdir(self.path)
        return self.cwd

    def __exit__(self, *args):
        try:
            os.chdir(self.cwd)
        except OSError:
            # The previous CWD no longer exists
            pass


_ncpus = None


def detect_ncpus():
    global _ncpus
    if _ncpus is None:
        _ncpus = max(1, os.cpu_count() or 1)
    return _ncpus


relpath = os.path.relpath


def walk(dir):
    ''' A nice interface to os.walk '''
    for record in os.walk(dir):
        for f in record[-1]:
            yield os.path.join(record[0], f)


def strftime(fmt, t=None):
    ''' A version of strftime that returns unicode strings and tries to handle dates
    before 1900 '''
    if not fmt:
        return ''
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
        t = time.struct_time(t)
    ans = None
    if isinstance(fmt, bytes):
        fmt = fmt.decode('mbcs' if iswindows else 'utf-8', 'replace')
    ans = time.strftime(fmt, t)
    if early_year:
        ans = ans.replace('_early year hack##', str(orig_year))
    return ans


def my_unichr(num):
    try:
        return safe_chr(num)
    except (ValueError, OverflowError):
        return '?'


def entity_to_unicode(match, exceptions=[], encoding='cp1252',
        result_exceptions={}):
    '''
    :param match: A match object such that '&'+match.group(1)';' is the entity.

    :param exceptions: A list of entities to not convert (Each entry is the name of the entity, e.g. 'apos' or '#1234'

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
    if ent in {'apos', 'squot'}:  # squot is generated by some broken CMS software
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
            return check(bytes(bytearray((num,))).decode(encoding))
        except UnicodeDecodeError:
            return check(my_unichr(num))
    from calibre.ebooks.html_entities import html5_entities
    try:
        return check(html5_entities[ent])
    except KeyError:
        pass
    from polyglot.html_entities import name2codepoint
    try:
        return check(my_unichr(name2codepoint[ent]))
    except KeyError:
        return '&'+ent+';'


_ent_pat = re.compile(r'&(\S+?);')
xml_entity_to_unicode = partial(entity_to_unicode, result_exceptions={
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
    return isinstance(obj, bytes)


def force_unicode(obj, enc=preferred_encoding):
    if isbytestring(obj):
        try:
            obj = obj.decode(enc)
        except Exception:
            try:
                obj = obj.decode(filesystem_encoding if enc ==
                        preferred_encoding else preferred_encoding)
            except Exception:
                try:
                    obj = obj.decode('utf-8')
                except Exception:
                    obj = repr(obj)
                    if isbytestring(obj):
                        obj = obj.decode('utf-8')
    return obj


def as_unicode(obj, enc=preferred_encoding):
    if not isbytestring(obj):
        try:
            obj = str(obj)
        except Exception:
            try:
                obj = native_string_type(obj)
            except Exception:
                obj = repr(obj)
    return force_unicode(obj, enc=enc)


def url_slash_cleaner(url):
    '''
    Removes redundant /'s from url's.
    '''
    return re.sub(r'(?<!:)/{2,}', '/', url)


def human_readable(size, sep=' '):
    """ Convert a size in bytes into a human readable form """
    divisor, suffix = 1, "B"
    for i, candidate in enumerate(('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB')):
        if size < (1 << ((i + 1) * 10)):
            divisor, suffix = (1 << (i * 10)), candidate
            break
    size = str(float(size)/divisor)
    if size.find(".") > -1:
        size = size[:size.find(".")+2]
    if size.endswith('.0'):
        size = size[:-2]
    return size + sep + suffix


def ipython(user_ns=None):
    from calibre.utils.ipython import ipython
    ipython(user_ns=user_ns)


def fsync(fileobj):
    fileobj.flush()
    os.fsync(fileobj.fileno())
    if islinux and getattr(fileobj, 'name', None):
        # On Linux kernels after 5.1.9 and 4.19.50 using fsync without any
        # following activity causes Kindles to eject. Instead of fixing this in
        # the obvious way, which is to have the kernel send some harmless
        # filesystem activity after the FSYNC, the kernel developers seem to
        # think the correct solution is to disable FSYNC using a mount flag
        # which users will have to turn on manually. So instead we create some
        # harmless filesystem activity, and who cares about performance.
        # See https://bugs.launchpad.net/calibre/+bug/1834641
        # and https://bugzilla.kernel.org/show_bug.cgi?id=203973
        # To check for the existence of the bug, simply run:
        # python -c "p = '/run/media/kovid/Kindle/driveinfo.calibre'; f = open(p, 'r+b'); os.fsync(f.fileno());"
        # this will cause the Kindle to disconnect.
        try:
            os.utime(fileobj.name, None)
        except Exception:
            import traceback
            traceback.print_exc()
