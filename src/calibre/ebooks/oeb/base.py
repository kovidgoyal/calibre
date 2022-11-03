'''
Basic support for manipulating OEB 1.x/2.0 content and metadata.
'''

__license__   = 'GPL v3'
__copyright__ = '2008, Marshall T. Vandegrift <llasram@gmail.com>'
__docformat__ = 'restructuredtext en'

import os, re, logging, sys, numbers
from collections import defaultdict
from itertools import count
from operator import attrgetter

from lxml import etree, html
from calibre import force_unicode
from calibre.constants import filesystem_encoding, __version__
from calibre.translations.dynamic import translate
from calibre.utils.xml_parse import safe_xml_fromstring
from calibre.ebooks.chardet import xml_to_unicode
from calibre.ebooks.conversion.preprocess import CSSPreProcessor
from calibre import (isbytestring, as_unicode, get_types_map)
from calibre.ebooks.oeb.parse_utils import barename, XHTML_NS, namespace, XHTML, parse_html, NotHTML
from calibre.utils.cleantext import clean_xml_chars
from calibre.utils.short_uuid import uuid4
from polyglot.builtins import iteritems, string_or_bytes, itervalues, codepoint_to_chr
from polyglot.urllib import unquote as urlunquote, urldefrag, urljoin, urlparse, urlunparse
from calibre.utils.icu import numeric_sort_key

XML_NS       = 'http://www.w3.org/XML/1998/namespace'
OEB_DOC_NS   = 'http://openebook.org/namespaces/oeb-document/1.0/'
OPF1_NS      = 'http://openebook.org/namespaces/oeb-package/1.0/'
OPF2_NS      = 'http://www.idpf.org/2007/opf'
OPF_NSES     = {OPF1_NS, OPF2_NS}
DC09_NS      = 'http://purl.org/metadata/dublin_core'
DC10_NS      = 'http://purl.org/dc/elements/1.0/'
DC11_NS      = 'http://purl.org/dc/elements/1.1/'
DC_NSES      = {DC09_NS, DC10_NS, DC11_NS}
XSI_NS       = 'http://www.w3.org/2001/XMLSchema-instance'
DCTERMS_NS   = 'http://purl.org/dc/terms/'
NCX_NS       = 'http://www.daisy.org/z3986/2005/ncx/'
SVG_NS       = 'http://www.w3.org/2000/svg'
XLINK_NS     = 'http://www.w3.org/1999/xlink'
CALIBRE_NS   = 'http://calibre.kovidgoyal.net/2009/metadata'
RE_NS        = 'http://exslt.org/regular-expressions'
MBP_NS       = 'http://www.mobipocket.com'
EPUB_NS      = 'http://www.idpf.org/2007/ops'
MATHML_NS    = 'http://www.w3.org/1998/Math/MathML'

XPNSMAP      = {
        'h': XHTML_NS, 'o1': OPF1_NS, 'o2': OPF2_NS, 'd09': DC09_NS,
        'd10': DC10_NS, 'd11': DC11_NS, 'xsi': XSI_NS, 'dt': DCTERMS_NS,
        'ncx': NCX_NS, 'svg': SVG_NS, 'xl': XLINK_NS, 're': RE_NS,
        'mathml': MATHML_NS, 'mbp': MBP_NS, 'calibre': CALIBRE_NS,
        'epub':EPUB_NS
}

OPF1_NSMAP   = {'dc': DC11_NS, 'oebpackage': OPF1_NS}
OPF2_NSMAP   = {'opf': OPF2_NS, 'dc': DC11_NS, 'dcterms': DCTERMS_NS,
                'xsi': XSI_NS, 'calibre': CALIBRE_NS}


def XML(name):
    return f'{{{XML_NS}}}{name}'


def OPF(name):
    return f'{{{OPF2_NS}}}{name}'


def DC(name):
    return f'{{{DC11_NS}}}{name}'


def XSI(name):
    return f'{{{XSI_NS}}}{name}'


def DCTERMS(name):
    return f'{{{DCTERMS_NS}}}{name}'


def NCX(name):
    return f'{{{NCX_NS}}}{name}'


def SVG(name):
    return f'{{{SVG_NS}}}{name}'


def XLINK(name):
    return f'{{{XLINK_NS}}}{name}'


def CALIBRE(name):
    return f'{{{CALIBRE_NS}}}{name}'


_css_url_re = re.compile(r'url\s*\([\'"]{0,1}(.*?)[\'"]{0,1}\)', re.I)
_css_import_re = re.compile(r'@import "(.*?)"')
_archive_re = re.compile(r'[^ ]+')

# Tags that should not be self closed in epub output
self_closing_bad_tags = {'a', 'abbr', 'address', 'article', 'aside', 'audio', 'b',
'bdo', 'blockquote', 'body', 'button', 'cite', 'code', 'dd', 'del', 'details',
'dfn', 'div', 'dl', 'dt', 'em', 'fieldset', 'figcaption', 'figure', 'footer',
'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'header', 'hgroup', 'i', 'iframe', 'ins', 'kbd',
'label', 'legend', 'li', 'map', 'mark', 'meter', 'nav', 'ol', 'output', 'p',
'pre', 'progress', 'q', 'rp', 'rt', 'samp', 'section', 'select', 'small',
'span', 'strong', 'sub', 'summary', 'sup', 'textarea', 'time', 'ul', 'var',
'video', 'title', 'script', 'style'}


def css_text(x):
    ans = x.cssText
    if isinstance(ans, bytes):
        ans = ans.decode('utf-8', 'replace')
    return ans


def as_string_type(pat, for_unicode):
    if for_unicode:
        if isinstance(pat, bytes):
            pat = pat.decode('utf-8')
    else:
        if isinstance(pat, str):
            pat = pat.encode('utf-8')
    return pat


def self_closing_pat(for_unicode):
    attr = 'unicode_ans' if for_unicode else 'bytes_ans'
    ans = getattr(self_closing_pat, attr, None)
    if ans is None:
        sub = '|'.join(self_closing_bad_tags)
        template = r'<(?P<tag>%s)(?=[\s/])(?P<arg>[^>]*)/>'
        pat = template % sub
        pat = as_string_type(pat, for_unicode)
        ans = re.compile(pat, flags=re.IGNORECASE)
        setattr(self_closing_pat, attr, ans)
    return ans


def close_self_closing_tags(raw):
    for_unicode = isinstance(raw, str)
    repl = as_string_type(r'<\g<tag>\g<arg>></\g<tag>>', for_unicode)
    pat = self_closing_pat(for_unicode)
    return pat.sub(repl, raw)


def uuid_id():
    return 'u' + uuid4()


def itercsslinks(raw):
    for match in _css_url_re.finditer(raw):
        yield match.group(1), match.start(1)
    for match in _css_import_re.finditer(raw):
        yield match.group(1), match.start(1)


_link_attrs = set(html.defs.link_attrs) | {XLINK('href'), 'poster'}


def iterlinks(root, find_links_in_css=True):
    '''
    Iterate over all links in a OEB Document.

    :param root: A valid lxml.etree element.
    '''
    assert etree.iselement(root)

    for el in root.iter('*'):
        try:
            tag = barename(el.tag).lower()
        except Exception:
            continue
        attribs = el.attrib

        if tag == 'object':
            codebase = None
            # <object> tags have attributes that are relative to
            # codebase
            if 'codebase' in attribs:
                codebase = el.get('codebase')
                yield (el, 'codebase', codebase, 0)
            for attrib in 'classid', 'data':
                if attrib in attribs:
                    value = el.get(attrib)
                    if codebase is not None:
                        value = urljoin(codebase, value)
                    yield (el, attrib, value, 0)
            if 'archive' in attribs:
                for match in _archive_re.finditer(el.get('archive')):
                    value = match.group(0)
                    if codebase is not None:
                        value = urljoin(codebase, value)
                    yield (el, 'archive', value, match.start())
        else:
            for attr in attribs:
                if attr in _link_attrs:
                    yield (el, attr, attribs[attr], 0)

        if not find_links_in_css:
            continue
        if tag == 'style' and el.text:
            for match in _css_url_re.finditer(el.text):
                yield (el, None, match.group(1), match.start(1))
            for match in _css_import_re.finditer(el.text):
                yield (el, None, match.group(1), match.start(1))
        if 'style' in attribs:
            for match in _css_url_re.finditer(attribs['style']):
                yield (el, 'style', match.group(1), match.start(1))


def make_links_absolute(root, base_url):
    '''
    Make all links in the document absolute, given the
    ``base_url`` for the document (the full URL where the document
    came from)
    '''
    def link_repl(href):
        return urljoin(base_url, href)
    rewrite_links(root, link_repl)


def resolve_base_href(root):
    base_href = None
    basetags = root.xpath('//base[@href]|//h:base[@href]',
            namespaces=XPNSMAP)
    for b in basetags:
        base_href = b.get('href')
        b.drop_tree()
    if not base_href:
        return
    make_links_absolute(root, base_href, resolve_base_href=False)


def rewrite_links(root, link_repl_func, resolve_base_href=False):
    '''
    Rewrite all the links in the document.  For each link
    ``link_repl_func(link)`` will be called, and the return value
    will replace the old link.

    Note that links may not be absolute (unless you first called
    ``make_links_absolute()``), and may be internal (e.g.,
    ``'#anchor'``).  They can also be values like
    ``'mailto:email'`` or ``'javascript:expr'``.

    If the ``link_repl_func`` returns None, the attribute or
    tag text will be removed completely.
    '''
    from css_parser import replaceUrls, log, CSSParser
    log.setLevel(logging.WARN)
    log.raiseExceptions = False

    if resolve_base_href:
        resolve_base_href(root)
    for el, attrib, link, pos in iterlinks(root, find_links_in_css=False):
        new_link = link_repl_func(link.strip())
        if new_link == link:
            continue
        if new_link is None:
            # Remove the attribute or element content
            if attrib is None:
                el.text = ''
            else:
                del el.attrib[attrib]
            continue
        if attrib is None:
            new = el.text[:pos] + new_link + el.text[pos+len(link):]
            el.text = new
        else:
            cur = el.attrib[attrib]
            if not pos and len(cur) == len(link):
                # Most common case
                el.attrib[attrib] = new_link
            else:
                new = cur[:pos] + new_link + cur[pos+len(link):]
                el.attrib[attrib] = new

    parser = CSSParser(raiseExceptions=False, log=_css_logger,
            fetcher=lambda x:(None, ''))
    for el in root.iter(etree.Element):
        try:
            tag = el.tag
        except UnicodeDecodeError:
            continue

        if tag == XHTML('style') and el.text and \
                (_css_url_re.search(el.text) is not None or '@import' in
                        el.text):
            stylesheet = parser.parseString(el.text, validate=False)
            replaceUrls(stylesheet, link_repl_func)
            repl = css_text(stylesheet)
            el.text = '\n'+ clean_xml_chars(repl) + '\n'

        text = el.get('style')
        if text and _css_url_re.search(text) is not None:
            try:
                stext = parser.parseStyle(text, validate=False)
            except Exception:
                # Parsing errors are raised by css_parser
                continue
            replaceUrls(stext, link_repl_func)
            repl = css_text(stext).replace('\n', ' ').replace('\r',
                    ' ')
            el.set('style', repl)


types_map = get_types_map()
EPUB_MIME      = types_map['.epub']
XHTML_MIME     = types_map['.xhtml']
CSS_MIME       = types_map['.css']
NCX_MIME       = types_map['.ncx']
OPF_MIME       = types_map['.opf']
PAGE_MAP_MIME  = 'application/oebps-page-map+xml'
OEB_DOC_MIME   = 'text/x-oeb1-document'
OEB_CSS_MIME   = 'text/x-oeb1-css'
OPENTYPE_MIME  = types_map['.otf']
GIF_MIME       = types_map['.gif']
JPEG_MIME      = types_map['.jpeg']
PNG_MIME       = types_map['.png']
SVG_MIME       = types_map['.svg']
WEBP_MIME      = types_map['.webp']
BINARY_MIME    = 'application/octet-stream'

XHTML_CSS_NAMESPACE = '@namespace "%s";\n' % XHTML_NS

OEB_STYLES        = {CSS_MIME, OEB_CSS_MIME, 'text/x-oeb-css', 'xhtml/css'}
OEB_DOCS          = {XHTML_MIME, 'text/html', OEB_DOC_MIME,
                         'text/x-oeb-document'}
OEB_RASTER_IMAGES = {GIF_MIME, JPEG_MIME, PNG_MIME, WEBP_MIME}
OEB_IMAGES        = {GIF_MIME, JPEG_MIME, PNG_MIME, SVG_MIME}

MS_COVER_TYPE = 'other.ms-coverimage-standard'

ENTITY_RE     = re.compile(r'&([a-zA-Z_:][a-zA-Z0-9.-_:]+);')
COLLAPSE_RE   = re.compile(r'[ \t\r\n\v]+')
QNAME_RE      = re.compile(r'^[{][^{}]+[}][^{}]+$')
PREFIXNAME_RE = re.compile(r'^[^:]+[:][^:]+')
XMLDECL_RE    = re.compile(r'^\s*<[?]xml.*?[?]>')
CSSURL_RE     = re.compile(r'''url[(](?P<q>["']?)(?P<url>[^)]+)(?P=q)[)]''')


def element(parent, *args, **kwargs):
    if parent is not None:
        return etree.SubElement(parent, *args, **kwargs)
    return etree.Element(*args, **kwargs)


def prefixname(name, nsrmap):
    if not isqname(name):
        return name
    ns = namespace(name)
    if ns not in nsrmap:
        return name
    prefix = nsrmap[ns]
    if not prefix:
        return barename(name)
    return ':'.join((prefix, barename(name)))


def isprefixname(name):
    return name and PREFIXNAME_RE.match(name) is not None


def qname(name, nsmap):
    if not isprefixname(name):
        return name
    prefix, local = name.split(':', 1)
    if prefix not in nsmap:
        return name
    return f'{{{nsmap[prefix]}}}{local}'


def isqname(name):
    return name and QNAME_RE.match(name) is not None


def XPath(expr):
    return etree.XPath(expr, namespaces=XPNSMAP)


def xpath(elem, expr):
    return elem.xpath(expr, namespaces=XPNSMAP)


def xml2str(root, pretty_print=False, strip_comments=False, with_tail=True):
    if not strip_comments:
        # -- in comments trips up adobe digital editions
        for x in root.iterdescendants(etree.Comment):
            if x.text and '--' in x.text:
                x.text = x.text.replace('--', '__')
    ans = etree.tostring(root, encoding='utf-8', xml_declaration=True,
                          pretty_print=pretty_print, with_tail=with_tail)

    if strip_comments:
        ans = re.compile(br'<!--.*?-->', re.DOTALL).sub(b'', ans)

    return ans


def xml2text(elem, pretty_print=False, method='text'):
    return etree.tostring(elem, method=method, encoding='unicode', with_tail=False, pretty_print=pretty_print)


def escape_cdata(root):
    pat = re.compile(r'[<>&]')
    for elem in root.iterdescendants('{%s}style' % XHTML_NS, '{%s}script' % XHTML_NS):
        if elem.text and pat.search(elem.text) is not None:
            elem.text = etree.CDATA(elem.text.replace(']]>', r'\]\]\>'))


def serialize(data, media_type, pretty_print=False):
    if isinstance(data, etree._Element):
        is_oeb_doc = media_type in OEB_DOCS
        if is_oeb_doc:
            escape_cdata(data)
        ans = xml2str(data, pretty_print=pretty_print)
        if is_oeb_doc:
            # Convert self closing div|span|a|video|audio|iframe|etc tags
            # to normally closed ones, as they are interpreted
            # incorrectly by some browser based renderers
            ans = close_self_closing_tags(ans)
        return ans
    if isinstance(data, str):
        return data.encode('utf-8')
    if hasattr(data, 'cssText'):
        from calibre.ebooks.oeb.polish.utils import setup_css_parser_serialization
        setup_css_parser_serialization()
        data = data.cssText
        if isinstance(data, str):
            data = data.encode('utf-8')
        return data + b'\n'
    return b'' if data is None else bytes(data)


ASCII_CHARS   = frozenset(codepoint_to_chr(x) for x in range(128))
UNIBYTE_CHARS = frozenset(x.encode('ascii') for x in ASCII_CHARS)
USAFE         = ('ABCDEFGHIJKLMNOPQRSTUVWXYZ'
                 'abcdefghijklmnopqrstuvwxyz'
                 '0123456789' '_.-/~')
URL_SAFE      = frozenset(USAFE)
URL_SAFE_BYTES = frozenset(USAFE.encode('ascii'))
URL_UNSAFE = [ASCII_CHARS - URL_SAFE, UNIBYTE_CHARS - URL_SAFE_BYTES]
del USAFE


def urlquote(href):
    """ Quote URL-unsafe characters, allowing IRI-safe characters.
    That is, this function returns valid IRIs not valid URIs. In particular,
    IRIs can contain non-ascii characters.  """
    result = []
    isbytes = isinstance(href, bytes)
    unsafe = URL_UNSAFE[int(isbytes)]
    esc, join = "%%%02x", ''
    if isbytes:
        esc, join = esc.encode('ascii'), b''
    for char in href:
        if char in unsafe:
            char = esc % ord(char)
        result.append(char)
    return join.join(result)


def urlnormalize(href):
    """Convert a URL into normalized form, with all and only URL-unsafe
    characters URL quoted.
    """
    try:
        parts = urlparse(href)
    except ValueError as e:
        raise ValueError(f'Failed to parse the URL: {href!r} with underlying error: {as_unicode(e)}')
    if not parts.scheme or parts.scheme == 'file':
        path, frag = urldefrag(href)
        parts = ('', '', path, '', '', frag)
    parts = (part.replace('\\', '/') for part in parts)
    parts = (urlunquote(part) for part in parts)
    parts = (urlquote(part) for part in parts)
    return urlunparse(parts)


def extract(elem):
    """
    Removes this element from the tree, including its children and
    text.  The tail text is joined to the previous element or
    parent.
    """
    parent = elem.getparent()
    if parent is not None:
        if elem.tail:
            previous = elem.getprevious()
            if previous is None:
                parent.text = (parent.text or '') + elem.tail
            else:
                previous.tail = (previous.tail or '') + elem.tail
        parent.remove(elem)


class DummyHandler(logging.Handler):

    def __init__(self):
        logging.Handler.__init__(self, logging.WARNING)
        self.setFormatter(logging.Formatter('%(message)s'))
        self.log = None

    def emit(self, record):
        if self.log is not None:
            msg = self.format(record)
            f = self.log.error if record.levelno >= logging.ERROR \
                    else self.log.warn
            f(msg)


_css_logger = logging.getLogger('calibre.css')
_css_logger.setLevel(logging.WARNING)
_css_log_handler = DummyHandler()
_css_logger.addHandler(_css_log_handler)


class OEBError(Exception):
    """Generic OEB-processing error."""
    pass


class NullContainer:
    """An empty container.

    For use with book formats which do not support container-like access.
    """

    def __init__(self, log):
        self.log = log

    def read(self, path):
        raise OEBError('Attempt to read from NullContainer')

    def write(self, path):
        raise OEBError('Attempt to write to NullContainer')

    def exists(self, path):
        return False

    def namelist(self):
        return []


class DirContainer:
    """Filesystem directory container."""

    def __init__(self, path, log, ignore_opf=False):
        self.log = log
        if isbytestring(path):
            path = path.decode(filesystem_encoding)
        self.opfname = None
        ext = os.path.splitext(path)[1].lower()
        if ext == '.opf':
            self.opfname = os.path.basename(path)
            self.rootdir = os.path.dirname(path)
            return
        self.rootdir = path
        if not ignore_opf:
            for path in self.namelist():
                ext = os.path.splitext(path)[1].lower()
                if ext == '.opf':
                    self.opfname = path
                    return

    def _unquote(self, path):
        # unquote must run on a bytestring and will return a bytestring
        # If it runs on a unicode object, it returns a double encoded unicode
        # string: unquote(u'%C3%A4') != unquote(b'%C3%A4').decode('utf-8')
        # and the latter is correct
        if isinstance(path, str):
            path = path.encode('utf-8')
        return urlunquote(path).decode('utf-8')

    def read(self, path):
        if path is None:
            path = self.opfname
        path = os.path.join(self.rootdir, self._unquote(path))
        with lopen(path, 'rb') as f:
            return f.read()

    def write(self, path, data):
        path = os.path.join(self.rootdir, self._unquote(path))
        dir = os.path.dirname(path)
        if not os.path.isdir(dir):
            os.makedirs(dir)
        with lopen(path, 'wb') as f:
            return f.write(data)

    def exists(self, path):
        if not path:
            return False
        try:
            path = os.path.join(self.rootdir, self._unquote(path))
        except ValueError:  # Happens if path contains quoted special chars
            return False
        try:
            return os.path.isfile(path)
        except UnicodeEncodeError:
            # On linux, if LANG is unset, the os.stat call tries to encode the
            # unicode path using ASCII
            # To replicate try:
            # LANG=en_US.ASCII python -c "import os; os.stat(u'Espa\xf1a')"
            return os.path.isfile(path.encode(filesystem_encoding))

    def namelist(self):
        names = []
        base = self.rootdir
        for root, dirs, files in os.walk(base):
            for fname in files:
                fname = os.path.join(root, fname)
                if isinstance(fname, bytes):
                    try:
                        fname = fname.decode(filesystem_encoding)
                    except Exception:
                        try:
                            fname = fname.decode('utf-8')
                        except Exception:
                            continue
                fname = fname.replace('\\', '/')
                names.append(fname)
        return names


class Metadata:
    """A collection of OEB data model metadata.

    Provides access to the list of items associated with a particular metadata
    term via the term's local name using either Python container or attribute
    syntax.  Return an empty list for any terms with no currently associated
    metadata items.
    """

    DC_TERMS      = {'contributor', 'coverage', 'creator', 'date',
                         'description', 'format', 'identifier', 'language',
                         'publisher', 'relation', 'rights', 'source',
                         'subject', 'title', 'type'}
    CALIBRE_TERMS = {'series', 'series_index', 'rating', 'timestamp',
                         'publication_type', 'title_sort'}
    OPF_ATTRS     = {'role': OPF('role'), 'file-as': OPF('file-as'),
                     'scheme': OPF('scheme'), 'event': OPF('event'),
                     'type': XSI('type'), 'lang': XML('lang'), 'id': 'id'}
    OPF1_NSMAP    = {'dc': DC11_NS, 'oebpackage': OPF1_NS}
    OPF2_NSMAP    = {'opf': OPF2_NS, 'dc': DC11_NS, 'dcterms': DCTERMS_NS,
                     'xsi': XSI_NS, 'calibre': CALIBRE_NS}

    class Item:
        """An item of OEB data model metadata.

        The metadata term or name may be accessed via the :attr:`term` or
        :attr:`name` attributes.  The metadata value or content may be accessed
        via the :attr:`value` or :attr:`content` attributes, or via Unicode or
        string representations of the object.

        OEB data model metadata attributes may be accessed either via their
        fully-qualified names using the Python container access syntax, or via
        their local names using Python attribute syntax.  Only attributes
        allowed by the OPF 2.0 specification are supported.
        """
        class Attribute:
            """Smart accessor for allowed OEB metadata item attributes."""

            def __init__(self, attr, allowed=None):
                if not callable(attr):
                    attr_, attr = attr, lambda term: attr_
                self.attr = attr
                self.allowed = allowed

            def term_attr(self, obj):
                term = obj.term
                if namespace(term) != DC11_NS:
                    term = OPF('meta')
                allowed = self.allowed
                if allowed is not None and term not in allowed:
                    raise AttributeError(
                        'attribute {!r} not valid for metadata term {!r}'.format(
                            self.attr(term), barename(obj.term)))
                return self.attr(term)

            def __get__(self, obj, cls):
                if obj is None:
                    return None
                return obj.attrib.get(self.term_attr(obj), '')

            def __set__(self, obj, value):
                obj.attrib[self.term_attr(obj)] = value

        def __init__(self, term, value, attrib={}, nsmap={}, **kwargs):
            self.attrib = attrib = dict(attrib)
            self.nsmap = nsmap = dict(nsmap)
            attrib.update(kwargs)
            if namespace(term) == OPF2_NS:
                term = barename(term)
            ns = namespace(term)
            local = barename(term).lower()
            if local in Metadata.DC_TERMS and (not ns or ns in DC_NSES):
                # Anything looking like Dublin Core is coerced
                term = DC(local)
            elif local in Metadata.CALIBRE_TERMS and ns in (CALIBRE_NS, ''):
                # Ditto for Calibre-specific metadata
                term = CALIBRE(local)
            self.term = term
            self.value = value
            for attr, value in tuple(iteritems(attrib)):
                if isprefixname(value):
                    attrib[attr] = qname(value, nsmap)
                nsattr = Metadata.OPF_ATTRS.get(attr, attr)
                if nsattr == OPF('scheme') and namespace(term) != DC11_NS:
                    # The opf:meta element takes @scheme, not @opf:scheme
                    nsattr = 'scheme'
                if attr != nsattr:
                    attrib[nsattr] = attrib.pop(attr)

        @property
        def name(self):
            return self.term

        @property
        def content(self):
            return self.value

        @content.setter
        def content(self, value):
            self.value = value

        scheme  = Attribute(lambda term: 'scheme' if
                            term == OPF('meta') else OPF('scheme'),
                            [DC('identifier'), OPF('meta')])
        file_as = Attribute(OPF('file-as'), [DC('creator'), DC('contributor'),
                                             DC('title')])
        role    = Attribute(OPF('role'), [DC('creator'), DC('contributor')])
        event   = Attribute(OPF('event'), [DC('date')])
        id      = Attribute('id')
        type    = Attribute(XSI('type'), [DC('date'), DC('format'),
                                          DC('type')])
        lang    = Attribute(XML('lang'), [DC('contributor'), DC('coverage'),
                                          DC('creator'), DC('publisher'),
                                          DC('relation'), DC('rights'),
                                          DC('source'), DC('subject'),
                                          OPF('meta')])

        def __getitem__(self, key):
            return self.attrib[key]

        def __setitem__(self, key, value):
            self.attrib[key] = value

        def __contains__(self, key):
            return key in self.attrib

        def get(self, key, default=None):
            return self.attrib.get(key, default)

        def __repr__(self):
            return 'Item(term=%r, value=%r, attrib=%r)' \
                % (barename(self.term), self.value, self.attrib)

        def __str__(self):
            return as_unicode(self.value)

        def to_opf1(self, dcmeta=None, xmeta=None, nsrmap={}):
            attrib = {}
            for key, value in self.attrib.items():
                if namespace(key) == OPF2_NS:
                    key = barename(key)
                attrib[key] = prefixname(value, nsrmap)
            if namespace(self.term) == DC11_NS:
                name = DC(icu_title(barename(self.term)))
                elem = element(dcmeta, name, attrib=attrib)
                elem.text = self.value
            else:
                elem = element(xmeta, 'meta', attrib=attrib)
                elem.attrib['name'] = prefixname(self.term, nsrmap)
                elem.attrib['content'] = prefixname(self.value, nsrmap)
            return elem

        def to_opf2(self, parent=None, nsrmap={}):
            attrib = {}
            for key, value in self.attrib.items():
                attrib[key] = prefixname(value, nsrmap)
            if namespace(self.term) == DC11_NS:
                elem = element(parent, self.term, attrib=attrib)
                try:
                    elem.text = self.value
                except:
                    elem.text = repr(self.value)
            else:
                elem = element(parent, OPF('meta'), attrib=attrib)
                elem.attrib['name'] = prefixname(self.term, nsrmap)
                elem.attrib['content'] = prefixname(self.value, nsrmap)
            return elem

    def __init__(self, oeb):
        self.oeb = oeb
        self.items = defaultdict(list)
        self.primary_writing_mode = None

    def add(self, term, value, attrib={}, nsmap={}, **kwargs):
        """Add a new metadata item."""
        item = self.Item(term, value, attrib, nsmap, **kwargs)
        items = self.items[barename(item.term)]
        items.append(item)
        return item

    def iterkeys(self):
        yield from self.items
    __iter__ = iterkeys

    def clear(self, key):
        l = self.items[key]
        for x in list(l):
            l.remove(x)

    def filter(self, key, predicate):
        l = self.items[key]
        for x in list(l):
            if predicate(x):
                l.remove(x)

    def __getitem__(self, key):
        return self.items[key]

    def __contains__(self, key):
        return key in self.items

    def __getattr__(self, term):
        return self.items[term]

    @property
    def _nsmap(self):
        nsmap = {}
        for term in self.items:
            for item in self.items[term]:
                nsmap.update(item.nsmap)
        return nsmap

    @property
    def _opf1_nsmap(self):
        nsmap = self._nsmap
        for key, value in nsmap.items():
            if value in OPF_NSES or value in DC_NSES:
                del nsmap[key]
        return nsmap

    @property
    def _opf2_nsmap(self):
        nsmap = self._nsmap
        nsmap.update(OPF2_NSMAP)
        return nsmap

    def to_opf1(self, parent=None):
        nsmap = self._opf1_nsmap
        nsrmap = {value: key for key, value in iteritems(nsmap)}
        elem = element(parent, 'metadata', nsmap=nsmap)
        dcmeta = element(elem, 'dc-metadata', nsmap=OPF1_NSMAP)
        xmeta = element(elem, 'x-metadata')
        for term in self.items:
            for item in self.items[term]:
                item.to_opf1(dcmeta, xmeta, nsrmap=nsrmap)
        if 'ms-chaptertour' not in self.items:
            chaptertour = self.Item('ms-chaptertour', 'chaptertour')
            chaptertour.to_opf1(dcmeta, xmeta, nsrmap=nsrmap)
        return elem

    def to_opf2(self, parent=None):
        nsmap = self._opf2_nsmap
        nsrmap = {value: key for key, value in iteritems(nsmap)}
        elem = element(parent, OPF('metadata'), nsmap=nsmap)
        for term in self.items:
            for item in self.items[term]:
                item.to_opf2(elem, nsrmap=nsrmap)
        if self.primary_writing_mode:
            elem.append(elem.makeelement(OPF('meta'), attrib={'name':'primary-writing-mode', 'content':self.primary_writing_mode}))
        return elem


class Manifest:
    """Collection of files composing an OEB data model book.

    Provides access to the content of the files composing the book and
    attributes associated with those files, including their internal paths,
    unique identifiers, and MIME types.

    Itself acts as a :class:`set` of manifest items, and provides the following
    instance data member for dictionary-like access:

    :attr:`ids`: A dictionary in which the keys are the unique identifiers of
        the manifest items and the values are the items themselves.
    :attr:`hrefs`: A dictionary in which the keys are the internal paths of the
        manifest items and the values are the items themselves.
    """

    class Item:
        """An OEB data model book content file.

        Provides the following data members for accessing the file content and
        metadata associated with this particular file.

        :attr:`id`: Unique identifier.
        :attr:`href`: Book-internal path.
        :attr:`media_type`: MIME type of the file content.
        :attr:`fallback`: Unique id of any fallback manifest item associated
            with this manifest item.
        :attr:`spine_position`: Display/reading order index for book textual
            content.  `None` for manifest items which are not part of the
            book's textual content.
        :attr:`linear`: `True` for textual content items which are part of the
            primary linear reading order and `False` for textual content items
            which are not (such as footnotes).  Meaningless for items which
            have a :attr:`spine_position` of `None`.
        """

        def __init__(self, oeb, id, href, media_type,
                     fallback=None, loader=str, data=None):
            if href:
                href = str(href)
            self.oeb = oeb
            self.id = id
            self.href = self.path = urlnormalize(href)
            self.media_type = media_type
            self.fallback = fallback
            self.override_css_fetch = None
            self.resolve_css_imports = True
            self.spine_position = None
            self.linear = True
            if loader is None and data is None:
                loader = oeb.container.read
            self._loader = loader
            self._data = data

        def __repr__(self):
            return 'Item(id=%r, href=%r, media_type=%r)' \
                % (self.id, self.href, self.media_type)

        # Parsing {{{
        def _parse_xml(self, data):
            if not data:
                return
            data = xml_to_unicode(data, strip_encoding_pats=True,
                    assume_utf8=True, resolve_entities=True)[0]
            return safe_xml_fromstring(data)

        def _parse_xhtml(self, data):
            orig_data = data
            fname = urlunquote(self.href)
            self.oeb.log.debug('Parsing', fname, '...')
            self.oeb.html_preprocessor.current_href = self.href
            try:
                data = parse_html(data, log=self.oeb.log,
                        decoder=self.oeb.decode,
                        preprocessor=self.oeb.html_preprocessor,
                        filename=fname, non_html_file_tags={'ncx'})
            except NotHTML:
                return self._parse_xml(orig_data)
            return data

        def _parse_txt(self, data):
            has_html = '<html>'
            if isinstance(data, bytes):
                has_html = has_html.encode('ascii')
            if has_html in data:
                return self._parse_xhtml(data)

            self.oeb.log.debug('Converting', self.href, '...')

            from calibre.ebooks.txt.processor import convert_markdown

            title = self.oeb.metadata.title
            if title:
                title = str(title[0])
            else:
                title = _('Unknown')

            return self._parse_xhtml(convert_markdown(data, title=title))

        def _parse_css(self, data):
            from css_parser import CSSParser, log, resolveImports
            from css_parser.css import CSSRule
            log.setLevel(logging.WARN)
            log.raiseExceptions = False
            self.oeb.log.debug('Parsing', self.href, '...')
            data = self.oeb.decode(data)
            data = self.oeb.css_preprocessor(data, add_namespace=False)
            parser = CSSParser(loglevel=logging.WARNING,
                               fetcher=self.override_css_fetch or self._fetch_css,
                               log=_css_logger)
            data = parser.parseString(data, href=self.href, validate=False)
            if self.resolve_css_imports:
                data = resolveImports(data)
            for rule in tuple(data.cssRules.rulesOfType(CSSRule.PAGE_RULE)):
                data.cssRules.remove(rule)
            return data

        def _fetch_css(self, path):
            hrefs = self.oeb.manifest.hrefs
            if path not in hrefs:
                self.oeb.logger.warn('CSS import of missing file %r' % path)
                return (None, None)
            item = hrefs[path]
            if item.media_type not in OEB_STYLES:
                self.oeb.logger.warn('CSS import of non-CSS file %r' % path)
                return (None, None)
            data = item.data.cssText
            enc = None if isinstance(data, str) else 'utf-8'
            return (enc, data)

        # }}}

        @property
        def data(self):
            """Provides MIME type sensitive access to the manifest
            entry's associated content.

            - XHTML, HTML, and variant content is parsed as necessary to
              convert and return as an lxml.etree element in the XHTML
              namespace.
            - XML content is parsed and returned as an lxml.etree element.
            - CSS and CSS-variant content is parsed and returned as a css_parser
              CSS DOM stylesheet.
            - All other content is returned as a :class:`str` or :class:`bytes`
              object with no special parsing.
            """
            data = self._data
            if data is None:
                if self._loader is None:
                    return None
                data = self._loader(getattr(self, 'html_input_href',
                    self.href))
            try:
                mt = self.media_type.lower()
            except Exception:
                mt = 'application/octet-stream'
            if not isinstance(data, string_or_bytes):
                pass  # already parsed
            elif mt in OEB_DOCS:
                data = self._parse_xhtml(data)
            elif mt[-4:] in ('+xml', '/xml'):
                data = self._parse_xml(data)
            elif mt in OEB_STYLES:
                data = self._parse_css(data)
            elif mt == 'text/plain':
                self.oeb.log.warn('%s contains data in TXT format'%self.href,
                        'converting to HTML')
                data = self._parse_txt(data)
                self.media_type = XHTML_MIME
            self._data = data
            return data

        @data.setter
        def data(self, value):
            self._data = value

        @data.deleter
        def data(self):
            self._data = None

        def reparse_css(self):
            self._data = self._parse_css(str(self))

        def unload_data_from_memory(self, memory=None):
            if isinstance(self._data, bytes):
                if memory is None:
                    from calibre.ptempfile import PersistentTemporaryFile
                    pt = PersistentTemporaryFile(suffix='_oeb_base_mem_unloader.img')
                    with pt:
                        pt.write(self._data)
                    self.oeb._temp_files.append(pt.name)

                    def loader(*args):
                        with open(pt.name, 'rb') as f:
                            ans = f.read()
                        os.remove(pt.name)
                        return ans
                    self._loader = loader
                else:
                    def loader2(*args):
                        with open(memory, 'rb') as f:
                            ans = f.read()
                        return ans
                    self._loader = loader2
                self._data = None

        @property
        def unicode_representation(self):
            data = self.data
            if isinstance(data, etree._Element):
                return xml2text(data, pretty_print=self.oeb.pretty_print)
            if isinstance(data, str):
                return data
            if hasattr(data, 'cssText'):
                return css_text(data)
            return str(data)

        @property
        def bytes_representation(self):
            return serialize(self.data, self.media_type, pretty_print=self.oeb.pretty_print)

        def __str__(self):
            return self.unicode_representation

        def __eq__(self, other):
            return self is other

        def __ne__(self, other):
            return self is not other

        def __hash__(self):
            return id(self)

        @property
        def sort_key(self):
            href = self.href
            if isinstance(href, bytes):
                href = force_unicode(href)
            sp = self.spine_position if isinstance(self.spine_position, numbers.Number) else sys.maxsize
            return sp, (self.media_type or '').lower(), numeric_sort_key(href), self.id

        def relhref(self, href):
            """Convert the URL provided in :param:`href` from a book-absolute
            reference to a reference relative to this manifest item.
            """
            return rel_href(self.href, href)

        def abshref(self, href):
            """Convert the URL provided in :param:`href` from a reference
            relative to this manifest item to a book-absolute reference.
            """
            try:
                purl = urlparse(href)
            except ValueError:
                return href
            scheme = purl.scheme
            if scheme and scheme != 'file':
                return href
            purl = list(purl)
            purl[0] = ''
            href = urlunparse(purl)
            path, frag = urldefrag(href)
            if not path:
                if frag:
                    return '#'.join((self.href, frag))
                else:
                    return self.href
            if '/' not in self.href:
                return href
            dirname = os.path.dirname(self.href)
            href = os.path.join(dirname, href)
            href = os.path.normpath(href).replace('\\', '/')
            return href

    def __init__(self, oeb):
        self.oeb = oeb
        self.items = set()
        self.ids = {}
        self.hrefs = {}

    def add(self, id, href, media_type, fallback=None, loader=None, data=None):
        """Add a new item to the book manifest.

        The item's :param:`id`, :param:`href`, and :param:`media_type` are all
        required.  A :param:`fallback` item-id is required for any items with a
        MIME type which is not one of the OPS core media types.  Either the
        item's data itself may be provided with :param:`data`, or a loader
        function for the data may be provided with :param:`loader`, or the
        item's data may later be set manually via the :attr:`data` attribute.
        """
        item = self.Item(
            self.oeb, id, href, media_type, fallback, loader, data)
        self.items.add(item)
        self.ids[item.id] = item
        self.hrefs[item.href] = item
        return item

    def remove(self, item):
        """Removes :param:`item` from the manifest."""
        if item in self.ids:
            item = self.ids[item]
        del self.ids[item.id]
        if item.href in self.hrefs:
            del self.hrefs[item.href]
        self.items.remove(item)
        if item in self.oeb.spine:
            self.oeb.spine.remove(item)

    def remove_duplicate_item(self, item):
        if item in self.ids:
            item = self.ids[item]
        del self.ids[item.id]
        self.items.remove(item)

    def generate(self, id=None, href=None):
        """Generate a new unique identifier and/or internal path for use in
        creating a new manifest item, using the provided :param:`id` and/or
        :param:`href` as bases.

        Returns an two-tuple of the new id and path.  If either :param:`id` or
        :param:`href` are `None` then the corresponding item in the return
        tuple will also be `None`.
        """
        if id is not None:
            base = id
            index = 1
            while id in self.ids:
                id = base + str(index)
                index += 1
        if href is not None:
            href = urlnormalize(href)
            base, ext = os.path.splitext(href)
            index = 1
            lhrefs = {x.lower() for x in self.hrefs}
            while href.lower() in lhrefs:
                href = base + str(index) + ext
                index += 1
        return id, str(href)

    def __iter__(self):
        yield from self.items

    def __len__(self):
        return len(self.items)

    def values(self):
        return list(self.items)

    def __contains__(self, item):
        return item in self.items

    def to_opf1(self, parent=None):
        elem = element(parent, 'manifest')
        for item in self.items:
            media_type = item.media_type
            if media_type in OEB_DOCS:
                media_type = OEB_DOC_MIME
            elif media_type in OEB_STYLES:
                media_type = OEB_CSS_MIME
            attrib = {'id': item.id, 'href': urlunquote(item.href),
                      'media-type': media_type}
            if item.fallback:
                attrib['fallback'] = item.fallback
            element(elem, 'item', attrib=attrib)
        return elem

    def to_opf2(self, parent=None):
        elem = element(parent, OPF('manifest'))
        for item in sorted(self.items, key=attrgetter('sort_key')):
            media_type = item.media_type
            if media_type in OEB_DOCS:
                media_type = XHTML_MIME
            elif media_type in OEB_STYLES:
                media_type = CSS_MIME
            attrib = {'id': item.id, 'href': urlunquote(item.href),
                      'media-type': media_type}
            if item.fallback:
                attrib['fallback'] = item.fallback
            element(elem, OPF('item'), attrib=attrib)
        return elem

    @property
    def main_stylesheet(self):
        ans = getattr(self, '_main_stylesheet', None)
        if ans is None:
            for item in self:
                if item.media_type.lower() in OEB_STYLES:
                    ans = item
                    break
        return ans

    @main_stylesheet.setter
    def main_stylesheet(self, item):
        self._main_stylesheet = item


class Spine:
    """Collection of manifest items composing an OEB data model book's main
    textual content.

    The spine manages which manifest items compose the book's main textual
    content and the sequence in which they appear.  Provides Python container
    access as a list-like object.
    """

    def __init__(self, oeb):
        self.oeb = oeb
        self.items = []
        self.page_progression_direction = None

    def _linear(self, linear):
        if isinstance(linear, string_or_bytes):
            linear = linear.lower()
        if linear is None or linear in ('yes', 'true'):
            linear = True
        elif linear in ('no', 'false'):
            linear = False
        return linear

    def add(self, item, linear=None):
        """Append :param:`item` to the end of the `Spine`."""
        item.linear = self._linear(linear)
        item.spine_position = len(self.items)
        self.items.append(item)
        return item

    def insert(self, index, item, linear):
        """Insert :param:`item` at position :param:`index` in the `Spine`."""
        item.linear = self._linear(linear)
        item.spine_position = index
        self.items.insert(index, item)
        for i in range(index, len(self.items)):
            self.items[i].spine_position = i
        return item

    def remove(self, item):
        """Remove :param:`item` from the `Spine`."""
        index = item.spine_position
        self.items.pop(index)
        for i in range(index, len(self.items)):
            self.items[i].spine_position = i
        item.spine_position = None

    def index(self, item):
        for i, x in enumerate(self):
            if item == x:
                return i
        return -1

    def __iter__(self):
        yield from self.items

    def __getitem__(self, index):
        return self.items[index]

    def __len__(self):
        return len(self.items)

    def __contains__(self, item):
        return (item in self.items)

    def to_opf1(self, parent=None):
        elem = element(parent, 'spine')
        for item in self.items:
            if item.linear:
                element(elem, 'itemref', attrib={'idref': item.id})
        return elem

    def to_opf2(self, parent=None):
        elem = element(parent, OPF('spine'))
        for item in self.items:
            attrib = {'idref': item.id}
            if not item.linear:
                attrib['linear'] = 'no'
            element(elem, OPF('itemref'), attrib=attrib)
        return elem


class Guide:
    """Collection of references to standard frequently-occurring sections
    within an OEB data model book.

    Provides dictionary-like access, in which the keys are the OEB reference
    type identifiers and the values are `Reference` objects.
    """

    class Reference:
        """Reference to a standard book section.

        Provides the following instance data members:

        :attr:`type`: Reference type identifier, as chosen from the list
            allowed in the OPF 2.0 specification.
        :attr:`title`: Human-readable section title.
        :attr:`href`: Book-internal URL of the referenced section.  May include
            a fragment identifier.
        """
        _TYPES_TITLES = [('cover', __('Cover')),
                         ('title-page', __('Title page')),
                         ('toc', __('Table of Contents')),
                         ('index', __('Index')),
                         ('glossary', __('Glossary')),
                         ('acknowledgements', __('Acknowledgements')),
                         ('bibliography', __('Bibliography')),
                         ('colophon', __('Colophon')),
                         ('copyright-page', __('Copyright')),
                         ('dedication', __('Dedication')),
                         ('epigraph', __('Epigraph')),
                         ('foreword', __('Foreword')),
                         ('loi', __('List of illustrations')),
                         ('lot', __('List of tables')),
                         ('notes', __('Notes')),
                         ('preface', __('Preface')),
                         ('text', __('Main text'))]
        TITLES = dict(_TYPES_TITLES)
        TYPES = frozenset(TITLES)
        ORDER = {t: i for i, (t, _) in enumerate(_TYPES_TITLES)}

        def __init__(self, oeb, type, title, href):
            self.oeb = oeb
            if type.lower() in self.TYPES:
                type = type.lower()
            elif type not in self.TYPES and \
                 not type.startswith('other.'):
                type = 'other.' + type
            if not title and type in self.TITLES:
                title = oeb.translate(self.TITLES[type])
            self.type = type
            self.title = title
            self.href = urlnormalize(href)

        def __repr__(self):
            return 'Reference(type=%r, title=%r, href=%r)' \
                % (self.type, self.title, self.href)

        @property
        def item(self):
            """The manifest item associated with this reference."""
            path = urldefrag(self.href)[0]
            hrefs = self.oeb.manifest.hrefs
            return hrefs.get(path, None)

    def __init__(self, oeb):
        self.oeb = oeb
        self.refs = {}

    def add(self, type, title, href):
        """Add a new reference to the `Guide`."""
        if href:
            href = str(href)
        ref = self.Reference(self.oeb, type, title, href)
        self.refs[type] = ref
        return ref

    def remove(self, type):
        return self.refs.pop(type, None)

    def remove_by_href(self, href):
        remove = [r for r, i in iteritems(self.refs) if i.href == href]
        for r in remove:
            self.remove(r)

    def iterkeys(self):
        yield from self.refs
    __iter__ = iterkeys

    def values(self):
        return sorted(itervalues(self.refs), key=lambda ref: ref.ORDER.get(ref.type, 10000))

    def items(self):
        yield from self.refs.items()

    def __getitem__(self, key):
        return self.refs[key]

    def get(self, key):
        return self.refs.get(key)

    def __delitem__(self, key):
        del self.refs[key]

    def __contains__(self, key):
        return key in self.refs

    def __len__(self):
        return len(self.refs)

    def to_opf1(self, parent=None):
        elem = element(parent, 'guide')
        for ref in self.refs.values():
            attrib = {'type': ref.type, 'href': urlunquote(ref.href)}
            if ref.title:
                attrib['title'] = ref.title
            element(elem, 'reference', attrib=attrib)
        return elem

    def to_opf2(self, parent=None):
        if not len(self):
            return
        elem = element(parent, OPF('guide'))
        for ref in self.refs.values():
            attrib = {'type': ref.type, 'href': urlunquote(ref.href)}
            if ref.title:
                attrib['title'] = ref.title
            element(elem, OPF('reference'), attrib=attrib)
        return elem


class TOC:
    """Represents a hierarchical table of contents or navigation tree for
    accessing arbitrary semantic sections within an OEB data model book.

    Acts as a node within the navigation tree.  Provides list-like access to
    sub-nodes.  Provides the follow node instance data attributes:

    :attr:`title`: The title of this navigation node.
    :attr:`href`: Book-internal URL referenced by this node.
    :attr:`klass`: Optional semantic class referenced by this node.
    :attr:`id`: Option unique identifier for this node.
    :attr:`author`: Optional author attribution for periodicals <mbp:>
    :attr:`description`: Optional description attribute for periodicals <mbp:>
    :attr:`toc_thumbnail`: Optional toc thumbnail image
    """

    def __init__(self, title=None, href=None, klass=None, id=None,
            play_order=None, author=None, description=None, toc_thumbnail=None):
        self.title = title
        self.href = urlnormalize(href) if href else href
        self.klass = klass
        self.id = id
        self.nodes = []
        self.play_order = 0
        if play_order is None:
            play_order = self.next_play_order()
        self.play_order = play_order
        self.author = author
        self.description = description
        self.toc_thumbnail = toc_thumbnail

    def add(self, title, href, klass=None, id=None, play_order=0, author=None, description=None, toc_thumbnail=None):
        """Create and return a new sub-node of this node."""
        node = TOC(title, href, klass, id, play_order, author, description, toc_thumbnail)
        self.nodes.append(node)
        return node

    def remove(self, node):
        for child in self.nodes:
            if child is node:
                self.nodes.remove(child)
                return True
            else:
                if child.remove(node):
                    return True
        return False

    def iter(self):
        """Iterate over this node and all descendants in depth-first order."""
        yield self
        for child in self.nodes:
            yield from child.iter()

    def count(self):
        return len(list(self.iter())) - 1

    def next_play_order(self):
        entries = [x.play_order for x in self.iter()]
        base = max(entries) if entries else 0
        return base+1

    def has_href(self, href):
        for x in self.iter():
            if x.href == href:
                return True
        return False

    def has_text(self, text):
        for x in self.iter():
            if x.title and x.title.lower() == text.lower():
                return True
        return False

    def iterdescendants(self, breadth_first=False):
        """Iterate over all descendant nodes in depth-first order."""
        if breadth_first:
            for child in self.nodes:
                yield child
            for child in self.nodes:
                yield from child.iterdescendants(breadth_first=True)
        else:
            for child in self.nodes:
                yield from child.iter()

    def __iter__(self):
        """Iterate over all immediate child nodes."""
        yield from self.nodes

    def __getitem__(self, index):
        return self.nodes[index]

    def autolayer(self):
        """Make sequences of children pointing to the same content file into
        children of the first node referencing that file.
        """
        prev = None
        for node in list(self.nodes):
            if prev and urldefrag(prev.href)[0] == urldefrag(node.href)[0]:
                self.nodes.remove(node)
                prev.nodes.append(node)
            else:
                prev = node

    def depth(self):
        """The maximum depth of the navigation tree rooted at this node."""
        try:
            return max(node.depth() for node in self.nodes) + 1
        except ValueError:
            return 1

    def get_lines(self, lvl=0):
        ans = [('\t'*lvl) + 'TOC: %s --> %s'%(self.title, self.href)]
        for child in self:
            ans.extend(child.get_lines(lvl+1))
        return ans

    def __str__(self):
        return '\n'.join(self.get_lines())

    def to_opf1(self, tour):
        for node in self.nodes:
            element(tour, 'site', attrib={
                'title': node.title, 'href': urlunquote(node.href)})
            node.to_opf1(tour)
        return tour

    def to_ncx(self, parent=None):
        if parent is None:
            parent = etree.Element(NCX('navMap'))
        for node in self.nodes:
            id = node.id or uuid_id()
            po = node.play_order
            if po == 0:
                po = 1
            attrib = {'id': id, 'playOrder': str(po)}
            if node.klass:
                attrib['class'] = node.klass
            point = element(parent, NCX('navPoint'), attrib=attrib)
            label = etree.SubElement(point, NCX('navLabel'))
            title = node.title
            if title:
                title = re.sub(r'\s+', ' ', title)
            element(label, NCX('text')).text = title
            # Do not unescape this URL as ADE requires it to be escaped to
            # handle semi colons and other special characters in the file names
            element(point, NCX('content'), src=node.href)
            node.to_ncx(point)
        return parent

    def rationalize_play_orders(self):
        '''
        Ensure that all nodes with the same play_order have the same href and
        with different play_orders have different hrefs.
        '''
        def po_node(n):
            for x in self.iter():
                if x is n:
                    return
                if x.play_order == n.play_order:
                    return x

        def href_node(n):
            for x in self.iter():
                if x is n:
                    return
                if x.href == n.href:
                    return x

        for x in self.iter():
            y = po_node(x)
            if y is not None:
                if x.href != y.href:
                    x.play_order = getattr(href_node(x), 'play_order',
                            self.next_play_order())
            y = href_node(x)
            if y is not None:
                x.play_order = y.play_order


class PageList:
    """Collection of named "pages" to mapped positions within an OEB data model
    book's textual content.

    Provides list-like access to the pages.
    """

    class Page:
        """Represents a mapping between a page name and a position within
        the book content.

        Provides the following instance data attributes:

        :attr:`name`: The name of this page.  Generally a number.
        :attr:`href`: Book-internal URL at which point this page begins.
        :attr:`type`: Must be one of 'front' (for prefatory pages, as commonly
            labeled in print with small-case Roman numerals), 'normal' (for
            standard pages, as commonly labeled in print with Arabic numerals),
            or 'special' (for other pages, as commonly not labeled in any
            fashion in print, such as the cover and title pages).
        :attr:`klass`: Optional semantic class of this page.
        :attr:`id`: Optional unique identifier for this page.
        """
        TYPES = {'front', 'normal', 'special'}

        def __init__(self, name, href, type='normal', klass=None, id=None):
            self.name = str(name)
            self.href = urlnormalize(href)
            self.type = type if type in self.TYPES else 'normal'
            self.id = id
            self.klass = klass

    def __init__(self):
        self.pages = []

    def add(self, name, href, type='normal', klass=None, id=None):
        """Create a new page and add it to the `PageList`."""
        page = self.Page(name, href, type, klass, id)
        self.pages.append(page)
        return page

    def __len__(self):
        return len(self.pages)

    def __iter__(self):
        yield from self.pages

    def __getitem__(self, index):
        return self.pages[index]

    def pop(self, index=-1):
        return self.pages.pop(index)

    def remove(self, page):
        return self.pages.remove(page)

    def to_ncx(self, parent=None):
        plist = element(parent, NCX('pageList'), id=uuid_id())
        values = {t: count(1) for t in ('front', 'normal', 'special')}
        for page in self.pages:
            id = page.id or uuid_id()
            type = page.type
            value = str(next(values[type]))
            attrib = {'id': id, 'value': value, 'type': type, 'playOrder': '0'}
            if page.klass:
                attrib['class'] = page.klass
            ptarget = element(plist, NCX('pageTarget'), attrib=attrib)
            label = element(ptarget, NCX('navLabel'))
            element(label, NCX('text')).text = page.name
            element(ptarget, NCX('content'), src=page.href)
        return plist

    def to_page_map(self):
        pmap = etree.Element(OPF('page-map'), nsmap={None: OPF2_NS})
        for page in self.pages:
            element(pmap, OPF('page'), name=page.name, href=page.href)
        return pmap


class OEBBook:
    """Representation of a book in the IDPF OEB data model."""

    COVER_SVG_XP    = XPath('h:body//svg:svg[position() = 1]')
    COVER_OBJECT_XP = XPath('h:body//h:object[@data][position() = 1]')

    def __init__(self, logger,
            html_preprocessor,
            css_preprocessor=CSSPreProcessor(),
            encoding='utf-8', pretty_print=False,
            input_encoding='utf-8'):
        """Create empty book.  Arguments:

        :param:`encoding`: Default encoding for textual content read
            from an external container.
        :param:`pretty_print`: Whether or not the canonical string form
            of XML markup is pretty-printed.
        :param html_preprocessor: A callable that takes a unicode object
            and returns a unicode object. Will be called on all html files
            before they are parsed.
        :param css_preprocessor: A callable that takes a unicode object
            and returns a unicode object. Will be called on all CSS files
            before they are parsed.
        :param:`logger`: A Log object to use for logging all messages
            related to the processing of this book.  It is accessible
            via the instance data members :attr:`logger,log`.

        It provides the following public instance data members for
        accessing various parts of the OEB data model:

        :attr:`metadata`: Metadata such as title, author name(s), etc.
        :attr:`manifest`: Manifest of all files included in the book,
            including MIME types and fallback information.
        :attr:`spine`: In-order list of manifest items which compose
            the textual content of the book.
        :attr:`guide`: Collection of references to standard positions
            within the text, such as the cover, preface, etc.
        :attr:`toc`: Hierarchical table of contents.
        :attr:`pages`: List of "pages," such as indexed to a print edition of
            the same text.
        """
        _css_log_handler.log = logger
        self.encoding = encoding
        self.input_encoding = input_encoding
        self.html_preprocessor = html_preprocessor
        self.css_preprocessor = css_preprocessor
        self.pretty_print = pretty_print
        self.logger = self.log = logger
        self.version = '2.0'
        self.container = NullContainer(self.log)
        self.metadata = Metadata(self)
        self.uid = None
        self.manifest = Manifest(self)
        self.spine = Spine(self)
        self.guide = Guide(self)
        self.toc = TOC()
        self.pages = PageList()
        self.auto_generated_toc = True
        self._temp_files = []

    def clean_temp_files(self):
        for path in self._temp_files:
            try:
                os.remove(path)
            except:
                pass

    @classmethod
    def generate(cls, opts):
        """Generate an OEBBook instance from command-line options."""
        encoding = opts.encoding
        pretty_print = opts.pretty_print
        return cls(encoding=encoding, pretty_print=pretty_print)

    def translate(self, text):
        """Translate :param:`text` into the book's primary language."""
        lang = str(self.metadata.language[0])
        lang = lang.split('-', 1)[0].lower()
        return translate(lang, text)

    def decode(self, data):
        """Automatically decode :param:`data` into a `unicode` object."""
        def fix_data(d):
            return d.replace('\r\n', '\n').replace('\r', '\n')
        if isinstance(data, str):
            return fix_data(data)
        bom_enc = None
        if data[:4] in (b'\0\0\xfe\xff', b'\xff\xfe\0\0'):
            bom_enc = {b'\0\0\xfe\xff':'utf-32-be',
                    b'\xff\xfe\0\0':'utf-32-le'}[data[:4]]
            data = data[4:]
        elif data[:2] in (b'\xff\xfe', b'\xfe\xff'):
            bom_enc = {b'\xff\xfe':'utf-16-le', 'b\xfe\xff':'utf-16-be'}[data[:2]]
            data = data[2:]
        elif data[:3] == b'\xef\xbb\xbf':
            bom_enc = 'utf-8'
            data = data[3:]
        if bom_enc is not None:
            try:
                return fix_data(data.decode(bom_enc))
            except UnicodeDecodeError:
                pass
        if self.input_encoding:
            try:
                return fix_data(data.decode(self.input_encoding, 'replace'))
            except UnicodeDecodeError:
                pass
        try:
            return fix_data(data.decode('utf-8'))
        except UnicodeDecodeError:
            pass
        data, _ = xml_to_unicode(data)
        return fix_data(data)

    def to_opf1(self):
        """Produce OPF 1.2 representing the book's metadata and structure.

        Returns a dictionary in which the keys are MIME types and the values
        are tuples of (default) filenames and lxml.etree element structures.
        """
        package = etree.Element('package',
            attrib={'unique-identifier': self.uid.id})
        self.metadata.to_opf1(package)
        self.manifest.to_opf1(package)
        self.spine.to_opf1(package)
        tours = element(package, 'tours')
        tour = element(tours, 'tour',
            attrib={'id': 'chaptertour', 'title': 'Chapter Tour'})
        self.toc.to_opf1(tour)
        self.guide.to_opf1(package)
        return {OPF_MIME: ('content.opf', package)}

    def _update_playorder(self, ncx):
        hrefs = set(map(urlnormalize, xpath(ncx, '//ncx:content/@src')))
        playorder = {}
        next = 1
        selector = XPath('h:body//*[@id or @name]')
        for item in self.spine:
            base = item.href
            if base in hrefs:
                playorder[base] = next
                next += 1
            for elem in selector(item.data):
                added = False
                for attr in ('id', 'name'):
                    id = elem.get(attr)
                    if not id:
                        continue
                    href = '#'.join([base, id])
                    if href in hrefs:
                        playorder[href] = next
                        added = True
                if added:
                    next += 1
        selector = XPath('ncx:content/@src')
        for i, elem in enumerate(xpath(ncx, '//*[@playOrder and ./ncx:content[@src]]')):
            href = urlnormalize(selector(elem)[0])
            order = playorder.get(href, i)
            elem.attrib['playOrder'] = str(order)
        return

    def _to_ncx(self):
        try:
            lang = str(self.metadata.language[0])
        except IndexError:
            lang = 'en'
        lang = lang.replace('_', '-')
        ncx = etree.Element(NCX('ncx'),
            attrib={'version': '2005-1', XML('lang'): lang},
            nsmap={None: NCX_NS})
        head = etree.SubElement(ncx, NCX('head'))
        etree.SubElement(head, NCX('meta'),
            name='dtb:uid', content=str(self.uid))
        etree.SubElement(head, NCX('meta'),
            name='dtb:depth', content=str(self.toc.depth()))
        generator = ''.join(['calibre (', __version__, ')'])
        etree.SubElement(head, NCX('meta'),
            name='dtb:generator', content=generator)
        etree.SubElement(head, NCX('meta'),
            name='dtb:totalPageCount', content=str(len(self.pages)))
        maxpnum = etree.SubElement(head, NCX('meta'),
            name='dtb:maxPageNumber', content='0')
        title = etree.SubElement(ncx, NCX('docTitle'))
        text = etree.SubElement(title, NCX('text'))
        text.text = str(self.metadata.title[0])
        navmap = etree.SubElement(ncx, NCX('navMap'))
        self.toc.to_ncx(navmap)
        if len(self.pages) > 0:
            plist = self.pages.to_ncx(ncx)
            value = max(int(x) for x in xpath(plist, '//@value'))
            maxpnum.attrib['content'] = str(value)
        self._update_playorder(ncx)
        return ncx

    def to_opf2(self, page_map=False):
        """Produce OPF 2.0 representing the book's metadata and structure.

        Returns a dictionary in which the keys are MIME types and the values
        are tuples of (default) filenames and lxml.etree element structures.
        """
        results = {}
        package = etree.Element(OPF('package'),
            attrib={'version': '2.0', 'unique-identifier': self.uid.id},
            nsmap={None: OPF2_NS})
        self.metadata.to_opf2(package)
        manifest = self.manifest.to_opf2(package)
        spine = self.spine.to_opf2(package)
        self.guide.to_opf2(package)
        results[OPF_MIME] = ('content.opf', package)
        id, href = self.manifest.generate('ncx', 'toc.ncx')
        etree.SubElement(manifest, OPF('item'), id=id, href=href,
                         attrib={'media-type': NCX_MIME})
        spine.attrib['toc'] = id
        results[NCX_MIME] = (href, self._to_ncx())
        if page_map and len(self.pages) > 0:
            id, href = self.manifest.generate('page-map', 'page-map.xml')
            etree.SubElement(manifest, OPF('item'), id=id, href=href,
                             attrib={'media-type': PAGE_MAP_MIME})
            spine.attrib['page-map'] = id
            results[PAGE_MAP_MIME] = (href, self.pages.to_page_map())
        if self.spine.page_progression_direction in {'ltr', 'rtl'}:
            spine.attrib['page-progression-direction'] = self.spine.page_progression_direction
        return results


def rel_href(base_href, href):
    """Convert the URL provided in :param:`href` to a URL relative to the URL
    in :param:`base_href`  """
    if urlparse(href).scheme:
        return href
    if '/' not in base_href:
        return href
    base = list(filter(lambda x: x and x != '.', os.path.dirname(os.path.normpath(base_href)).replace(os.sep, '/').split('/')))
    while True:
        try:
            idx = base.index('..')
        except ValueError:
            break
        if idx > 0:
            del base[idx-1:idx+1]
        else:
            break
    if not base:
        return href
    target, frag = urldefrag(href)
    target = target.split('/')
    index = 0
    for index in range(min(len(base), len(target))):
        if base[index] != target[index]:
            break
    else:
        index += 1
    relhref = (['..'] * (len(base) - index)) + target[index:]
    relhref = '/'.join(relhref)
    if frag:
        relhref = '#'.join((relhref, frag))
    return relhref
