#!/usr/bin/env python
"""Universal feed parser

Handles RSS 0.9x, RSS 1.0, RSS 2.0, CDF, Atom 0.3, and Atom 1.0 feeds

Visit http://feedparser.org/ for the latest version
Visit http://feedparser.org/docs/ for the latest documentation

Required: Python 2.1 or later
Recommended: Python 2.3 or later
Recommended: CJKCodecs and iconv_codec <http://cjkpython.i18n.org/>
"""

__version__ = "4.2-pre-" + "$Revision: 316 $"[11:14] + "-svn"
__license__ = """Copyright (c) 2002-2008, Mark Pilgrim, All rights reserved.

Redistribution and use in source and binary forms, with or without modification,
are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice,
  this list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS 'AS IS'
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE."""
__author__ = "Mark Pilgrim <http://diveintomark.org/>"
__contributors__ = ["Jason Diamond <http://injektilo.org/>",
                    "John Beimler <http://john.beimler.org/>",
                    "Fazal Majid <http://www.majid.info/mylos/weblog/>",
                    "Aaron Swartz <http://aaronsw.com/>",
                    "Kevin Marks <http://epeus.blogspot.com/>",
                    "Sam Ruby <http://intertwingly.net/>",
                    "Ade Oshineye <http://blog.oshineye.com/>",
                    "Martin Pool <http://sourcefrog.net/>"]
_debug = 0

# HTTP "User-Agent" header to send to servers when downloading feeds.
# If you are embedding feedparser in a larger application, you should
# change this to your application name and URL.
USER_AGENT = 'Mozilla/5.0 (X11; U; i686 Linux; en_US; rv:1.8.0.4) Gecko/20060508 Firefox/1.5.0.4' # Changed by Kovid

# HTTP "Accept" header to send to servers when downloading feeds.  If you don't
# want to send an Accept header, set this to None.
ACCEPT_HEADER = "application/atom+xml,application/rdf+xml,application/rss+xml,application/x-netcdf,application/xml;q=0.9,text/xml;q=0.2,*/*;q=0.1"

# List of preferred XML parsers, by SAX driver name.  These will be tried first,
# but if they're not installed, Python will keep searching through its own list
# of pre-installed parsers until it finds one that supports everything we need.
PREFERRED_XML_PARSERS = ["drv_libxml2"]

# If you want feedparser to automatically run HTML markup through HTML Tidy, set
# this to 1.  Requires mxTidy <http://www.egenix.com/files/python/mxTidy.html>
# or utidylib <http://utidylib.berlios.de/>.
TIDY_MARKUP = 0

# List of Python interfaces for HTML Tidy, in order of preference.  Only useful
# if TIDY_MARKUP = 1
PREFERRED_TIDY_INTERFACES = ["uTidy", "mxTidy"]

# If you want feedparser to automatically resolve all relative URIs, set this
# to 1.
RESOLVE_RELATIVE_URIS = 1

# If you want feedparser to automatically sanitize all potentially unsafe
# HTML content, set this to 1.
SANITIZE_HTML = 1

# ---------- required modules (should come with any Python distribution) ----------
import sgmllib, re, sys, copy, urlparse, time, rfc822, types, cgi, urllib, urllib2
try:
    from cStringIO import StringIO as _StringIO
except:
    from StringIO import StringIO as _StringIO

# ---------- optional modules (feedparser will work without these, but with reduced functionality) ----------

# gzip is included with most Python distributions, but may not be available if you compiled your own
try:
    import gzip
except:
    gzip = None
try:
    import zlib
except:
    zlib = None

# If a real XML parser is available, feedparser will attempt to use it.  feedparser has
# been tested with the built-in SAX parser, PyXML, and libxml2.  On platforms where the
# Python distribution does not come with an XML parser (such as Mac OS X 10.2 and some
# versions of FreeBSD), feedparser will quietly fall back on regex-based parsing.
try:
    import xml.sax
    xml.sax.make_parser(PREFERRED_XML_PARSERS) # test for valid parsers
    from xml.sax.saxutils import escape as _xmlescape
    _XML_AVAILABLE = 1
except:
    _XML_AVAILABLE = 0
    def _xmlescape(data,entities={}):
        data = data.replace('&', '&amp;')
        data = data.replace('>', '&gt;')
        data = data.replace('<', '&lt;')
        for char, entity in entities:
            data = data.replace(char, entity)
        return data

# base64 support for Atom feeds that contain embedded binary data
try:
    import base64, binascii
except:
    base64 = binascii = None

# cjkcodecs and iconv_codec provide support for more character encodings.
# Both are available from http://cjkpython.i18n.org/
try:
    import cjkcodecs.aliases
except:
    pass
try:
    import iconv_codec
except:
    pass

# chardet library auto-detects character encodings
# Download from http://chardet.feedparser.org/
try:
    import calibre.ebooks.chardet as chardet # Changed by Kovid
    if _debug:
        import chardet.constants
        chardet.constants._debug = 1
except:
    chardet = None

# reversable htmlentitydefs mappings for Python 2.2
try:
  from htmlentitydefs import name2codepoint, codepoint2name
except:
  import htmlentitydefs
  name2codepoint={}
  codepoint2name={}
  for (name,codepoint) in htmlentitydefs.entitydefs.iteritems():
    if codepoint.startswith('&#'): codepoint=unichr(int(codepoint[2:-1]))
    name2codepoint[name]=ord(codepoint)
    codepoint2name[ord(codepoint)]=name

# BeautifulSoup parser used for parsing microformats from embedded HTML content
# http://www.crummy.com/software/BeautifulSoup/
# feedparser is tested with BeautifulSoup 3.0.x, but it might work with the
# older 2.x series.  If it doesn't, and you can figure out why, I'll accept a
# patch and modify the compatibility statement accordingly.
try:
    import BeautifulSoup
except:
    BeautifulSoup = None

# ---------- don't touch these ----------
class ThingsNobodyCaresAboutButMe(Exception): pass
class CharacterEncodingOverride(ThingsNobodyCaresAboutButMe): pass
class CharacterEncodingUnknown(ThingsNobodyCaresAboutButMe): pass
class NonXMLContentType(ThingsNobodyCaresAboutButMe): pass
class UndeclaredNamespace(Exception): pass

sgmllib.tagfind = re.compile('[a-zA-Z][-_.:a-zA-Z0-9]*')
sgmllib.special = re.compile('<!')
sgmllib.charref = re.compile('&#(\d+|x[0-9a-fA-F]+);')

if sgmllib.endbracket.search(' <').start(0):
    class EndBracketMatch:
        endbracket = re.compile('''([^'"<>]|"[^"]*"(?=>|/|\s|\w+=)|'[^']*'(?=>|/|\s|\w+=))*(?=[<>])|.*?(?=[<>])''')
        def search(self,string,index=0):
            self.match = self.endbracket.match(string,index)
            if self.match: return self
        def start(self,n):
            return self.match.end(n)
    sgmllib.endbracket = EndBracketMatch()

SUPPORTED_VERSIONS = {'': 'unknown',
                      'rss090': 'RSS 0.90',
                      'rss091n': 'RSS 0.91 (Netscape)',
                      'rss091u': 'RSS 0.91 (Userland)',
                      'rss092': 'RSS 0.92',
                      'rss093': 'RSS 0.93',
                      'rss094': 'RSS 0.94',
                      'rss20': 'RSS 2.0',
                      'rss10': 'RSS 1.0',
                      'rss': 'RSS (unknown version)',
                      'atom01': 'Atom 0.1',
                      'atom02': 'Atom 0.2',
                      'atom03': 'Atom 0.3',
                      'atom10': 'Atom 1.0',
                      'atom': 'Atom (unknown version)',
                      'cdf': 'CDF',
                      'hotrss': 'Hot RSS'
                      }

try:
    UserDict = dict
except NameError:
    # Python 2.1 does not have dict
    from UserDict import UserDict
    def dict(aList):
        rc = {}
        for k, v in aList:
            rc[k] = v
        return rc

class FeedParserDict(UserDict):
    keymap = {'channel': 'feed',
              'items': 'entries',
              'guid': 'id',
              'date': 'updated',
              'date_parsed': 'updated_parsed',
              'description': ['subtitle', 'summary'],
              'url': ['href'],
              'modified': 'updated',
              'modified_parsed': 'updated_parsed',
              'issued': 'published',
              'issued_parsed': 'published_parsed',
              'copyright': 'rights',
              'copyright_detail': 'rights_detail',
              'tagline': 'subtitle',
              'tagline_detail': 'subtitle_detail'}
    def __getitem__(self, key):
        if key == 'category':
            return UserDict.__getitem__(self, 'tags')[0]['term']
        if key == 'enclosures':
            norel = lambda link: FeedParserDict([(name,value) for (name,value) in link.items() if name!='rel'])
            return [norel(link) for link in UserDict.__getitem__(self, 'links') if link['rel']=='enclosure']
        if key == 'license':
            for link in UserDict.__getitem__(self, 'links'):
                if link['rel']=='license' and link.has_key('href'):
                    return link['href']
        if key == 'categories':
            return [(tag['scheme'], tag['term']) for tag in UserDict.__getitem__(self, 'tags')]
        realkey = self.keymap.get(key, key)
        if type(realkey) == types.ListType:
            for k in realkey:
                if UserDict.has_key(self, k):
                    return UserDict.__getitem__(self, k)
        if UserDict.has_key(self, key):
            return UserDict.__getitem__(self, key)
        return UserDict.__getitem__(self, realkey)

    def __setitem__(self, key, value):
        for k in self.keymap.keys():
            if key == k:
                key = self.keymap[k]
                if type(key) == types.ListType:
                    key = key[0]
        return UserDict.__setitem__(self, key, value)

    def get(self, key, default=None):
        if self.has_key(key):
            return self[key]
        else:
            return default

    def setdefault(self, key, value):
        if not self.has_key(key):
            self[key] = value
        return self[key]

    def has_key(self, key):
        try:
            return hasattr(self, key) or UserDict.has_key(self, key)
        except AttributeError:
            return False

    def __getattr__(self, key):
        try:
            return self.__dict__[key]
        except KeyError:
            pass
        try:
            assert not key.startswith('_')
            return self.__getitem__(key)
        except:
            raise AttributeError, "object has no attribute '%s'" % key

    def __setattr__(self, key, value):
        if key.startswith('_') or key == 'data':
            self.__dict__[key] = value
        else:
            return self.__setitem__(key, value)

    def __contains__(self, key):
        return self.has_key(key)

def zopeCompatibilityHack():
    global FeedParserDict
    del FeedParserDict
    def FeedParserDict(aDict=None):
        rc = {}
        if aDict:
            rc.update(aDict)
        return rc

_ebcdic_to_ascii_map = None
def _ebcdic_to_ascii(s):
    global _ebcdic_to_ascii_map
    if not _ebcdic_to_ascii_map:
        emap = (
            0,1,2,3,156,9,134,127,151,141,142,11,12,13,14,15,
            16,17,18,19,157,133,8,135,24,25,146,143,28,29,30,31,
            128,129,130,131,132,10,23,27,136,137,138,139,140,5,6,7,
            144,145,22,147,148,149,150,4,152,153,154,155,20,21,158,26,
            32,160,161,162,163,164,165,166,167,168,91,46,60,40,43,33,
            38,169,170,171,172,173,174,175,176,177,93,36,42,41,59,94,
            45,47,178,179,180,181,182,183,184,185,124,44,37,95,62,63,
            186,187,188,189,190,191,192,193,194,96,58,35,64,39,61,34,
            195,97,98,99,100,101,102,103,104,105,196,197,198,199,200,201,
            202,106,107,108,109,110,111,112,113,114,203,204,205,206,207,208,
            209,126,115,116,117,118,119,120,121,122,210,211,212,213,214,215,
            216,217,218,219,220,221,222,223,224,225,226,227,228,229,230,231,
            123,65,66,67,68,69,70,71,72,73,232,233,234,235,236,237,
            125,74,75,76,77,78,79,80,81,82,238,239,240,241,242,243,
            92,159,83,84,85,86,87,88,89,90,244,245,246,247,248,249,
            48,49,50,51,52,53,54,55,56,57,250,251,252,253,254,255
            )
        import string
        _ebcdic_to_ascii_map = string.maketrans( \
            ''.join(map(chr, range(256))), ''.join(map(chr, emap)))
    return s.translate(_ebcdic_to_ascii_map)

_cp1252 = {
  unichr(128): unichr(8364), # euro sign
  unichr(130): unichr(8218), # single low-9 quotation mark
  unichr(131): unichr( 402), # latin small letter f with hook
  unichr(132): unichr(8222), # double low-9 quotation mark
  unichr(133): unichr(8230), # horizontal ellipsis
  unichr(134): unichr(8224), # dagger
  unichr(135): unichr(8225), # double dagger
  unichr(136): unichr( 710), # modifier letter circumflex accent
  unichr(137): unichr(8240), # per mille sign
  unichr(138): unichr( 352), # latin capital letter s with caron
  unichr(139): unichr(8249), # single left-pointing angle quotation mark
  unichr(140): unichr( 338), # latin capital ligature oe
  unichr(142): unichr( 381), # latin capital letter z with caron
  unichr(145): unichr(8216), # left single quotation mark
  unichr(146): unichr(8217), # right single quotation mark
  unichr(147): unichr(8220), # left double quotation mark
  unichr(148): unichr(8221), # right double quotation mark
  unichr(149): unichr(8226), # bullet
  unichr(150): unichr(8211), # en dash
  unichr(151): unichr(8212), # em dash
  unichr(152): unichr( 732), # small tilde
  unichr(153): unichr(8482), # trade mark sign
  unichr(154): unichr( 353), # latin small letter s with caron
  unichr(155): unichr(8250), # single right-pointing angle quotation mark
  unichr(156): unichr( 339), # latin small ligature oe
  unichr(158): unichr( 382), # latin small letter z with caron
  unichr(159): unichr( 376)} # latin capital letter y with diaeresis

_urifixer = re.compile('^([A-Za-z][A-Za-z0-9+-.]*://)(/*)(.*?)')
def _urljoin(base, uri):
    uri = _urifixer.sub(r'\1\3', uri)
    try:
        return urlparse.urljoin(base, uri)
    except:
        uri = urlparse.urlunparse([urllib.quote(part) for part in urlparse.urlparse(uri)])
        return urlparse.urljoin(base, uri)

class _FeedParserMixin:
    namespaces = {'': '',
                  'http://backend.userland.com/rss': '',
                  'http://blogs.law.harvard.edu/tech/rss': '',
                  'http://purl.org/rss/1.0/': '',
                  'http://my.netscape.com/rdf/simple/0.9/': '',
                  'http://example.com/newformat#': '',
                  'http://example.com/necho': '',
                  'http://purl.org/echo/': '',
                  'uri/of/echo/namespace#': '',
                  'http://purl.org/pie/': '',
                  'http://purl.org/atom/ns#': '',
                  'http://www.w3.org/2005/Atom': '',
                  'http://purl.org/rss/1.0/modules/rss091#': '',

                  'http://webns.net/mvcb/':                               'admin',
                  'http://purl.org/rss/1.0/modules/aggregation/':         'ag',
                  'http://purl.org/rss/1.0/modules/annotate/':            'annotate',
                  'http://media.tangent.org/rss/1.0/':                    'audio',
                  'http://backend.userland.com/blogChannelModule':        'blogChannel',
                  'http://web.resource.org/cc/':                          'cc',
                  'http://backend.userland.com/creativeCommonsRssModule': 'creativeCommons',
                  'http://purl.org/rss/1.0/modules/company':              'co',
                  'http://purl.org/rss/1.0/modules/content/':             'content',
                  'http://my.theinfo.org/changed/1.0/rss/':               'cp',
                  'http://purl.org/dc/elements/1.1/':                     'dc',
                  'http://purl.org/dc/terms/':                            'dcterms',
                  'http://purl.org/rss/1.0/modules/email/':               'email',
                  'http://purl.org/rss/1.0/modules/event/':               'ev',
                  'http://rssnamespace.org/feedburner/ext/1.0':           'feedburner',
                  'http://freshmeat.net/rss/fm/':                         'fm',
                  'http://xmlns.com/foaf/0.1/':                           'foaf',
                  'http://www.w3.org/2003/01/geo/wgs84_pos#':             'geo',
                  'http://postneo.com/icbm/':                             'icbm',
                  'http://purl.org/rss/1.0/modules/image/':               'image',
                  'http://www.itunes.com/DTDs/PodCast-1.0.dtd':           'itunes',
                  'http://example.com/DTDs/PodCast-1.0.dtd':              'itunes',
                  'http://purl.org/rss/1.0/modules/link/':                'l',
                  'http://search.yahoo.com/mrss':                         'media',
                  #Version 1.1.2 of the Media RSS spec added the trailing slash on the namespace
                  'http://search.yahoo.com/mrss/':                         'media',
                  'http://madskills.com/public/xml/rss/module/pingback/': 'pingback',
                  'http://prismstandard.org/namespaces/1.2/basic/':       'prism',
                  'http://www.w3.org/1999/02/22-rdf-syntax-ns#':          'rdf',
                  'http://www.w3.org/2000/01/rdf-schema#':                'rdfs',
                  'http://purl.org/rss/1.0/modules/reference/':           'ref',
                  'http://purl.org/rss/1.0/modules/richequiv/':           'reqv',
                  'http://purl.org/rss/1.0/modules/search/':              'search',
                  'http://purl.org/rss/1.0/modules/slash/':               'slash',
                  'http://schemas.xmlsoap.org/soap/envelope/':            'soap',
                  'http://purl.org/rss/1.0/modules/servicestatus/':       'ss',
                  'http://hacks.benhammersley.com/rss/streaming/':        'str',
                  'http://purl.org/rss/1.0/modules/subscription/':        'sub',
                  'http://purl.org/rss/1.0/modules/syndication/':         'sy',
                  'http://schemas.pocketsoap.com/rss/myDescModule/':      'szf',
                  'http://purl.org/rss/1.0/modules/taxonomy/':            'taxo',
                  'http://purl.org/rss/1.0/modules/threading/':           'thr',
                  'http://purl.org/rss/1.0/modules/textinput/':           'ti',
                  'http://madskills.com/public/xml/rss/module/trackback/':'trackback',
                  'http://wellformedweb.org/commentAPI/':                 'wfw',
                  'http://purl.org/rss/1.0/modules/wiki/':                'wiki',
                  'http://www.w3.org/1999/xhtml':                         'xhtml',
                  'http://www.w3.org/1999/xlink':                         'xlink',
                  'http://www.w3.org/XML/1998/namespace':                 'xml'
}
    _matchnamespaces = {}

    can_be_relative_uri = ['link', 'id', 'wfw_comment', 'wfw_commentrss', 'docs', 'url', 'href', 'comments', 'icon', 'logo']
    can_contain_relative_uris = ['content', 'title', 'summary', 'info', 'tagline', 'subtitle', 'copyright', 'rights', 'description']
    can_contain_dangerous_markup = ['content', 'title', 'summary', 'info', 'tagline', 'subtitle', 'copyright', 'rights', 'description']
    html_types = ['text/html', 'application/xhtml+xml']

    def __init__(self, baseuri=None, baselang=None, encoding='utf-8'):
        if _debug: sys.stderr.write('initializing FeedParser\n')
        if not self._matchnamespaces:
            for k, v in self.namespaces.items():
                self._matchnamespaces[k.lower()] = v
        self.feeddata = FeedParserDict() # feed-level data
        self.encoding = encoding # character encoding
        self.entries = [] # list of entry-level data
        self.version = '' # feed type/version, see SUPPORTED_VERSIONS
        self.namespacesInUse = {} # dictionary of namespaces defined by the feed

        # the following are used internally to track state;
        # this is really out of control and should be refactored
        self.infeed = 0
        self.inentry = 0
        self.incontent = 0
        self.intextinput = 0
        self.inimage = 0
        self.inauthor = 0
        self.incontributor = 0
        self.inpublisher = 0
        self.insource = 0
        self.sourcedata = FeedParserDict()
        self.contentparams = FeedParserDict()
        self._summaryKey = None
        self.namespacemap = {}
        self.elementstack = []
        self.basestack = []
        self.langstack = []
        self.baseuri = baseuri or ''
        self.lang = baselang or None
        self.svgOK = 0
        self.hasTitle = 0
        if baselang:
            self.feeddata['language'] = baselang.replace('_','-')

    def unknown_starttag(self, tag, attrs):
        if _debug: sys.stderr.write('start %s with %s\n' % (tag, attrs))
        # normalize attrs
        attrs = [(k.lower(), v) for k, v in attrs]
        attrs = [(k, k in ('rel', 'type') and v.lower() or v) for k, v in attrs]

        # track xml:base and xml:lang
        attrsD = dict(attrs)
        baseuri = attrsD.get('xml:base', attrsD.get('base')) or self.baseuri
        if type(baseuri) != type(u''):
            try:
                baseuri = unicode(baseuri, self.encoding)
            except:
                baseuri = unicode(baseuri, 'iso-8859-1')
        self.baseuri = _urljoin(self.baseuri, baseuri)
        lang = attrsD.get('xml:lang', attrsD.get('lang'))
        if lang == '':
            # xml:lang could be explicitly set to '', we need to capture that
            lang = None
        elif lang is None:
            # if no xml:lang is specified, use parent lang
            lang = self.lang
        if lang:
            if tag in ('feed', 'rss', 'rdf:RDF'):
                self.feeddata['language'] = lang.replace('_','-')
        self.lang = lang
        self.basestack.append(self.baseuri)
        self.langstack.append(lang)

        # track namespaces
        for prefix, uri in attrs:
            if prefix.startswith('xmlns:'):
                self.trackNamespace(prefix[6:], uri)
            elif prefix == 'xmlns':
                self.trackNamespace(None, uri)

        # track inline content
        if self.incontent and self.contentparams.has_key('type') and not self.contentparams.get('type', 'xml').endswith('xml'):
            if tag in ['xhtml:div', 'div']: return # typepad does this 10/2007
            # element declared itself as escaped markup, but it isn't really
            self.contentparams['type'] = 'application/xhtml+xml'
        if self.incontent and self.contentparams.get('type') == 'application/xhtml+xml':
            if tag.find(':') <> -1:
                prefix, tag = tag.split(':', 1)
                namespace = self.namespacesInUse.get(prefix, '')
                if tag=='math' and namespace=='http://www.w3.org/1998/Math/MathML':
                    attrs.append(('xmlns',namespace))
                if tag=='svg' and namespace=='http://www.w3.org/2000/svg':
                    attrs.append(('xmlns',namespace))
            if tag == 'svg': self.svgOK += 1
            return self.handle_data('<%s%s>' % (tag, self.strattrs(attrs)), escape=0)

        # match namespaces
        if tag.find(':') <> -1:
            prefix, suffix = tag.split(':', 1)
        else:
            prefix, suffix = '', tag
        prefix = self.namespacemap.get(prefix, prefix)
        if prefix:
            prefix = prefix + '_'

        # special hack for better tracking of empty textinput/image elements in illformed feeds
        if (not prefix) and tag not in ('title', 'link', 'description', 'name'):
            self.intextinput = 0
        if (not prefix) and tag not in ('title', 'link', 'description', 'url', 'href', 'width', 'height'):
            self.inimage = 0

        # call special handler (if defined) or default handler
        methodname = '_start_' + prefix + suffix
        try:
            method = getattr(self, methodname)
            return method(attrsD)
        except AttributeError:
            # Since there's no handler or something has gone wrong we explicitly add the element and its attributes
            unknown_tag = prefix + suffix
            if len(attrsD) == 0:
                # No attributes so merge it into the encosing dictionary
                return self.push(unknown_tag, 1)
            else:
                # Has attributes so create it in its own dictionary
                context = self._getContext()
                context[unknown_tag] = attrsD

    def unknown_endtag(self, tag):
        if _debug: sys.stderr.write('end %s\n' % tag)
        # match namespaces
        if tag.find(':') <> -1:
            prefix, suffix = tag.split(':', 1)
        else:
            prefix, suffix = '', tag
        prefix = self.namespacemap.get(prefix, prefix)
        if prefix:
            prefix = prefix + '_'
        if suffix == 'svg' and self.svgOK: self.svgOK -= 1

        # call special handler (if defined) or default handler
        methodname = '_end_' + prefix + suffix
        try:
            if self.svgOK: raise AttributeError()
            method = getattr(self, methodname)
            method()
        except AttributeError:
            self.pop(prefix + suffix)

        # track inline content
        if self.incontent and self.contentparams.has_key('type') and not self.contentparams.get('type', 'xml').endswith('xml'):
            # element declared itself as escaped markup, but it isn't really
            if tag in ['xhtml:div', 'div']: return # typepad does this 10/2007
            self.contentparams['type'] = 'application/xhtml+xml'
        if self.incontent and self.contentparams.get('type') == 'application/xhtml+xml':
            tag = tag.split(':')[-1]
            self.handle_data('</%s>' % tag, escape=0)

        # track xml:base and xml:lang going out of scope
        if self.basestack:
            self.basestack.pop()
            if self.basestack and self.basestack[-1]:
                self.baseuri = self.basestack[-1]
        if self.langstack:
            self.langstack.pop()
            if self.langstack: # and (self.langstack[-1] is not None):
                self.lang = self.langstack[-1]

    def handle_charref(self, ref):
        # called for each character reference, e.g. for '&#160;', ref will be '160'
        if not self.elementstack: return
        ref = ref.lower()
        if ref in ('34', '38', '39', '60', '62', 'x22', 'x26', 'x27', 'x3c', 'x3e'):
            text = '&#%s;' % ref
        else:
            if ref[0] == 'x':
                c = int(ref[1:], 16)
            else:
                c = int(ref)
            text = unichr(c).encode('utf-8')
        self.elementstack[-1][2].append(text)

    def handle_entityref(self, ref):
        # called for each entity reference, e.g. for '&copy;', ref will be 'copy'
        if not self.elementstack: return
        if _debug: sys.stderr.write('entering handle_entityref with %s\n' % ref)
        if ref in ('lt', 'gt', 'quot', 'amp', 'apos'):
            text = '&%s;' % ref
        elif ref in self.entities.keys():
            text = self.entities[ref]
            if text.startswith('&#') and text.endswith(';'):
                return self.handle_entityref(text)
        else:
            try: name2codepoint[ref]
            except KeyError: text = '&%s;' % ref
            else: text = unichr(name2codepoint[ref]).encode('utf-8')
        self.elementstack[-1][2].append(text)

    def handle_data(self, text, escape=1):
        # called for each block of plain text, i.e. outside of any tag and
        # not containing any character or entity references
        if not self.elementstack: return
        if escape and self.contentparams.get('type') == 'application/xhtml+xml':
            text = _xmlescape(text)
        self.elementstack[-1][2].append(text)

    def handle_comment(self, text):
        # called for each comment, e.g. <!-- insert message here -->
        pass

    def handle_pi(self, text):
        # called for each processing instruction, e.g. <?instruction>
        pass

    def handle_decl(self, text):
        pass

    def parse_declaration(self, i):
        # override internal declaration handler to handle CDATA blocks
        if _debug: sys.stderr.write('entering parse_declaration\n')
        if self.rawdata[i:i+9] == '<![CDATA[':
            k = self.rawdata.find(']]>', i)
            if k == -1:
                # CDATA block began but didn't finish
                k = len(self.rawdata)
                return k
            self.handle_data(_xmlescape(self.rawdata[i+9:k]), 0)
            return k+3
        else:
            k = self.rawdata.find('>', i)
            if k >= 0:
                return k+1
            else:
                # We have an incomplete CDATA block.
                return k

    def mapContentType(self, contentType):
        contentType = contentType.lower()
        if contentType == 'text':
            contentType = 'text/plain'
        elif contentType == 'html':
            contentType = 'text/html'
        elif contentType == 'xhtml':
            contentType = 'application/xhtml+xml'
        return contentType

    def trackNamespace(self, prefix, uri):
        loweruri = uri.lower()
        if (prefix, loweruri) == (None, 'http://my.netscape.com/rdf/simple/0.9/') and not self.version:
            self.version = 'rss090'
        if loweruri == 'http://purl.org/rss/1.0/' and not self.version:
            self.version = 'rss10'
        if loweruri == 'http://www.w3.org/2005/atom' and not self.version:
            self.version = 'atom10'
        if loweruri.find('backend.userland.com/rss') <> -1:
            # match any backend.userland.com namespace
            uri = 'http://backend.userland.com/rss'
            loweruri = uri
        if self._matchnamespaces.has_key(loweruri):
            self.namespacemap[prefix] = self._matchnamespaces[loweruri]
            self.namespacesInUse[self._matchnamespaces[loweruri]] = uri
        else:
            self.namespacesInUse[prefix or ''] = uri

    def resolveURI(self, uri):
        return _urljoin(self.baseuri or '', uri)

    def decodeEntities(self, element, data):
        return data

    def strattrs(self, attrs):
        return ''.join([' %s="%s"' % (t[0],_xmlescape(t[1],{'"':'&quot;'})) for t in attrs])

    def push(self, element, expectingText):
        self.elementstack.append([element, expectingText, []])

    def pop(self, element, stripWhitespace=1):
        if not self.elementstack: return
        if self.elementstack[-1][0] != element: return

        element, expectingText, pieces = self.elementstack.pop()

        if self.version == 'atom10' and self.contentparams.get('type','text') == 'application/xhtml+xml':
            # remove enclosing child element, but only if it is a <div> and
            # only if all the remaining content is nested underneath it.
            # This means that the divs would be retained in the following:
            #    <div>foo</div><div>bar</div>
            while pieces and len(pieces)>1 and not pieces[-1].strip():
                del pieces[-1]
            while pieces and len(pieces)>1 and not pieces[0].strip():
                del pieces[0]
            if pieces and (pieces[0] == '<div>' or pieces[0].startswith('<div ')) and pieces[-1]=='</div>':
                depth = 0
                for piece in pieces[:-1]:
                    if piece.startswith('</'):
                        depth -= 1
                        if depth == 0: break
                    elif piece.startswith('<') and not piece.endswith('/>'):
                        depth += 1
                else:
                    pieces = pieces[1:-1]

        output = ''.join(pieces)
        if stripWhitespace:
            output = output.strip()
        if not expectingText: return output

        # decode base64 content
        if base64 and self.contentparams.get('base64', 0):
            try:
                output = base64.decodestring(output)
            except binascii.Error:
                pass
            except binascii.Incomplete:
                pass

        # resolve relative URIs
        if (element in self.can_be_relative_uri) and output:
            output = self.resolveURI(output)

        # decode entities within embedded markup
        if not self.contentparams.get('base64', 0):
            output = self.decodeEntities(element, output)

        if self.lookslikehtml(output):
            self.contentparams['type']='text/html'

        # remove temporary cruft from contentparams
        try:
            del self.contentparams['mode']
        except KeyError:
            pass
        try:
            del self.contentparams['base64']
        except KeyError:
            pass

        is_htmlish = self.mapContentType(self.contentparams.get('type', 'text/html')) in self.html_types
        # resolve relative URIs within embedded markup
        if is_htmlish and RESOLVE_RELATIVE_URIS:
            if element in self.can_contain_relative_uris:
                output = _resolveRelativeURIs(output, self.baseuri, self.encoding, self.contentparams.get('type', 'text/html'))

        # parse microformats
        # (must do this before sanitizing because some microformats
        # rely on elements that we sanitize)
        if is_htmlish and element in ['content', 'description', 'summary']:
            mfresults = _parseMicroformats(output, self.baseuri, self.encoding)
            if mfresults:
                for tag in mfresults.get('tags', []):
                    self._addTag(tag['term'], tag['scheme'], tag['label'])
                for enclosure in mfresults.get('enclosures', []):
                    self._start_enclosure(enclosure)
                for xfn in mfresults.get('xfn', []):
                    self._addXFN(xfn['relationships'], xfn['href'], xfn['name'])
                vcard = mfresults.get('vcard')
                if vcard:
                    self._getContext()['vcard'] = vcard

        # sanitize embedded markup
        if is_htmlish and SANITIZE_HTML:
            if element in self.can_contain_dangerous_markup:
                output = _sanitizeHTML(output, self.encoding, self.contentparams.get('type', 'text/html'))

        if self.encoding and type(output) != type(u''):
            try:
                output = unicode(output, self.encoding)
            except:
                pass

        # address common error where people take data that is already
        # utf-8, presume that it is iso-8859-1, and re-encode it.
        if self.encoding=='utf-8' and type(output) == type(u''):
            try:
                output = unicode(output.encode('iso-8859-1'), 'utf-8')
            except:
                pass

        # map win-1252 extensions to the proper code points
        if type(output) == type(u''):
            output = u''.join([c in _cp1252.keys() and _cp1252[c] or c for c in output])

        # categories/tags/keywords/whatever are handled in _end_category
        if element == 'category':
            return output

        if element == 'title' and self.hasTitle:
            return output

        # store output in appropriate place(s)
        if self.inentry and not self.insource:
            if element == 'content':
                self.entries[-1].setdefault(element, [])
                contentparams = copy.deepcopy(self.contentparams)
                contentparams['value'] = output
                self.entries[-1][element].append(contentparams)
            elif element == 'link':
                self.entries[-1][element] = output
                if output:
                    self.entries[-1]['links'][-1]['href'] = output
            else:
                if element == 'description':
                    element = 'summary'
                self.entries[-1][element] = output
                if self.incontent:
                    contentparams = copy.deepcopy(self.contentparams)
                    contentparams['value'] = output
                    self.entries[-1][element + '_detail'] = contentparams
        elif (self.infeed or self.insource):# and (not self.intextinput) and (not self.inimage):
            context = self._getContext()
            if element == 'description':
                element = 'subtitle'
            context[element] = output
            if element == 'link':
                context['links'][-1]['href'] = output
            elif self.incontent:
                contentparams = copy.deepcopy(self.contentparams)
                contentparams['value'] = output
                context[element + '_detail'] = contentparams
        return output

    def pushContent(self, tag, attrsD, defaultContentType, expectingText):
        self.incontent += 1
        if self.lang: self.lang=self.lang.replace('_','-')
        self.contentparams = FeedParserDict({
            'type': self.mapContentType(attrsD.get('type', defaultContentType)),
            'language': self.lang,
            'base': self.baseuri})
        self.contentparams['base64'] = self._isBase64(attrsD, self.contentparams)
        self.push(tag, expectingText)

    def popContent(self, tag):
        value = self.pop(tag)
        self.incontent -= 1
        self.contentparams.clear()
        return value

    # a number of elements in a number of RSS variants are nominally plain
    # text, but this is routinely ignored.  This is an attempt to detect
    # the most common cases.  As false positives often result in silent
    # data loss, this function errs on the conservative side.
    def lookslikehtml(self, str):
        if self.version.startswith('atom'): return
        if self.contentparams.get('type','text/html') != 'text/plain': return

        # must have a close tag or a entity reference to qualify
        if not (re.search(r'</(\w+)>',str) or re.search("&#?\w+;",str)): return

        # all tags must be in a restricted subset of valid HTML tags
        if filter(lambda t: t.lower() not in _HTMLSanitizer.acceptable_elements,
            re.findall(r'</?(\w+)',str)): return

        # all entities must have been defined as valid HTML entities
        from htmlentitydefs import entitydefs
        if filter(lambda e: e not in entitydefs.keys(),
            re.findall(r'&(\w+);',str)): return

        return 1

    def _mapToStandardPrefix(self, name):
        colonpos = name.find(':')
        if colonpos <> -1:
            prefix = name[:colonpos]
            suffix = name[colonpos+1:]
            prefix = self.namespacemap.get(prefix, prefix)
            name = prefix + ':' + suffix
        return name

    def _getAttribute(self, attrsD, name):
        return attrsD.get(self._mapToStandardPrefix(name))

    def _isBase64(self, attrsD, contentparams):
        if attrsD.get('mode', '') == 'base64':
            return 1
        if self.contentparams['type'].startswith('text/'):
            return 0
        if self.contentparams['type'].endswith('+xml'):
            return 0
        if self.contentparams['type'].endswith('/xml'):
            return 0
        return 1

    def _itsAnHrefDamnIt(self, attrsD):
        href = attrsD.get('url', attrsD.get('uri', attrsD.get('href', None)))
        if href:
            try:
                del attrsD['url']
            except KeyError:
                pass
            try:
                del attrsD['uri']
            except KeyError:
                pass
            attrsD['href'] = href
        return attrsD

    def _save(self, key, value):
        context = self._getContext()
        context.setdefault(key, value)

    def _start_rss(self, attrsD):
        versionmap = {'0.91': 'rss091u',
                      '0.92': 'rss092',
                      '0.93': 'rss093',
                      '0.94': 'rss094'}
        #If we're here then this is an RSS feed.
        #If we don't have a version or have a version that starts with something
        #other than RSS then there's been a mistake. Correct it.
        if not self.version or not self.version.startswith('rss'):
            attr_version = attrsD.get('version', '')
            version = versionmap.get(attr_version)
            if version:
                self.version = version
            elif attr_version.startswith('2.'):
                self.version = 'rss20'
            else:
                self.version = 'rss'

    def _start_dlhottitles(self, attrsD):
        self.version = 'hotrss'

    def _start_channel(self, attrsD):
        self.infeed = 1
        self._cdf_common(attrsD)
    _start_feedinfo = _start_channel

    def _cdf_common(self, attrsD):
        if attrsD.has_key('lastmod'):
            self._start_modified({})
            self.elementstack[-1][-1] = attrsD['lastmod']
            self._end_modified()
        if attrsD.has_key('href'):
            self._start_link({})
            self.elementstack[-1][-1] = attrsD['href']
            self._end_link()

    def _start_feed(self, attrsD):
        self.infeed = 1
        versionmap = {'0.1': 'atom01',
                      '0.2': 'atom02',
                      '0.3': 'atom03'}
        if not self.version:
            attr_version = attrsD.get('version')
            version = versionmap.get(attr_version)
            if version:
                self.version = version
            else:
                self.version = 'atom'

    def _end_channel(self):
        self.infeed = 0
    _end_feed = _end_channel

    def _start_image(self, attrsD):
        context = self._getContext()
        context.setdefault('image', FeedParserDict())
        self.inimage = 1
        self.hasTitle = 0
        self.push('image', 0)

    def _end_image(self):
        self.pop('image')
        self.inimage = 0

    def _start_textinput(self, attrsD):
        context = self._getContext()
        context.setdefault('textinput', FeedParserDict())
        self.intextinput = 1
        self.hasTitle = 0
        self.push('textinput', 0)
    _start_textInput = _start_textinput

    def _end_textinput(self):
        self.pop('textinput')
        self.intextinput = 0
    _end_textInput = _end_textinput

    def _start_author(self, attrsD):
        self.inauthor = 1
        self.push('author', 1)
    _start_managingeditor = _start_author
    _start_dc_author = _start_author
    _start_dc_creator = _start_author
    _start_itunes_author = _start_author

    def _end_author(self):
        self.pop('author')
        self.inauthor = 0
        self._sync_author_detail()
    _end_managingeditor = _end_author
    _end_dc_author = _end_author
    _end_dc_creator = _end_author
    _end_itunes_author = _end_author

    def _start_itunes_owner(self, attrsD):
        self.inpublisher = 1
        self.push('publisher', 0)

    def _end_itunes_owner(self):
        self.pop('publisher')
        self.inpublisher = 0
        self._sync_author_detail('publisher')

    def _start_contributor(self, attrsD):
        self.incontributor = 1
        context = self._getContext()
        context.setdefault('contributors', [])
        context['contributors'].append(FeedParserDict())
        self.push('contributor', 0)

    def _end_contributor(self):
        self.pop('contributor')
        self.incontributor = 0

    def _start_dc_contributor(self, attrsD):
        self.incontributor = 1
        context = self._getContext()
        context.setdefault('contributors', [])
        context['contributors'].append(FeedParserDict())
        self.push('name', 0)

    def _end_dc_contributor(self):
        self._end_name()
        self.incontributor = 0

    def _start_name(self, attrsD):
        self.push('name', 0)
    _start_itunes_name = _start_name

    def _end_name(self):
        value = self.pop('name')
        if self.inpublisher:
            self._save_author('name', value, 'publisher')
        elif self.inauthor:
            self._save_author('name', value)
        elif self.incontributor:
            self._save_contributor('name', value)
        elif self.intextinput:
            context = self._getContext()
            context['name'] = value
    _end_itunes_name = _end_name

    def _start_width(self, attrsD):
        self.push('width', 0)

    def _end_width(self):
        value = self.pop('width')
        try:
            value = int(value)
        except:
            value = 0
        if self.inimage:
            context = self._getContext()
            context['width'] = value

    def _start_height(self, attrsD):
        self.push('height', 0)

    def _end_height(self):
        value = self.pop('height')
        try:
            value = int(value)
        except:
            value = 0
        if self.inimage:
            context = self._getContext()
            context['height'] = value

    def _start_url(self, attrsD):
        self.push('href', 1)
    _start_homepage = _start_url
    _start_uri = _start_url

    def _end_url(self):
        value = self.pop('href')
        if self.inauthor:
            self._save_author('href', value)
        elif self.incontributor:
            self._save_contributor('href', value)
    _end_homepage = _end_url
    _end_uri = _end_url

    def _start_email(self, attrsD):
        self.push('email', 0)
    _start_itunes_email = _start_email

    def _end_email(self):
        value = self.pop('email')
        if self.inpublisher:
            self._save_author('email', value, 'publisher')
        elif self.inauthor:
            self._save_author('email', value)
        elif self.incontributor:
            self._save_contributor('email', value)
    _end_itunes_email = _end_email

    def _getContext(self):
        if self.insource:
            context = self.sourcedata
        elif self.inimage and self.feeddata.has_key('image'):
            context = self.feeddata['image']
        elif self.intextinput:
            context = self.feeddata['textinput']
        elif self.inentry:
            context = self.entries[-1]
        else:
            context = self.feeddata
        return context

    def _save_author(self, key, value, prefix='author'):
        context = self._getContext()
        context.setdefault(prefix + '_detail', FeedParserDict())
        context[prefix + '_detail'][key] = value
        self._sync_author_detail()

    def _save_contributor(self, key, value):
        context = self._getContext()
        context.setdefault('contributors', [FeedParserDict()])
        context['contributors'][-1][key] = value

    def _sync_author_detail(self, key='author'):
        context = self._getContext()
        detail = context.get('%s_detail' % key)
        if detail:
            name = detail.get('name')
            email = detail.get('email')
            if name and email:
                context[key] = '%s (%s)' % (name, email)
            elif name:
                context[key] = name
            elif email:
                context[key] = email
        else:
            author, email = context.get(key), None
            if not author: return
            emailmatch = re.search(r'''(([a-zA-Z0-9\_\-\.\+]+)@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.)|(([a-zA-Z0-9\-]+\.)+))([a-zA-Z]{2,4}|[0-9]{1,3})(\]?))(\?subject=\S+)?''', author)
            if emailmatch:
                email = emailmatch.group(0)
                # probably a better way to do the following, but it passes all the tests
                author = author.replace(email, '')
                author = author.replace('()', '')
                author = author.replace('<>', '')
                author = author.replace('&lt;&gt;', '')
                author = author.strip()
                if author and (author[0] == '('):
                    author = author[1:]
                if author and (author[-1] == ')'):
                    author = author[:-1]
                author = author.strip()
            if author or email:
                context.setdefault('%s_detail' % key, FeedParserDict())
            if author:
                context['%s_detail' % key]['name'] = author
            if email:
                context['%s_detail' % key]['email'] = email

    def _start_subtitle(self, attrsD):
        self.pushContent('subtitle', attrsD, 'text/plain', 1)
    _start_tagline = _start_subtitle
    _start_itunes_subtitle = _start_subtitle

    def _end_subtitle(self):
        self.popContent('subtitle')
    _end_tagline = _end_subtitle
    _end_itunes_subtitle = _end_subtitle

    def _start_rights(self, attrsD):
        self.pushContent('rights', attrsD, 'text/plain', 1)
    _start_dc_rights = _start_rights
    _start_copyright = _start_rights

    def _end_rights(self):
        self.popContent('rights')
    _end_dc_rights = _end_rights
    _end_copyright = _end_rights

    def _start_item(self, attrsD):
        self.entries.append(FeedParserDict())
        self.push('item', 0)
        self.inentry = 1
        self.guidislink = 0
        self.hasTitle = 0
        id = self._getAttribute(attrsD, 'rdf:about')
        if id:
            context = self._getContext()
            context['id'] = id
        self._cdf_common(attrsD)
    _start_entry = _start_item
    _start_product = _start_item

    def _end_item(self):
        self.pop('item')
        self.inentry = 0
    _end_entry = _end_item

    def _start_dc_language(self, attrsD):
        self.push('language', 1)
    _start_language = _start_dc_language

    def _end_dc_language(self):
        self.lang = self.pop('language')
    _end_language = _end_dc_language

    def _start_dc_publisher(self, attrsD):
        self.push('publisher', 1)
    _start_webmaster = _start_dc_publisher

    def _end_dc_publisher(self):
        self.pop('publisher')
        self._sync_author_detail('publisher')
    _end_webmaster = _end_dc_publisher

    def _start_published(self, attrsD):
        self.push('published', 1)
    _start_dcterms_issued = _start_published
    _start_issued = _start_published

    def _end_published(self):
        value = self.pop('published')
        self._save('published_parsed', _parse_date(value))
    _end_dcterms_issued = _end_published
    _end_issued = _end_published

    def _start_updated(self, attrsD):
        self.push('updated', 1)
    _start_modified = _start_updated
    _start_dcterms_modified = _start_updated
    _start_pubdate = _start_updated
    _start_dc_date = _start_updated

    def _end_updated(self):
        value = self.pop('updated')
        parsed_value = _parse_date(value)
        self._save('updated_parsed', parsed_value)
    _end_modified = _end_updated
    _end_dcterms_modified = _end_updated
    _end_pubdate = _end_updated
    _end_dc_date = _end_updated

    def _start_created(self, attrsD):
        self.push('created', 1)
    _start_dcterms_created = _start_created

    def _end_created(self):
        value = self.pop('created')
        self._save('created_parsed', _parse_date(value))
    _end_dcterms_created = _end_created

    def _start_expirationdate(self, attrsD):
        self.push('expired', 1)

    def _end_expirationdate(self):
        self._save('expired_parsed', _parse_date(self.pop('expired')))

    def _start_cc_license(self, attrsD):
        context = self._getContext()
        value = self._getAttribute(attrsD, 'rdf:resource')
        attrsD = FeedParserDict()
        attrsD['rel']='license'
        if value: attrsD['href']=value
        context.setdefault('links', []).append(attrsD)

    def _start_creativecommons_license(self, attrsD):
        self.push('license', 1)
    _start_creativeCommons_license = _start_creativecommons_license

    def _end_creativecommons_license(self):
        value = self.pop('license')
        context = self._getContext()
        attrsD = FeedParserDict()
        attrsD['rel']='license'
        if value: attrsD['href']=value
        context.setdefault('links', []).append(attrsD)
        del context['license']
    _end_creativeCommons_license = _end_creativecommons_license

    def _addXFN(self, relationships, href, name):
        context = self._getContext()
        xfn = context.setdefault('xfn', [])
        value = FeedParserDict({'relationships': relationships, 'href': href, 'name': name})
        if value not in xfn:
            xfn.append(value)

    def _addTag(self, term, scheme, label):
        context = self._getContext()
        tags = context.setdefault('tags', [])
        if (not term) and (not scheme) and (not label): return
        value = FeedParserDict({'term': term, 'scheme': scheme, 'label': label})
        if value not in tags:
            tags.append(value)

    def _start_category(self, attrsD):
        if _debug: sys.stderr.write('entering _start_category with %s\n' % repr(attrsD))
        term = attrsD.get('term')
        scheme = attrsD.get('scheme', attrsD.get('domain'))
        label = attrsD.get('label')
        self._addTag(term, scheme, label)
        self.push('category', 1)
    _start_dc_subject = _start_category
    _start_keywords = _start_category

    def _end_itunes_keywords(self):
        for term in self.pop('itunes_keywords').split():
            self._addTag(term, 'http://www.itunes.com/', None)

    def _start_itunes_category(self, attrsD):
        self._addTag(attrsD.get('text'), 'http://www.itunes.com/', None)
        self.push('category', 1)

    def _end_category(self):
        value = self.pop('category')
        if not value: return
        context = self._getContext()
        tags = context['tags']
        if value and len(tags) and not tags[-1]['term']:
            tags[-1]['term'] = value
        else:
            self._addTag(value, None, None)
    _end_dc_subject = _end_category
    _end_keywords = _end_category
    _end_itunes_category = _end_category

    def _start_cloud(self, attrsD):
        self._getContext()['cloud'] = FeedParserDict(attrsD)

    def _start_link(self, attrsD):
        attrsD.setdefault('rel', 'alternate')
        if attrsD['rel'] == 'self':
            attrsD.setdefault('type', 'application/atom+xml')
        else:
            attrsD.setdefault('type', 'text/html')
        context = self._getContext()
        attrsD = self._itsAnHrefDamnIt(attrsD)
        if attrsD.has_key('href'):
            attrsD['href'] = self.resolveURI(attrsD['href'])
            if attrsD.get('rel')=='enclosure' and not context.get('id'):
                context['id'] = attrsD.get('href')
        expectingText = self.infeed or self.inentry or self.insource
        context.setdefault('links', [])
        context['links'].append(FeedParserDict(attrsD))
        if attrsD.has_key('href'):
            expectingText = 0
            if (attrsD.get('rel') == 'alternate') and (self.mapContentType(attrsD.get('type')) in self.html_types):
                context['link'] = attrsD['href']
        else:
            self.push('link', expectingText)
    _start_producturl = _start_link

    def _end_link(self):
        value = self.pop('link')
        context = self._getContext()
    _end_producturl = _end_link

    def _start_guid(self, attrsD):
        self.guidislink = (attrsD.get('ispermalink', 'true') == 'true')
        self.push('id', 1)

    def _end_guid(self):
        value = self.pop('id')
        self._save('guidislink', self.guidislink and not self._getContext().has_key('link'))
        if self.guidislink:
            # guid acts as link, but only if 'ispermalink' is not present or is 'true',
            # and only if the item doesn't already have a link element
            self._save('link', value)

    def _start_title(self, attrsD):
        if self.svgOK: return self.unknown_starttag('title', attrsD.items())
        self.pushContent('title', attrsD, 'text/plain', self.infeed or self.inentry or self.insource)
    _start_dc_title = _start_title
    _start_media_title = _start_title

    def _end_title(self):
        if self.svgOK: return
        value = self.popContent('title')
        if not value: return
        context = self._getContext()
        self.hasTitle = 1
    _end_dc_title = _end_title

    def _end_media_title(self):
        hasTitle = self.hasTitle
        self._end_title()
        self.hasTitle = hasTitle

    def _start_description(self, attrsD):
        context = self._getContext()
        if context.has_key('summary'):
            self._summaryKey = 'content'
            self._start_content(attrsD)
        else:
            self.pushContent('description', attrsD, 'text/html', self.infeed or self.inentry or self.insource)
    _start_dc_description = _start_description

    def _start_abstract(self, attrsD):
        self.pushContent('description', attrsD, 'text/plain', self.infeed or self.inentry or self.insource)

    def _end_description(self):
        if self._summaryKey == 'content':
            self._end_content()
        else:
            value = self.popContent('description')
        self._summaryKey = None
    _end_abstract = _end_description
    _end_dc_description = _end_description

    def _start_info(self, attrsD):
        self.pushContent('info', attrsD, 'text/plain', 1)
    _start_feedburner_browserfriendly = _start_info

    def _end_info(self):
        self.popContent('info')
    _end_feedburner_browserfriendly = _end_info

    def _start_generator(self, attrsD):
        if attrsD:
            attrsD = self._itsAnHrefDamnIt(attrsD)
            if attrsD.has_key('href'):
                attrsD['href'] = self.resolveURI(attrsD['href'])
        self._getContext()['generator_detail'] = FeedParserDict(attrsD)
        self.push('generator', 1)

    def _end_generator(self):
        value = self.pop('generator')
        context = self._getContext()
        if context.has_key('generator_detail'):
            context['generator_detail']['name'] = value

    def _start_admin_generatoragent(self, attrsD):
        self.push('generator', 1)
        value = self._getAttribute(attrsD, 'rdf:resource')
        if value:
            self.elementstack[-1][2].append(value)
        self.pop('generator')
        self._getContext()['generator_detail'] = FeedParserDict({'href': value})

    def _start_admin_errorreportsto(self, attrsD):
        self.push('errorreportsto', 1)
        value = self._getAttribute(attrsD, 'rdf:resource')
        if value:
            self.elementstack[-1][2].append(value)
        self.pop('errorreportsto')

    def _start_summary(self, attrsD):
        context = self._getContext()
        if context.has_key('summary'):
            self._summaryKey = 'content'
            self._start_content(attrsD)
        else:
            self._summaryKey = 'summary'
            self.pushContent(self._summaryKey, attrsD, 'text/plain', 1)
    _start_itunes_summary = _start_summary

    def _end_summary(self):
        if self._summaryKey == 'content':
            self._end_content()
        else:
            self.popContent(self._summaryKey or 'summary')
        self._summaryKey = None
    _end_itunes_summary = _end_summary

    def _start_enclosure(self, attrsD):
        attrsD = self._itsAnHrefDamnIt(attrsD)
        context = self._getContext()
        attrsD['rel']='enclosure'
        context.setdefault('links', []).append(FeedParserDict(attrsD))
        href = attrsD.get('href')
        if href and not context.get('id'):
            context['id'] = href

    def _start_source(self, attrsD):
        if 'url' in attrsD:
          # This means that we're processing a source element from an RSS 2.0 feed
          self.sourcedata['href'] = attrsD[u'url']
        self.push('source', 1)
        self.insource = 1
        self.hasTitle = 0

    def _end_source(self):
        self.insource = 0
        value = self.pop('source')
        if value:
          self.sourcedata['title'] = value
        self._getContext()['source'] = copy.deepcopy(self.sourcedata)
        self.sourcedata.clear()

    def _start_content(self, attrsD):
        self.pushContent('content', attrsD, 'text/plain', 1)
        src = attrsD.get('src')
        if src:
            self.contentparams['src'] = src
        self.push('content', 1)

    def _start_prodlink(self, attrsD):
        self.pushContent('content', attrsD, 'text/html', 1)

    def _start_body(self, attrsD):
        self.pushContent('content', attrsD, 'application/xhtml+xml', 1)
    _start_xhtml_body = _start_body

    def _start_content_encoded(self, attrsD):
        self.pushContent('content', attrsD, 'text/html', 1)
    _start_fullitem = _start_content_encoded

    def _end_content(self):
        copyToDescription = self.mapContentType(self.contentparams.get('type')) in (['text/plain'] + self.html_types)
        value = self.popContent('content')
        if copyToDescription:
            self._save('description', value)

    _end_body = _end_content
    _end_xhtml_body = _end_content
    _end_content_encoded = _end_content
    _end_fullitem = _end_content
    _end_prodlink = _end_content

    def _start_itunes_image(self, attrsD):
        self.push('itunes_image', 0)
        self._getContext()['image'] = FeedParserDict({'href': attrsD.get('href')})
    _start_itunes_link = _start_itunes_image

    def _end_itunes_block(self):
        value = self.pop('itunes_block', 0)
        self._getContext()['itunes_block'] = (value == 'yes') and 1 or 0

    def _end_itunes_explicit(self):
        value = self.pop('itunes_explicit', 0)
        self._getContext()['itunes_explicit'] = (value == 'yes') and 1 or 0

    def _start_media_content(self, attrsD):
        context = self._getContext()
        context.setdefault('media_content', [])
        context['media_content'].append(attrsD)

    def _start_media_thumbnail(self, attrsD):
        context = self._getContext()
        context.setdefault('media_thumbnail', [])
        self.push('url', 1) # new
        context['media_thumbnail'].append(attrsD)

    def _end_media_thumbnail(self):
        url = self.pop('url')
        context = self._getContext()
        if url != None and len(url.strip()) != 0:
            if not context['media_thumbnail'][-1].has_key('url'):
                context['media_thumbnail'][-1]['url'] = url

    def _start_media_player(self, attrsD):
        self.push('media_player', 0)
        self._getContext()['media_player'] = FeedParserDict(attrsD)

    def _end_media_player(self):
        value = self.pop('media_player')
        context = self._getContext()
        context['media_player']['content'] = value

if _XML_AVAILABLE:
    class _StrictFeedParser(_FeedParserMixin, xml.sax.handler.ContentHandler):
        def __init__(self, baseuri, baselang, encoding):
            if _debug: sys.stderr.write('trying StrictFeedParser\n')
            xml.sax.handler.ContentHandler.__init__(self)
            _FeedParserMixin.__init__(self, baseuri, baselang, encoding)
            self.bozo = 0
            self.exc = None
            self.decls = {}

        def startPrefixMapping(self, prefix, uri):
            self.trackNamespace(prefix, uri)
            if uri == 'http://www.w3.org/1999/xlink':
              self.decls['xmlns:'+prefix] = uri

        def startElementNS(self, name, qname, attrs):
            namespace, localname = name
            lowernamespace = str(namespace or '').lower()
            if lowernamespace.find('backend.userland.com/rss') <> -1:
                # match any backend.userland.com namespace
                namespace = 'http://backend.userland.com/rss'
                lowernamespace = namespace
            if qname and qname.find(':') > 0:
                givenprefix = qname.split(':')[0]
            else:
                givenprefix = None
            prefix = self._matchnamespaces.get(lowernamespace, givenprefix)
            if givenprefix and (prefix == None or (prefix == '' and lowernamespace == '')) and not self.namespacesInUse.has_key(givenprefix):
                    raise UndeclaredNamespace, "'%s' is not associated with a namespace" % givenprefix
            localname = str(localname).lower()

            # qname implementation is horribly broken in Python 2.1 (it
            # doesn't report any), and slightly broken in Python 2.2 (it
            # doesn't report the xml: namespace). So we match up namespaces
            # with a known list first, and then possibly override them with
            # the qnames the SAX parser gives us (if indeed it gives us any
            # at all).  Thanks to MatejC for helping me test this and
            # tirelessly telling me that it didn't work yet.
            attrsD, self.decls = self.decls, {}
            if localname=='math' and namespace=='http://www.w3.org/1998/Math/MathML':
                attrsD['xmlns']=namespace
            if localname=='svg' and namespace=='http://www.w3.org/2000/svg':
                attrsD['xmlns']=namespace

            if prefix:
                localname = prefix.lower() + ':' + localname
            elif namespace and not qname: #Expat
                for name,value in self.namespacesInUse.items():
                     if name and value == namespace:
                         localname = name + ':' + localname
                         break
            if _debug: sys.stderr.write('startElementNS: qname = %s, namespace = %s, givenprefix = %s, prefix = %s, attrs = %s, localname = %s\n' % (qname, namespace, givenprefix, prefix, attrs.items(), localname))

            for (namespace, attrlocalname), attrvalue in attrs._attrs.items():
                lowernamespace = (namespace or '').lower()
                prefix = self._matchnamespaces.get(lowernamespace, '')
                if prefix:
                    attrlocalname = prefix + ':' + attrlocalname
                attrsD[str(attrlocalname).lower()] = attrvalue
            for qname in attrs.getQNames():
                attrsD[str(qname).lower()] = attrs.getValueByQName(qname)
            self.unknown_starttag(localname, attrsD.items())

        def characters(self, text):
            self.handle_data(text)

        def endElementNS(self, name, qname):
            namespace, localname = name
            lowernamespace = str(namespace or '').lower()
            if qname and qname.find(':') > 0:
                givenprefix = qname.split(':')[0]
            else:
                givenprefix = ''
            prefix = self._matchnamespaces.get(lowernamespace, givenprefix)
            if prefix:
                localname = prefix + ':' + localname
            elif namespace and not qname: #Expat
                for name,value in self.namespacesInUse.items():
                     if name and value == namespace:
                         localname = name + ':' + localname
                         break
            localname = str(localname).lower()
            self.unknown_endtag(localname)

        def error(self, exc):
            self.bozo = 1
            self.exc = exc

        def fatalError(self, exc):
            self.error(exc)
            raise exc

class _BaseHTMLProcessor(sgmllib.SGMLParser):
    special = re.compile('''[<>'"]''')
    bare_ampersand = re.compile("&(?!#\d+;|#x[0-9a-fA-F]+;|\w+;)")
    elements_no_end_tag = [
      'area', 'base', 'basefont', 'br', 'col', 'command', 'embed', 'frame',
      'hr', 'img', 'input', 'isindex', 'keygen', 'link', 'meta', 'param',
      'source', 'track', 'wbr'
    ]

    def __init__(self, encoding, type):
        self.encoding = encoding
        self.type = type
        if _debug: sys.stderr.write('entering BaseHTMLProcessor, encoding=%s\n' % self.encoding)
        sgmllib.SGMLParser.__init__(self)

    def reset(self):
        self.pieces = []
        sgmllib.SGMLParser.reset(self)

    def _shorttag_replace(self, match):
        tag = match.group(1)
        if tag in self.elements_no_end_tag:
            return '<' + tag + ' />'
        else:
            return '<' + tag + '></' + tag + '>'

    def parse_starttag(self,i):
        j=sgmllib.SGMLParser.parse_starttag(self, i)
        if self.type == 'application/xhtml+xml':
            if j>2 and self.rawdata[j-2:j]=='/>':
                self.unknown_endtag(self.lasttag)
        return j

    def feed(self, data):
        data = re.compile(r'<!((?!DOCTYPE|--|\[))', re.IGNORECASE).sub(r'&lt;!\1', data)
        #data = re.sub(r'<(\S+?)\s*?/>', self._shorttag_replace, data) # bug [ 1399464 ] Bad regexp for _shorttag_replace
        data = re.sub(r'<([^<>\s]+?)\s*/>', self._shorttag_replace, data)
        data = data.replace('&#39;', "'")
        data = data.replace('&#34;', '"')
        if self.encoding and type(data) == type(u''):
            data = data.encode(self.encoding)
        sgmllib.SGMLParser.feed(self, data)
        sgmllib.SGMLParser.close(self)

    def normalize_attrs(self, attrs):
        if not attrs: return attrs
        # utility method to be called by descendants
        attrs = dict([(k.lower(), v) for k, v in attrs]).items()
        attrs = [(k, k in ('rel', 'type') and v.lower() or v) for k, v in attrs]
        attrs.sort()
        return attrs

    def unknown_starttag(self, tag, attrs):
        # called for each start tag
        # attrs is a list of (attr, value) tuples
        # e.g. for <pre class='screen'>, tag='pre', attrs=[('class', 'screen')]
        if _debug: sys.stderr.write('_BaseHTMLProcessor, unknown_starttag, tag=%s\n' % tag)
        uattrs = []
        strattrs=''
        if attrs:
            for key, value in attrs:
                value=value.replace('>','&gt;').replace('<','&lt;').replace('"','&quot;')
                value = self.bare_ampersand.sub("&amp;", value)
                # thanks to Kevin Marks for this breathtaking hack to deal with (valid) high-bit attribute values in UTF-8 feeds
                if type(value) != type(u''):
                    try:
                        value = unicode(value, self.encoding)
                    except:
                        value = unicode(value, 'iso-8859-1')
                uattrs.append((unicode(key, self.encoding), value))
            strattrs = u''.join([u' %s="%s"' % (key, value) for key, value in uattrs])
            if self.encoding:
                try:
                    strattrs=strattrs.encode(self.encoding)
                except:
                    pass
        if tag in self.elements_no_end_tag:
            self.pieces.append('<%(tag)s%(strattrs)s />' % locals())
        else:
            self.pieces.append('<%(tag)s%(strattrs)s>' % locals())

    def unknown_endtag(self, tag):
        # called for each end tag, e.g. for </pre>, tag will be 'pre'
        # Reconstruct the original end tag.
        if tag not in self.elements_no_end_tag:
            self.pieces.append("</%(tag)s>" % locals())

    def handle_charref(self, ref):
        # called for each character reference, e.g. for '&#160;', ref will be '160'
        # Reconstruct the original character reference.
        if ref.startswith('x'):
            value = unichr(int(ref[1:],16))
        else:
            value = unichr(int(ref))

        if value in _cp1252.keys():
            self.pieces.append('&#%s;' % hex(ord(_cp1252[value]))[1:])
        else:
            self.pieces.append('&#%(ref)s;' % locals())

    def handle_entityref(self, ref):
        # called for each entity reference, e.g. for '&copy;', ref will be 'copy'
        # Reconstruct the original entity reference.
        if name2codepoint.has_key(ref):
            self.pieces.append('&%(ref)s;' % locals())
        else:
            self.pieces.append('&amp;%(ref)s' % locals())

    def handle_data(self, text):
        # called for each block of plain text, i.e. outside of any tag and
        # not containing any character or entity references
        # Store the original text verbatim.
        if _debug: sys.stderr.write('_BaseHTMLProcessor, handle_data, text=%s\n' % text)
        self.pieces.append(text)

    def handle_comment(self, text):
        # called for each HTML comment, e.g. <!-- insert Javascript code here -->
        # Reconstruct the original comment.
        self.pieces.append('<!--%(text)s-->' % locals())

    def handle_pi(self, text):
        # called for each processing instruction, e.g. <?instruction>
        # Reconstruct original processing instruction.
        self.pieces.append('<?%(text)s>' % locals())

    def handle_decl(self, text):
        # called for the DOCTYPE, if present, e.g.
        # <!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN"
        #     "http://www.w3.org/TR/html4/loose.dtd">
        # Reconstruct original DOCTYPE
        self.pieces.append('<!%(text)s>' % locals())

    _new_declname_match = re.compile(r'[a-zA-Z][-_.a-zA-Z0-9:]*\s*').match
    def _scan_name(self, i, declstartpos):
        rawdata = self.rawdata
        n = len(rawdata)
        if i == n:
            return None, -1
        m = self._new_declname_match(rawdata, i)
        if m:
            s = m.group()
            name = s.strip()
            if (i + len(s)) == n:
                return None, -1  # end of buffer
            return name.lower(), m.end()
        else:
            self.handle_data(rawdata)
#            self.updatepos(declstartpos, i)
            return None, -1

    def convert_charref(self, name):
        return '&#%s;' % name

    def convert_entityref(self, name):
        return '&%s;' % name

    def output(self):
        '''Return processed HTML as a single string'''
        return ''.join([str(p) for p in self.pieces])

class _LooseFeedParser(_FeedParserMixin, _BaseHTMLProcessor):
    def __init__(self, baseuri, baselang, encoding, entities):
        sgmllib.SGMLParser.__init__(self)
        _FeedParserMixin.__init__(self, baseuri, baselang, encoding)
        _BaseHTMLProcessor.__init__(self, encoding, 'application/xhtml+xml')
        self.entities=entities

    def decodeEntities(self, element, data):
        data = data.replace('&#60;', '&lt;')
        data = data.replace('&#x3c;', '&lt;')
        data = data.replace('&#x3C;', '&lt;')
        data = data.replace('&#62;', '&gt;')
        data = data.replace('&#x3e;', '&gt;')
        data = data.replace('&#x3E;', '&gt;')
        data = data.replace('&#38;', '&amp;')
        data = data.replace('&#x26;', '&amp;')
        data = data.replace('&#34;', '&quot;')
        data = data.replace('&#x22;', '&quot;')
        data = data.replace('&#39;', '&apos;')
        data = data.replace('&#x27;', '&apos;')
        if self.contentparams.has_key('type') and not self.contentparams.get('type', 'xml').endswith('xml'):
            data = data.replace('&lt;', '<')
            data = data.replace('&gt;', '>')
            data = data.replace('&amp;', '&')
            data = data.replace('&quot;', '"')
            data = data.replace('&apos;', "'")
        return data

    def strattrs(self, attrs):
        return ''.join([' %s="%s"' % (n,v.replace('"','&quot;')) for n,v in attrs])

class _MicroformatsParser:
    STRING = 1
    DATE = 2
    URI = 3
    NODE = 4
    EMAIL = 5

    known_xfn_relationships = ['contact', 'acquaintance', 'friend', 'met', 'co-worker', 'coworker', 'colleague', 'co-resident', 'coresident', 'neighbor', 'child', 'parent', 'sibling', 'brother', 'sister', 'spouse', 'wife', 'husband', 'kin', 'relative', 'muse', 'crush', 'date', 'sweetheart', 'me']
    known_binary_extensions =  ['zip','rar','exe','gz','tar','tgz','tbz2','bz2','z','7z','dmg','img','sit','sitx','hqx','deb','rpm','bz2','jar','rar','iso','bin','msi','mp2','mp3','ogg','ogm','mp4','m4v','m4a','avi','wma','wmv']

    def __init__(self, data, baseuri, encoding):
        self.document = BeautifulSoup.BeautifulSoup(data)
        self.baseuri = baseuri
        self.encoding = encoding
        if type(data) == type(u''):
            data = data.encode(encoding)
        self.tags = []
        self.enclosures = []
        self.xfn = []
        self.vcard = None

    def vcardEscape(self, s):
        if type(s) in (type(''), type(u'')):
            s = s.replace(',', '\\,').replace(';', '\\;').replace('\n', '\\n')
        return s

    def vcardFold(self, s):
        s = re.sub(';+$', '', s)
        sFolded = ''
        iMax = 75
        sPrefix = ''
        while len(s) > iMax:
            sFolded += sPrefix + s[:iMax] + '\n'
            s = s[iMax:]
            sPrefix = ' '
            iMax = 74
        sFolded += sPrefix + s
        return sFolded

    def normalize(self, s):
        return re.sub(r'\s+', ' ', s).strip()

    def unique(self, aList):
        results = []
        for element in aList:
            if element not in results:
                results.append(element)
        return results

    def toISO8601(self, dt):
        return time.strftime('%Y-%m-%dT%H:%M:%SZ', dt)

    def getPropertyValue(self, elmRoot, sProperty, iPropertyType=4, bAllowMultiple=0, bAutoEscape=0):
        all = lambda x: 1
        sProperty = sProperty.lower()
        bFound = 0
        bNormalize = 1
        propertyMatch = {'class': re.compile(r'\b%s\b' % sProperty)}
        if bAllowMultiple and (iPropertyType != self.NODE):
            snapResults = []
            containers = elmRoot(['ul', 'ol'], propertyMatch)
            for container in containers:
                snapResults.extend(container('li'))
            bFound = (len(snapResults) != 0)
        if not bFound:
            snapResults = elmRoot(all, propertyMatch)
            bFound = (len(snapResults) != 0)
        if (not bFound) and (sProperty == 'value'):
            snapResults = elmRoot('pre')
            bFound = (len(snapResults) != 0)
            bNormalize = not bFound
            if not bFound:
                snapResults = [elmRoot]
                bFound = (len(snapResults) != 0)
        arFilter = []
        if sProperty == 'vcard':
            snapFilter = elmRoot(all, propertyMatch)
            for node in snapFilter:
                if node.findParent(all, propertyMatch):
                    arFilter.append(node)
        arResults = []
        for node in snapResults:
            if node not in arFilter:
                arResults.append(node)
        bFound = (len(arResults) != 0)
        if not bFound:
            if bAllowMultiple: return []
            elif iPropertyType == self.STRING: return ''
            elif iPropertyType == self.DATE: return None
            elif iPropertyType == self.URI: return ''
            elif iPropertyType == self.NODE: return None
            else: return None
        arValues = []
        for elmResult in arResults:
            sValue = None
            if iPropertyType == self.NODE:
                if bAllowMultiple:
                    arValues.append(elmResult)
                    continue
                else:
                    return elmResult
            sNodeName = elmResult.name.lower()
            if (iPropertyType == self.EMAIL) and (sNodeName == 'a'):
                sValue = (elmResult.get('href') or '').split('mailto:').pop().split('?')[0]
            if sValue:
                sValue = bNormalize and self.normalize(sValue) or sValue.strip()
            if (not sValue) and (sNodeName == 'abbr'):
                sValue = elmResult.get('title')
            if sValue:
                sValue = bNormalize and self.normalize(sValue) or sValue.strip()
            if (not sValue) and (iPropertyType == self.URI):
                if sNodeName == 'a': sValue = elmResult.get('href')
                elif sNodeName == 'img': sValue = elmResult.get('src')
                elif sNodeName == 'object': sValue = elmResult.get('data')
            if sValue:
                sValue = bNormalize and self.normalize(sValue) or sValue.strip()
            if (not sValue) and (sNodeName == 'img'):
                sValue = elmResult.get('alt')
            if sValue:
                sValue = bNormalize and self.normalize(sValue) or sValue.strip()
            if not sValue:
                sValue = elmResult.renderContents()
                sValue = re.sub(r'<\S[^>]*>', '', sValue)
                sValue = sValue.replace('\r\n', '\n')
                sValue = sValue.replace('\r', '\n')
            if sValue:
                sValue = bNormalize and self.normalize(sValue) or sValue.strip()
            if not sValue: continue
            if iPropertyType == self.DATE:
                sValue = _parse_date_iso8601(sValue)
            if bAllowMultiple:
                arValues.append(bAutoEscape and self.vcardEscape(sValue) or sValue)
            else:
                return bAutoEscape and self.vcardEscape(sValue) or sValue
        return arValues

    def findVCards(self, elmRoot, bAgentParsing=0):
        sVCards = ''

        if not bAgentParsing:
            arCards = self.getPropertyValue(elmRoot, 'vcard', bAllowMultiple=1)
        else:
            arCards = [elmRoot]

        for elmCard in arCards:
            arLines = []

            def processSingleString(sProperty):
                sValue = self.getPropertyValue(elmCard, sProperty, self.STRING, bAutoEscape=1)
                if sValue:
                    arLines.append(self.vcardFold(sProperty.upper() + ':' + sValue))
                return sValue or ''

            def processSingleURI(sProperty):
                sValue = self.getPropertyValue(elmCard, sProperty, self.URI)
                if sValue:
                    sContentType = ''
                    sEncoding = ''
                    sValueKey = ''
                    if sValue.startswith('data:'):
                        sEncoding = ';ENCODING=b'
                        sContentType = sValue.split(';')[0].split('/').pop()
                        sValue = sValue.split(',', 1).pop()
                    else:
                        elmValue = self.getPropertyValue(elmCard, sProperty)
                        if elmValue:
                            if sProperty != 'url':
                                sValueKey = ';VALUE=uri'
                            sContentType = elmValue.get('type', '').strip().split('/').pop().strip()
                    sContentType = sContentType.upper()
                    if sContentType == 'OCTET-STREAM':
                        sContentType = ''
                    if sContentType:
                        sContentType = ';TYPE=' + sContentType.upper()
                    arLines.append(self.vcardFold(sProperty.upper() + sEncoding + sContentType + sValueKey + ':' + sValue))

            def processTypeValue(sProperty, arDefaultType, arForceType=None):
                arResults = self.getPropertyValue(elmCard, sProperty, bAllowMultiple=1)
                for elmResult in arResults:
                    arType = self.getPropertyValue(elmResult, 'type', self.STRING, 1, 1)
                    if arForceType:
                        arType = self.unique(arForceType + arType)
                    if not arType:
                        arType = arDefaultType
                    sValue = self.getPropertyValue(elmResult, 'value', self.EMAIL, 0)
                    if sValue:
                        arLines.append(self.vcardFold(sProperty.upper() + ';TYPE=' + ','.join(arType) + ':' + sValue))

            # AGENT
            # must do this before all other properties because it is destructive
            # (removes nested class="vcard" nodes so they don't interfere with
            # this vcard's other properties)
            arAgent = self.getPropertyValue(elmCard, 'agent', bAllowMultiple=1)
            for elmAgent in arAgent:
                if re.compile(r'\bvcard\b').search(elmAgent.get('class')):
                    sAgentValue = self.findVCards(elmAgent, 1) + '\n'
                    sAgentValue = sAgentValue.replace('\n', '\\n')
                    sAgentValue = sAgentValue.replace(';', '\\;')
                    if sAgentValue:
                        arLines.append(self.vcardFold('AGENT:' + sAgentValue))
                    elmAgent['class'] = ''
                    elmAgent.contents = []
                else:
                    sAgentValue = self.getPropertyValue(elmAgent, 'value', self.URI, bAutoEscape=1);
                    if sAgentValue:
                        arLines.append(self.vcardFold('AGENT;VALUE=uri:' + sAgentValue))

            # FN (full name)
            sFN = processSingleString('fn')

            # N (name)
            elmName = self.getPropertyValue(elmCard, 'n')
            if elmName:
                sFamilyName = self.getPropertyValue(elmName, 'family-name', self.STRING, bAutoEscape=1)
                sGivenName = self.getPropertyValue(elmName, 'given-name', self.STRING, bAutoEscape=1)
                arAdditionalNames = self.getPropertyValue(elmName, 'additional-name', self.STRING, 1, 1) + self.getPropertyValue(elmName, 'additional-names', self.STRING, 1, 1)
                arHonorificPrefixes = self.getPropertyValue(elmName, 'honorific-prefix', self.STRING, 1, 1) + self.getPropertyValue(elmName, 'honorific-prefixes', self.STRING, 1, 1)
                arHonorificSuffixes = self.getPropertyValue(elmName, 'honorific-suffix', self.STRING, 1, 1) + self.getPropertyValue(elmName, 'honorific-suffixes', self.STRING, 1, 1)
                arLines.append(self.vcardFold('N:' + sFamilyName + ';' +
                                         sGivenName + ';' +
                                         ','.join(arAdditionalNames) + ';' +
                                         ','.join(arHonorificPrefixes) + ';' +
                                         ','.join(arHonorificSuffixes)))
            elif sFN:
                # implied "N" optimization
                # http://microformats.org/wiki/hcard#Implied_.22N.22_Optimization
                arNames = self.normalize(sFN).split()
                if len(arNames) == 2:
                    bFamilyNameFirst = (arNames[0].endswith(',') or
                                        len(arNames[1]) == 1 or
                                        ((len(arNames[1]) == 2) and (arNames[1].endswith('.'))))
                    if bFamilyNameFirst:
                        arLines.append(self.vcardFold('N:' + arNames[0] + ';' + arNames[1]))
                    else:
                        arLines.append(self.vcardFold('N:' + arNames[1] + ';' + arNames[0]))

            # SORT-STRING
            sSortString = self.getPropertyValue(elmCard, 'sort-string', self.STRING, bAutoEscape=1)
            if sSortString:
                arLines.append(self.vcardFold('SORT-STRING:' + sSortString))

            # NICKNAME
            arNickname = self.getPropertyValue(elmCard, 'nickname', self.STRING, 1, 1)
            if arNickname:
                arLines.append(self.vcardFold('NICKNAME:' + ','.join(arNickname)))

            # PHOTO
            processSingleURI('photo')

            # BDAY
            dtBday = self.getPropertyValue(elmCard, 'bday', self.DATE)
            if dtBday:
                arLines.append(self.vcardFold('BDAY:' + self.toISO8601(dtBday)))

            # ADR (address)
            arAdr = self.getPropertyValue(elmCard, 'adr', bAllowMultiple=1)
            for elmAdr in arAdr:
                arType = self.getPropertyValue(elmAdr, 'type', self.STRING, 1, 1)
                if not arType:
                    arType = ['intl','postal','parcel','work'] # default adr types, see RFC 2426 section 3.2.1
                sPostOfficeBox = self.getPropertyValue(elmAdr, 'post-office-box', self.STRING, 0, 1)
                sExtendedAddress = self.getPropertyValue(elmAdr, 'extended-address', self.STRING, 0, 1)
                sStreetAddress = self.getPropertyValue(elmAdr, 'street-address', self.STRING, 0, 1)
                sLocality = self.getPropertyValue(elmAdr, 'locality', self.STRING, 0, 1)
                sRegion = self.getPropertyValue(elmAdr, 'region', self.STRING, 0, 1)
                sPostalCode = self.getPropertyValue(elmAdr, 'postal-code', self.STRING, 0, 1)
                sCountryName = self.getPropertyValue(elmAdr, 'country-name', self.STRING, 0, 1)
                arLines.append(self.vcardFold('ADR;TYPE=' + ','.join(arType) + ':' +
                                         sPostOfficeBox + ';' +
                                         sExtendedAddress + ';' +
                                         sStreetAddress + ';' +
                                         sLocality + ';' +
                                         sRegion + ';' +
                                         sPostalCode + ';' +
                                         sCountryName))

            # LABEL
            processTypeValue('label', ['intl','postal','parcel','work'])

            # TEL (phone number)
            processTypeValue('tel', ['voice'])

            # EMAIL
            processTypeValue('email', ['internet'], ['internet'])

            # MAILER
            processSingleString('mailer')

            # TZ (timezone)
            processSingleString('tz')

            # GEO (geographical information)
            elmGeo = self.getPropertyValue(elmCard, 'geo')
            if elmGeo:
                sLatitude = self.getPropertyValue(elmGeo, 'latitude', self.STRING, 0, 1)
                sLongitude = self.getPropertyValue(elmGeo, 'longitude', self.STRING, 0, 1)
                arLines.append(self.vcardFold('GEO:' + sLatitude + ';' + sLongitude))

            # TITLE
            processSingleString('title')

            # ROLE
            processSingleString('role')

            # LOGO
            processSingleURI('logo')

            # ORG (organization)
            elmOrg = self.getPropertyValue(elmCard, 'org')
            if elmOrg:
                sOrganizationName = self.getPropertyValue(elmOrg, 'organization-name', self.STRING, 0, 1)
                if not sOrganizationName:
                    # implied "organization-name" optimization
                    # http://microformats.org/wiki/hcard#Implied_.22organization-name.22_Optimization
                    sOrganizationName = self.getPropertyValue(elmCard, 'org', self.STRING, 0, 1)
                    if sOrganizationName:
                        arLines.append(self.vcardFold('ORG:' + sOrganizationName))
                else:
                    arOrganizationUnit = self.getPropertyValue(elmOrg, 'organization-unit', self.STRING, 1, 1)
                    arLines.append(self.vcardFold('ORG:' + sOrganizationName + ';' + ';'.join(arOrganizationUnit)))

            # CATEGORY
            arCategory = self.getPropertyValue(elmCard, 'category', self.STRING, 1, 1) + self.getPropertyValue(elmCard, 'categories', self.STRING, 1, 1)
            if arCategory:
                arLines.append(self.vcardFold('CATEGORIES:' + ','.join(arCategory)))

            # NOTE
            processSingleString('note')

            # REV
            processSingleString('rev')

            # SOUND
            processSingleURI('sound')

            # UID
            processSingleString('uid')

            # URL
            processSingleURI('url')

            # CLASS
            processSingleString('class')

            # KEY
            processSingleURI('key')

            if arLines:
                arLines = ['BEGIN:vCard','VERSION:3.0'] + arLines + ['END:vCard']
                sVCards += '\n'.join(arLines) + '\n'

        return sVCards.strip()

    def isProbablyDownloadable(self, elm):
        attrsD = elm.attrMap
        if not attrsD.has_key('href'): return 0
        linktype = attrsD.get('type', '').strip()
        if linktype.startswith('audio/') or \
           linktype.startswith('video/') or \
           (linktype.startswith('application/') and not linktype.endswith('xml')):
            return 1
        path = urlparse.urlparse(attrsD['href'])[2]
        if path.find('.') == -1: return 0
        fileext = path.split('.').pop().lower()
        return fileext in self.known_binary_extensions

    def findTags(self):
        all = lambda x: 1
        for elm in self.document(all, {'rel': re.compile(r'\btag\b')}):
            href = elm.get('href')
            if not href: continue
            urlscheme, domain, path, params, query, fragment = \
                       urlparse.urlparse(_urljoin(self.baseuri, href))
            segments = path.split('/')
            tag = segments.pop()
            if not tag:
                tag = segments.pop()
            tagscheme = urlparse.urlunparse((urlscheme, domain, '/'.join(segments), '', '', ''))
            if not tagscheme.endswith('/'):
                tagscheme += '/'
            self.tags.append(FeedParserDict({"term": tag, "scheme": tagscheme, "label": elm.string or ''}))

    def findEnclosures(self):
        all = lambda x: 1
        enclosure_match = re.compile(r'\benclosure\b')
        for elm in self.document(all, {'href': re.compile(r'.+')}):
            if not enclosure_match.search(elm.get('rel', '')) and not self.isProbablyDownloadable(elm): continue
            if elm.attrMap not in self.enclosures:
                self.enclosures.append(elm.attrMap)
                if elm.string and not elm.get('title'):
                    self.enclosures[-1]['title'] = elm.string

    def findXFN(self):
        all = lambda x: 1
        for elm in self.document(all, {'rel': re.compile('.+'), 'href': re.compile('.+')}):
            rels = elm.get('rel', '').split()
            xfn_rels = []
            for rel in rels:
                if rel in self.known_xfn_relationships:
                    xfn_rels.append(rel)
            if xfn_rels:
                self.xfn.append({"relationships": xfn_rels, "href": elm.get('href', ''), "name": elm.string})

def _parseMicroformats(htmlSource, baseURI, encoding):
    if not BeautifulSoup: return
    if _debug: sys.stderr.write('entering _parseMicroformats\n')
    p = _MicroformatsParser(htmlSource, baseURI, encoding)
    p.vcard = p.findVCards(p.document)
    p.findTags()
    p.findEnclosures()
    p.findXFN()
    return {"tags": p.tags, "enclosures": p.enclosures, "xfn": p.xfn, "vcard": p.vcard}

class _RelativeURIResolver(_BaseHTMLProcessor):
    relative_uris = [('a', 'href'),
                     ('applet', 'codebase'),
                     ('area', 'href'),
                     ('blockquote', 'cite'),
                     ('body', 'background'),
                     ('del', 'cite'),
                     ('form', 'action'),
                     ('frame', 'longdesc'),
                     ('frame', 'src'),
                     ('iframe', 'longdesc'),
                     ('iframe', 'src'),
                     ('head', 'profile'),
                     ('img', 'longdesc'),
                     ('img', 'src'),
                     ('img', 'usemap'),
                     ('input', 'src'),
                     ('input', 'usemap'),
                     ('ins', 'cite'),
                     ('link', 'href'),
                     ('object', 'classid'),
                     ('object', 'codebase'),
                     ('object', 'data'),
                     ('object', 'usemap'),
                     ('q', 'cite'),
                     ('script', 'src')]

    def __init__(self, baseuri, encoding, type):
        _BaseHTMLProcessor.__init__(self, encoding, type)
        self.baseuri = baseuri

    def resolveURI(self, uri):
        return _urljoin(self.baseuri, uri.strip())

    def unknown_starttag(self, tag, attrs):
        if _debug:
            sys.stderr.write('tag: [%s] with attributes: [%s]\n' % (tag, str(attrs)))
        attrs = self.normalize_attrs(attrs)
        attrs = [(key, ((tag, key) in self.relative_uris) and self.resolveURI(value) or value) for key, value in attrs]
        _BaseHTMLProcessor.unknown_starttag(self, tag, attrs)

def _resolveRelativeURIs(htmlSource, baseURI, encoding, type):
    if _debug:
        sys.stderr.write('entering _resolveRelativeURIs\n')

    p = _RelativeURIResolver(baseURI, encoding, type)
    p.feed(htmlSource)
    return p.output()

class _HTMLSanitizer(_BaseHTMLProcessor):
    acceptable_elements = ['a', 'abbr', 'acronym', 'address', 'area', 'article',
      'aside', 'audio', 'b', 'big', 'blockquote', 'br', 'button', 'canvas',
      'caption', 'center', 'cite', 'code', 'col', 'colgroup', 'command',
      'datagrid', 'datalist', 'dd', 'del', 'details', 'dfn', 'dialog', 'dir',
      'div', 'dl', 'dt', 'em', 'event-source', 'fieldset', 'figure', 'footer',
      'font', 'form', 'header', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'hr', 'i',
      'img', 'input', 'ins', 'keygen', 'kbd', 'label', 'legend', 'li', 'm', 'map',
      'menu', 'meter', 'multicol', 'nav', 'nextid', 'ol', 'output', 'optgroup',
      'option', 'p', 'pre', 'progress', 'q', 's', 'samp', 'section', 'select',
      'small', 'sound', 'source', 'spacer', 'span', 'strike', 'strong', 'sub',
      'sup', 'table', 'tbody', 'td', 'textarea', 'time', 'tfoot', 'th', 'thead',
      'tr', 'tt', 'u', 'ul', 'var', 'video', 'noscript']

    acceptable_attributes = ['abbr', 'accept', 'accept-charset', 'accesskey',
      'action', 'align', 'alt', 'autocomplete', 'autofocus', 'axis',
      'background', 'balance', 'bgcolor', 'bgproperties', 'border',
      'bordercolor', 'bordercolordark', 'bordercolorlight', 'bottompadding',
      'cellpadding', 'cellspacing', 'ch', 'challenge', 'char', 'charoff',
      'choff', 'charset', 'checked', 'cite', 'class', 'clear', 'color', 'cols',
      'colspan', 'compact', 'contenteditable', 'controls', 'coords', 'data',
      'datafld', 'datapagesize', 'datasrc', 'datetime', 'default', 'delay',
      'dir', 'disabled', 'draggable', 'dynsrc', 'enctype', 'end', 'face', 'for',
      'form', 'frame', 'galleryimg', 'gutter', 'headers', 'height', 'hidefocus',
      'hidden', 'high', 'href', 'hreflang', 'hspace', 'icon', 'id', 'inputmode',
      'ismap', 'keytype', 'label', 'leftspacing', 'lang', 'list', 'longdesc',
      'loop', 'loopcount', 'loopend', 'loopstart', 'low', 'lowsrc', 'max',
      'maxlength', 'media', 'method', 'min', 'multiple', 'name', 'nohref',
      'noshade', 'nowrap', 'open', 'optimum', 'pattern', 'ping', 'point-size',
      'prompt', 'pqg', 'radiogroup', 'readonly', 'rel', 'repeat-max',
      'repeat-min', 'replace', 'required', 'rev', 'rightspacing', 'rows',
      'rowspan', 'rules', 'scope', 'selected', 'shape', 'size', 'span', 'src',
      'start', 'step', 'summary', 'suppress', 'tabindex', 'target', 'template',
      'title', 'toppadding', 'type', 'unselectable', 'usemap', 'urn', 'valign',
      'value', 'variable', 'volume', 'vspace', 'vrml', 'width', 'wrap',
      'xml:lang']

    unacceptable_elements_with_end_tag = ['script', 'applet', 'style']

    acceptable_css_properties = ['azimuth', 'background-color',
      'border-bottom-color', 'border-collapse', 'border-color',
      'border-left-color', 'border-right-color', 'border-top-color', 'clear',
      'color', 'cursor', 'direction', 'display', 'elevation', 'float', 'font',
      'font-family', 'font-size', 'font-style', 'font-variant', 'font-weight',
      'height', 'letter-spacing', 'line-height', 'overflow', 'pause',
      'pause-after', 'pause-before', 'pitch', 'pitch-range', 'richness',
      'speak', 'speak-header', 'speak-numeral', 'speak-punctuation',
      'speech-rate', 'stress', 'text-align', 'text-decoration', 'text-indent',
      'unicode-bidi', 'vertical-align', 'voice-family', 'volume',
      'white-space', 'width']

    # survey of common keywords found in feeds
    acceptable_css_keywords = ['auto', 'aqua', 'black', 'block', 'blue',
      'bold', 'both', 'bottom', 'brown', 'center', 'collapse', 'dashed',
      'dotted', 'fuchsia', 'gray', 'green', '!important', 'italic', 'left',
      'lime', 'maroon', 'medium', 'none', 'navy', 'normal', 'nowrap', 'olive',
      'pointer', 'purple', 'red', 'right', 'solid', 'silver', 'teal', 'top',
      'transparent', 'underline', 'white', 'yellow']

    valid_css_values = re.compile('^(#[0-9a-f]+|rgb\(\d+%?,\d*%?,?\d*%?\)?|' +
      '\d{0,2}\.?\d{0,2}(cm|em|ex|in|mm|pc|pt|px|%|,|\))?)$')

    mathml_elements = ['annotation', 'annotation-xml', 'maction', 'math',
      'merror', 'mfenced', 'mfrac', 'mi', 'mmultiscripts', 'mn', 'mo', 'mover', 'mpadded',
      'mphantom', 'mprescripts', 'mroot', 'mrow', 'mspace', 'msqrt', 'mstyle',
      'msub', 'msubsup', 'msup', 'mtable', 'mtd', 'mtext', 'mtr', 'munder',
      'munderover', 'none', 'semantics']

    mathml_attributes = ['actiontype', 'align', 'columnalign', 'columnalign',
      'columnalign', 'close', 'columnlines', 'columnspacing', 'columnspan', 'depth',
      'display', 'displaystyle', 'encoding', 'equalcolumns', 'equalrows',
      'fence', 'fontstyle', 'fontweight', 'frame', 'height', 'linethickness',
      'lspace', 'mathbackground', 'mathcolor', 'mathvariant', 'mathvariant',
      'maxsize', 'minsize', 'open', 'other', 'rowalign', 'rowalign', 'rowalign',
      'rowlines', 'rowspacing', 'rowspan', 'rspace', 'scriptlevel', 'selection',
      'separator', 'separators', 'stretchy', 'width', 'width', 'xlink:href',
      'xlink:show', 'xlink:type', 'xmlns', 'xmlns:xlink']

    # svgtiny - foreignObject + linearGradient + radialGradient + stop
    svg_elements = ['a', 'animate', 'animateColor', 'animateMotion',
      'animateTransform', 'circle', 'defs', 'desc', 'ellipse', 'foreignObject',
      'font-face', 'font-face-name', 'font-face-src', 'g', 'glyph', 'hkern',
      'linearGradient', 'line', 'marker', 'metadata', 'missing-glyph', 'mpath',
      'path', 'polygon', 'polyline', 'radialGradient', 'rect', 'set', 'stop',
      'svg', 'switch', 'text', 'title', 'tspan', 'use']

    # svgtiny + class + opacity + offset + xmlns + xmlns:xlink
    svg_attributes = ['accent-height', 'accumulate', 'additive', 'alphabetic',
       'arabic-form', 'ascent', 'attributeName', 'attributeType',
       'baseProfile', 'bbox', 'begin', 'by', 'calcMode', 'cap-height',
       'class', 'color', 'color-rendering', 'content', 'cx', 'cy', 'd', 'dx',
       'dy', 'descent', 'display', 'dur', 'end', 'fill', 'fill-opacity',
       'fill-rule', 'font-family', 'font-size', 'font-stretch', 'font-style',
       'font-variant', 'font-weight', 'from', 'fx', 'fy', 'g1', 'g2',
       'glyph-name', 'gradientUnits', 'hanging', 'height', 'horiz-adv-x',
       'horiz-origin-x', 'id', 'ideographic', 'k', 'keyPoints', 'keySplines',
       'keyTimes', 'lang', 'mathematical', 'marker-end', 'marker-mid',
       'marker-start', 'markerHeight', 'markerUnits', 'markerWidth', 'max',
       'min', 'name', 'offset', 'opacity', 'orient', 'origin',
       'overline-position', 'overline-thickness', 'panose-1', 'path',
       'pathLength', 'points', 'preserveAspectRatio', 'r', 'refX', 'refY',
       'repeatCount', 'repeatDur', 'requiredExtensions', 'requiredFeatures',
       'restart', 'rotate', 'rx', 'ry', 'slope', 'stemh', 'stemv',
       'stop-color', 'stop-opacity', 'strikethrough-position',
       'strikethrough-thickness', 'stroke', 'stroke-dasharray',
       'stroke-dashoffset', 'stroke-linecap', 'stroke-linejoin',
       'stroke-miterlimit', 'stroke-opacity', 'stroke-width', 'systemLanguage',
       'target', 'text-anchor', 'to', 'transform', 'type', 'u1', 'u2',
       'underline-position', 'underline-thickness', 'unicode', 'unicode-range',
       'units-per-em', 'values', 'version', 'viewBox', 'visibility', 'width',
       'widths', 'x', 'x-height', 'x1', 'x2', 'xlink:actuate', 'xlink:arcrole',
       'xlink:href', 'xlink:role', 'xlink:show', 'xlink:title', 'xlink:type',
       'xml:base', 'xml:lang', 'xml:space', 'xmlns', 'xmlns:xlink', 'y', 'y1',
       'y2', 'zoomAndPan']

    svg_attr_map = None
    svg_elem_map = None

    acceptable_svg_properties = [ 'fill', 'fill-opacity', 'fill-rule',
      'stroke', 'stroke-width', 'stroke-linecap', 'stroke-linejoin',
      'stroke-opacity']

    def reset(self):
        _BaseHTMLProcessor.reset(self)
        self.unacceptablestack = 0
        self.mathmlOK = 0
        self.svgOK = 0

    def unknown_starttag(self, tag, attrs):
        acceptable_attributes = self.acceptable_attributes
        keymap = {}
        if not tag in self.acceptable_elements or self.svgOK:
            if tag in self.unacceptable_elements_with_end_tag:
                self.unacceptablestack += 1

            # add implicit namespaces to html5 inline svg/mathml
            if self.type.endswith('html'):
                if not dict(attrs).get('xmlns'):
                    if tag=='svg':
                        attrs.append( ('xmlns','http://www.w3.org/2000/svg') )
                    if tag=='math':
                        attrs.append( ('xmlns','http://www.w3.org/1998/Math/MathML') )

            # not otherwise acceptable, perhaps it is MathML or SVG?
            if tag=='math' and ('xmlns','http://www.w3.org/1998/Math/MathML') in attrs:
                self.mathmlOK += 1
            if tag=='svg' and ('xmlns','http://www.w3.org/2000/svg') in attrs:
                self.svgOK += 1

            # chose acceptable attributes based on tag class, else bail
            if  self.mathmlOK and tag in self.mathml_elements:
                acceptable_attributes = self.mathml_attributes
            elif self.svgOK and tag in self.svg_elements:
                # for most vocabularies, lowercasing is a good idea.  Many
                # svg elements, however, are camel case
                if not self.svg_attr_map:
                    lower=[attr.lower() for attr in self.svg_attributes]
                    mix=[a for a in self.svg_attributes if a not in lower]
                    self.svg_attributes = lower
                    self.svg_attr_map = dict([(a.lower(),a) for a in mix])

                    lower=[attr.lower() for attr in self.svg_elements]
                    mix=[a for a in self.svg_elements if a not in lower]
                    self.svg_elements = lower
                    self.svg_elem_map = dict([(a.lower(),a) for a in mix])
                acceptable_attributes = self.svg_attributes
                tag = self.svg_elem_map.get(tag,tag)
                keymap = self.svg_attr_map
            elif not tag in self.acceptable_elements:
                return

        # declare xlink namespace, if needed
        if self.mathmlOK or self.svgOK:
            if filter(lambda (n,v): n.startswith('xlink:'),attrs):
                if not ('xmlns:xlink','http://www.w3.org/1999/xlink') in attrs:
                    attrs.append(('xmlns:xlink','http://www.w3.org/1999/xlink'))

        clean_attrs = []
        for key, value in self.normalize_attrs(attrs):
            if key in acceptable_attributes:
                key=keymap.get(key,key)
                clean_attrs.append((key,value))
            elif key=='style':
                clean_value = self.sanitize_style(value)
                if clean_value: clean_attrs.append((key,clean_value))
        _BaseHTMLProcessor.unknown_starttag(self, tag, clean_attrs)

    def unknown_endtag(self, tag):
        if not tag in self.acceptable_elements:
            if tag in self.unacceptable_elements_with_end_tag:
                self.unacceptablestack -= 1
            if self.mathmlOK and tag in self.mathml_elements:
                if tag == 'math' and self.mathmlOK: self.mathmlOK -= 1
            elif self.svgOK and tag in self.svg_elements:
                tag = self.svg_elem_map.get(tag,tag)
                if tag == 'svg' and self.svgOK: self.svgOK -= 1
            else:
                return
        _BaseHTMLProcessor.unknown_endtag(self, tag)

    def handle_pi(self, text):
        pass

    def handle_decl(self, text):
        pass

    def handle_data(self, text):
        if not self.unacceptablestack:
            _BaseHTMLProcessor.handle_data(self, text)

    def sanitize_style(self, style):
        # disallow urls
        style=re.compile('url\s*\(\s*[^\s)]+?\s*\)\s*').sub(' ',style)

        # gauntlet
        if not re.match("""^([:,;#%.\sa-zA-Z0-9!]|\w-\w|'[\s\w]+'|"[\s\w]+"|\([\d,\s]+\))*$""", style): return ''
        # This replaced a regexp that used re.match and was prone to pathological back-tracking.
        if re.sub("\s*[-\w]+\s*:\s*[^:;]*;?", '', style).strip(): return ''

        clean = []
        for prop,value in re.findall("([-\w]+)\s*:\s*([^:;]*)",style):
          if not value: continue
          if prop.lower() in self.acceptable_css_properties:
              clean.append(prop + ': ' + value + ';')
          elif prop.split('-')[0].lower() in ['background','border','margin','padding']:
              for keyword in value.split():
                  if not keyword in self.acceptable_css_keywords and \
                      not self.valid_css_values.match(keyword):
                      break
              else:
                  clean.append(prop + ': ' + value + ';')
          elif self.svgOK and prop.lower() in self.acceptable_svg_properties:
              clean.append(prop + ': ' + value + ';')

        return ' '.join(clean)


def _sanitizeHTML(htmlSource, encoding, type):
    p = _HTMLSanitizer(encoding, type)
    p.feed(htmlSource)
    data = p.output()
    if TIDY_MARKUP:
        # loop through list of preferred Tidy interfaces looking for one that's installed,
        # then set up a common _tidy function to wrap the interface-specific API.
        _tidy = None
        for tidy_interface in PREFERRED_TIDY_INTERFACES:
            try:
                if tidy_interface == "uTidy":
                    from tidy import parseString as _utidy
                    def _tidy(data, **kwargs):
                        return str(_utidy(data, **kwargs))
                    break
                elif tidy_interface == "mxTidy":
                    from mx.Tidy import Tidy as _mxtidy
                    def _tidy(data, **kwargs):
                        nerrors, nwarnings, data, errordata = _mxtidy.tidy(data, **kwargs)
                        return data
                    break
            except:
                pass
        if _tidy:
            utf8 = type(data) == type(u'')
            if utf8:
                data = data.encode('utf-8')
            data = _tidy(data, output_xhtml=1, numeric_entities=1, wrap=0, char_encoding="utf8")
            if utf8:
                data = unicode(data, 'utf-8')
            if data.count('<body'):
                data = data.split('<body', 1)[1]
                if data.count('>'):
                    data = data.split('>', 1)[1]
            if data.count('</body'):
                data = data.split('</body', 1)[0]
    data = data.strip().replace('\r\n', '\n')
    return data

class _FeedURLHandler(urllib2.HTTPDigestAuthHandler, urllib2.HTTPRedirectHandler, urllib2.HTTPDefaultErrorHandler):
    def http_error_default(self, req, fp, code, msg, headers):
        if ((code / 100) == 3) and (code != 304):
            return self.http_error_302(req, fp, code, msg, headers)
        infourl = urllib.addinfourl(fp, headers, req.get_full_url())
        infourl.status = code
        return infourl

    def http_error_302(self, req, fp, code, msg, headers):
        if headers.dict.has_key('location'):
            infourl = urllib2.HTTPRedirectHandler.http_error_302(self, req, fp, code, msg, headers)
        else:
            infourl = urllib.addinfourl(fp, headers, req.get_full_url())
        if not hasattr(infourl, 'status'):
            infourl.status = code
        return infourl

    def http_error_301(self, req, fp, code, msg, headers):
        if headers.dict.has_key('location'):
            infourl = urllib2.HTTPRedirectHandler.http_error_301(self, req, fp, code, msg, headers)
        else:
            infourl = urllib.addinfourl(fp, headers, req.get_full_url())
        if not hasattr(infourl, 'status'):
            infourl.status = code
        return infourl

    http_error_300 = http_error_302
    http_error_303 = http_error_302
    http_error_307 = http_error_302

    def http_error_401(self, req, fp, code, msg, headers):
        # Check if
        # - server requires digest auth, AND
        # - we tried (unsuccessfully) with basic auth, AND
        # - we're using Python 2.3.3 or later (digest auth is irreparably broken in earlier versions)
        # If all conditions hold, parse authentication information
        # out of the Authorization header we sent the first time
        # (for the username and password) and the WWW-Authenticate
        # header the server sent back (for the realm) and retry
        # the request with the appropriate digest auth headers instead.
        # This evil genius hack has been brought to you by Aaron Swartz.
        host = urlparse.urlparse(req.get_full_url())[1]
        try:
            assert sys.version.split()[0] >= '2.3.3'
            assert base64 != None
            user, passw = base64.decodestring(req.headers['Authorization'].split(' ')[1]).split(':')
            realm = re.findall('realm="([^"]*)"', headers['WWW-Authenticate'])[0]
            self.add_password(realm, host, user, passw)
            retry = self.http_error_auth_reqed('www-authenticate', host, req, headers)
            self.reset_retry_count()
            return retry
        except:
            return self.http_error_default(req, fp, code, msg, headers)

def _open_resource(url_file_stream_or_string, etag, modified, agent, referrer, handlers, extra_headers):
    """URL, filename, or string --> stream

    This function lets you define parsers that take any input source
    (URL, pathname to local or network file, or actual data as a string)
    and deal with it in a uniform manner.  Returned object is guaranteed
    to have all the basic stdio read methods (read, readline, readlines).
    Just .close() the object when you're done with it.

    If the etag argument is supplied, it will be used as the value of an
    If-None-Match request header.

    If the modified argument is supplied, it can be a tuple of 9 integers
    (as returned by gmtime() in the standard Python time module) or a date
    string in any format supported by feedparser. Regardless, it MUST
    be in GMT (Greenwich Mean Time). It will be reformatted into an
    RFC 1123-compliant date and used as the value of an If-Modified-Since
    request header.

    If the agent argument is supplied, it will be used as the value of a
    User-Agent request header.

    If the referrer argument is supplied, it will be used as the value of a
    Referer[sic] request header.

    If handlers is supplied, it is a list of handlers used to build a
    urllib2 opener.

    if extra_headers is supplied it is a dictionary of HTTP request headers
    that will override the values generated by FeedParser.
    """

    if hasattr(url_file_stream_or_string, 'read'):
        return url_file_stream_or_string

    if url_file_stream_or_string == '-':
        return sys.stdin

    if urlparse.urlparse(url_file_stream_or_string)[0] in ('http', 'https', 'ftp'):
        if not agent:
            agent = USER_AGENT
        # test for inline user:password for basic auth
        auth = None
        if base64:
            urltype, rest = urllib.splittype(url_file_stream_or_string)
            realhost, rest = urllib.splithost(rest)
            if realhost:
                user_passwd, realhost = urllib.splituser(realhost)
                if user_passwd:
                    url_file_stream_or_string = '%s://%s%s' % (urltype, realhost, rest)
                    auth = base64.encodestring(user_passwd).strip()

        # iri support
        try:
            if isinstance(url_file_stream_or_string,unicode):
                url_file_stream_or_string = url_file_stream_or_string.encode('idna')
            else:
                url_file_stream_or_string = url_file_stream_or_string.decode('utf-8').encode('idna')
        except:
            pass

        # try to open with urllib2 (to use optional headers)
        request = _build_urllib2_request(url_file_stream_or_string, agent, etag, modified, referrer, auth, extra_headers)
        opener = apply(urllib2.build_opener, tuple([_FeedURLHandler()] + handlers))
        opener.addheaders = [] # RMK - must clear so we only send our custom User-Agent
        try:
            return opener.open(request)
        finally:
            opener.close() # JohnD

    # try to open with native open function (if url_file_stream_or_string is a filename)
    try:
        return open(url_file_stream_or_string)
    except:
        pass

    # treat url_file_stream_or_string as string
    return _StringIO(str(url_file_stream_or_string))

def _build_urllib2_request(url, agent, etag, modified, referrer, auth, extra_headers):
    request = urllib2.Request(url)
    request.add_header('User-Agent', agent)
    if etag:
        request.add_header('If-None-Match', etag)
    if type(modified) == type(''):
        modified = _parse_date(modified)
    if modified:
        # format into an RFC 1123-compliant timestamp. We can't use
        # time.strftime() since the %a and %b directives can be affected
        # by the current locale, but RFC 2616 states that dates must be
        # in English.
        short_weekdays = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        request.add_header('If-Modified-Since', '%s, %02d %s %04d %02d:%02d:%02d GMT' % (short_weekdays[modified[6]], modified[2], months[modified[1] - 1], modified[0], modified[3], modified[4], modified[5]))
    if referrer:
        request.add_header('Referer', referrer)
    if gzip and zlib:
        request.add_header('Accept-encoding', 'gzip, deflate')
    elif gzip:
        request.add_header('Accept-encoding', 'gzip')
    elif zlib:
        request.add_header('Accept-encoding', 'deflate')
    else:
        request.add_header('Accept-encoding', '')
    if auth:
        request.add_header('Authorization', 'Basic %s' % auth)
    if ACCEPT_HEADER:
        request.add_header('Accept', ACCEPT_HEADER)
    # use this for whatever -- cookies, special headers, etc
    # [('Cookie','Something'),('x-special-header','Another Value')]
    for header_name, header_value in extra_headers.items():
        request.add_header(header_name, header_value)
    request.add_header('A-IM', 'feed') # RFC 3229 support
    return request

_date_handlers = []
def registerDateHandler(func):
    '''Register a date handler function (takes string, returns 9-tuple date in GMT)'''
    _date_handlers.insert(0, func)

# ISO-8601 date parsing routines written by Fazal Majid.
# The ISO 8601 standard is very convoluted and irregular - a full ISO 8601
# parser is beyond the scope of feedparser and would be a worthwhile addition
# to the Python library.
# A single regular expression cannot parse ISO 8601 date formats into groups
# as the standard is highly irregular (for instance is 030104 2003-01-04 or
# 0301-04-01), so we use templates instead.
# Please note the order in templates is significant because we need a
# greedy match.
_iso8601_tmpl = ['YYYY-?MM-?DD', 'YYYY-0MM?-?DD', 'YYYY-MM', 'YYYY-?OOO',
                'YY-?MM-?DD', 'YY-?OOO', 'YYYY',
                '-YY-?MM', '-OOO', '-YY',
                '--MM-?DD', '--MM',
                '---DD',
                'CC', '']
_iso8601_re = [
    tmpl.replace(
    'YYYY', r'(?P<year>\d{4})').replace(
    'YY', r'(?P<year>\d\d)').replace(
    'MM', r'(?P<month>[01]\d)').replace(
    'DD', r'(?P<day>[0123]\d)').replace(
    'OOO', r'(?P<ordinal>[0123]\d\d)').replace(
    'CC', r'(?P<century>\d\d$)')
    + r'(T?(?P<hour>\d{2}):(?P<minute>\d{2})'
    + r'(:(?P<second>\d{2}))?'
    + r'(\.(?P<fracsecond>\d+))?'
    + r'(?P<tz>[+-](?P<tzhour>\d{2})(:(?P<tzmin>\d{2}))?|Z)?)?'
    for tmpl in _iso8601_tmpl]
del tmpl
_iso8601_matches = [re.compile(regex).match for regex in _iso8601_re]
del regex
def _parse_date_iso8601(dateString):
    '''Parse a variety of ISO-8601-compatible formats like 20040105'''
    m = None
    for _iso8601_match in _iso8601_matches:
        m = _iso8601_match(dateString)
        if m: break
    if not m: return
    if m.span() == (0, 0): return
    params = m.groupdict()
    ordinal = params.get('ordinal', 0)
    if ordinal:
        ordinal = int(ordinal)
    else:
        ordinal = 0
    year = params.get('year', '--')
    if not year or year == '--':
        year = time.gmtime()[0]
    elif len(year) == 2:
        # ISO 8601 assumes current century, i.e. 93 -> 2093, NOT 1993
        year = 100 * int(time.gmtime()[0] / 100) + int(year)
    else:
        year = int(year)
    month = params.get('month', '-')
    if not month or month == '-':
        # ordinals are NOT normalized by mktime, we simulate them
        # by setting month=1, day=ordinal
        if ordinal:
            month = 1
        else:
            month = time.gmtime()[1]
    month = int(month)
    day = params.get('day', 0)
    if not day:
        # see above
        if ordinal:
            day = ordinal
        elif params.get('century', 0) or \
                 params.get('year', 0) or params.get('month', 0):
            day = 1
        else:
            day = time.gmtime()[2]
    else:
        day = int(day)
    # special case of the century - is the first year of the 21st century
    # 2000 or 2001 ? The debate goes on...
    if 'century' in params.keys():
        year = (int(params['century']) - 1) * 100 + 1
    # in ISO 8601 most fields are optional
    for field in ['hour', 'minute', 'second', 'tzhour', 'tzmin']:
        if not params.get(field, None):
            params[field] = 0
    hour = int(params.get('hour', 0))
    minute = int(params.get('minute', 0))
    second = int(float(params.get('second', 0)))
    # weekday is normalized by mktime(), we can ignore it
    weekday = 0
    daylight_savings_flag = -1
    tm = [year, month, day, hour, minute, second, weekday,
          ordinal, daylight_savings_flag]
    # ISO 8601 time zone adjustments
    tz = params.get('tz')
    if tz and tz != 'Z':
        if tz[0] == '-':
            tm[3] += int(params.get('tzhour', 0))
            tm[4] += int(params.get('tzmin', 0))
        elif tz[0] == '+':
            tm[3] -= int(params.get('tzhour', 0))
            tm[4] -= int(params.get('tzmin', 0))
        else:
            return None
    # Python's time.mktime() is a wrapper around the ANSI C mktime(3c)
    # which is guaranteed to normalize d/m/y/h/m/s.
    # Many implementations have bugs, but we'll pretend they don't.
    return time.localtime(time.mktime(tm))
registerDateHandler(_parse_date_iso8601)

# 8-bit date handling routines written by ytrewq1.
_korean_year  = u'\ub144' # b3e2 in euc-kr
_korean_month = u'\uc6d4' # bff9 in euc-kr
_korean_day   = u'\uc77c' # c0cf in euc-kr
_korean_am    = u'\uc624\uc804' # bfc0 c0fc in euc-kr
_korean_pm    = u'\uc624\ud6c4' # bfc0 c8c4 in euc-kr

_korean_onblog_date_re = \
    re.compile('(\d{4})%s\s+(\d{2})%s\s+(\d{2})%s\s+(\d{2}):(\d{2}):(\d{2})' % \
               (_korean_year, _korean_month, _korean_day))
_korean_nate_date_re = \
    re.compile(u'(\d{4})-(\d{2})-(\d{2})\s+(%s|%s)\s+(\d{,2}):(\d{,2}):(\d{,2})' % \
               (_korean_am, _korean_pm))
def _parse_date_onblog(dateString):
    '''Parse a string according to the OnBlog 8-bit date format'''
    m = _korean_onblog_date_re.match(dateString)
    if not m: return
    w3dtfdate = '%(year)s-%(month)s-%(day)sT%(hour)s:%(minute)s:%(second)s%(zonediff)s' % \
                {'year': m.group(1), 'month': m.group(2), 'day': m.group(3),\
                 'hour': m.group(4), 'minute': m.group(5), 'second': m.group(6),\
                 'zonediff': '+09:00'}
    if _debug: sys.stderr.write('OnBlog date parsed as: %s\n' % w3dtfdate)
    return _parse_date_w3dtf(w3dtfdate)
registerDateHandler(_parse_date_onblog)

def _parse_date_nate(dateString):
    '''Parse a string according to the Nate 8-bit date format'''
    m = _korean_nate_date_re.match(dateString)
    if not m: return
    hour = int(m.group(5))
    ampm = m.group(4)
    if (ampm == _korean_pm):
        hour += 12
    hour = str(hour)
    if len(hour) == 1:
        hour = '0' + hour
    w3dtfdate = '%(year)s-%(month)s-%(day)sT%(hour)s:%(minute)s:%(second)s%(zonediff)s' % \
                {'year': m.group(1), 'month': m.group(2), 'day': m.group(3),\
                 'hour': hour, 'minute': m.group(6), 'second': m.group(7),\
                 'zonediff': '+09:00'}
    if _debug: sys.stderr.write('Nate date parsed as: %s\n' % w3dtfdate)
    return _parse_date_w3dtf(w3dtfdate)
registerDateHandler(_parse_date_nate)

_mssql_date_re = \
    re.compile('(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})(\.\d+)?')
def _parse_date_mssql(dateString):
    '''Parse a string according to the MS SQL date format'''
    m = _mssql_date_re.match(dateString)
    if not m: return
    w3dtfdate = '%(year)s-%(month)s-%(day)sT%(hour)s:%(minute)s:%(second)s%(zonediff)s' % \
                {'year': m.group(1), 'month': m.group(2), 'day': m.group(3),\
                 'hour': m.group(4), 'minute': m.group(5), 'second': m.group(6),\
                 'zonediff': '+09:00'}
    if _debug: sys.stderr.write('MS SQL date parsed as: %s\n' % w3dtfdate)
    return _parse_date_w3dtf(w3dtfdate)
registerDateHandler(_parse_date_mssql)

# Unicode strings for Greek date strings
_greek_months = \
  { \
   u'\u0399\u03b1\u03bd': u'Jan',       # c9e1ed in iso-8859-7
   u'\u03a6\u03b5\u03b2': u'Feb',       # d6e5e2 in iso-8859-7
   u'\u039c\u03ac\u03ce': u'Mar',       # ccdcfe in iso-8859-7
   u'\u039c\u03b1\u03ce': u'Mar',       # cce1fe in iso-8859-7
   u'\u0391\u03c0\u03c1': u'Apr',       # c1f0f1 in iso-8859-7
   u'\u039c\u03ac\u03b9': u'May',       # ccdce9 in iso-8859-7
   u'\u039c\u03b1\u03ca': u'May',       # cce1fa in iso-8859-7
   u'\u039c\u03b1\u03b9': u'May',       # cce1e9 in iso-8859-7
   u'\u0399\u03bf\u03cd\u03bd': u'Jun', # c9effded in iso-8859-7
   u'\u0399\u03bf\u03bd': u'Jun',       # c9efed in iso-8859-7
   u'\u0399\u03bf\u03cd\u03bb': u'Jul', # c9effdeb in iso-8859-7
   u'\u0399\u03bf\u03bb': u'Jul',       # c9f9eb in iso-8859-7
   u'\u0391\u03cd\u03b3': u'Aug',       # c1fde3 in iso-8859-7
   u'\u0391\u03c5\u03b3': u'Aug',       # c1f5e3 in iso-8859-7
   u'\u03a3\u03b5\u03c0': u'Sep',       # d3e5f0 in iso-8859-7
   u'\u039f\u03ba\u03c4': u'Oct',       # cfeaf4 in iso-8859-7
   u'\u039d\u03bf\u03ad': u'Nov',       # cdefdd in iso-8859-7
   u'\u039d\u03bf\u03b5': u'Nov',       # cdefe5 in iso-8859-7
   u'\u0394\u03b5\u03ba': u'Dec',       # c4e5ea in iso-8859-7
  }

_greek_wdays = \
  { \
   u'\u039a\u03c5\u03c1': u'Sun', # caf5f1 in iso-8859-7
   u'\u0394\u03b5\u03c5': u'Mon', # c4e5f5 in iso-8859-7
   u'\u03a4\u03c1\u03b9': u'Tue', # d4f1e9 in iso-8859-7
   u'\u03a4\u03b5\u03c4': u'Wed', # d4e5f4 in iso-8859-7
   u'\u03a0\u03b5\u03bc': u'Thu', # d0e5ec in iso-8859-7
   u'\u03a0\u03b1\u03c1': u'Fri', # d0e1f1 in iso-8859-7
   u'\u03a3\u03b1\u03b2': u'Sat', # d3e1e2 in iso-8859-7
  }

_greek_date_format_re = \
    re.compile(u'([^,]+),\s+(\d{2})\s+([^\s]+)\s+(\d{4})\s+(\d{2}):(\d{2}):(\d{2})\s+([^\s]+)')

def _parse_date_greek(dateString):
    '''Parse a string according to a Greek 8-bit date format.'''
    m = _greek_date_format_re.match(dateString)
    if not m: return
    try:
        wday = _greek_wdays[m.group(1)]
        month = _greek_months[m.group(3)]
    except:
        return
    rfc822date = '%(wday)s, %(day)s %(month)s %(year)s %(hour)s:%(minute)s:%(second)s %(zonediff)s' % \
                 {'wday': wday, 'day': m.group(2), 'month': month, 'year': m.group(4),\
                  'hour': m.group(5), 'minute': m.group(6), 'second': m.group(7),\
                  'zonediff': m.group(8)}
    if _debug: sys.stderr.write('Greek date parsed as: %s\n' % rfc822date)
    return _parse_date_rfc822(rfc822date)
registerDateHandler(_parse_date_greek)

# Unicode strings for Hungarian date strings
_hungarian_months = \
  { \
    u'janu\u00e1r':   u'01',  # e1 in iso-8859-2
    u'febru\u00e1ri': u'02',  # e1 in iso-8859-2
    u'm\u00e1rcius':  u'03',  # e1 in iso-8859-2
    u'\u00e1prilis':  u'04',  # e1 in iso-8859-2
    u'm\u00e1ujus':   u'05',  # e1 in iso-8859-2
    u'j\u00fanius':   u'06',  # fa in iso-8859-2
    u'j\u00falius':   u'07',  # fa in iso-8859-2
    u'augusztus':     u'08',
    u'szeptember':    u'09',
    u'okt\u00f3ber':  u'10',  # f3 in iso-8859-2
    u'november':      u'11',
    u'december':      u'12',
  }

_hungarian_date_format_re = \
  re.compile(u'(\d{4})-([^-]+)-(\d{,2})T(\d{,2}):(\d{2})((\+|-)(\d{,2}:\d{2}))')

def _parse_date_hungarian(dateString):
    '''Parse a string according to a Hungarian 8-bit date format.'''
    m = _hungarian_date_format_re.match(dateString)
    if not m: return
    try:
        month = _hungarian_months[m.group(2)]
        day = m.group(3)
        if len(day) == 1:
            day = '0' + day
        hour = m.group(4)
        if len(hour) == 1:
            hour = '0' + hour
    except:
        return
    w3dtfdate = '%(year)s-%(month)s-%(day)sT%(hour)s:%(minute)s%(zonediff)s' % \
                {'year': m.group(1), 'month': month, 'day': day,\
                 'hour': hour, 'minute': m.group(5),\
                 'zonediff': m.group(6)}
    if _debug: sys.stderr.write('Hungarian date parsed as: %s\n' % w3dtfdate)
    return _parse_date_w3dtf(w3dtfdate)
registerDateHandler(_parse_date_hungarian)

# W3DTF-style date parsing adapted from PyXML xml.utils.iso8601, written by
# Drake and licensed under the Python license.  Removed all range checking
# for month, day, hour, minute, and second, since mktime will normalize
# these later
def _parse_date_w3dtf(dateString):
    def __extract_date(m):
        year = int(m.group('year'))
        if year < 100:
            year = 100 * int(time.gmtime()[0] / 100) + int(year)
        if year < 1000:
            return 0, 0, 0
        julian = m.group('julian')
        if julian:
            julian = int(julian)
            month = julian / 30 + 1
            day = julian % 30 + 1
            jday = None
            while jday != julian:
                t = time.mktime((year, month, day, 0, 0, 0, 0, 0, 0))
                jday = time.gmtime(t)[-2]
                diff = abs(jday - julian)
                if jday > julian:
                    if diff < day:
                        day = day - diff
                    else:
                        month = month - 1
                        day = 31
                elif jday < julian:
                    if day + diff < 28:
                       day = day + diff
                    else:
                        month = month + 1
            return year, month, day
        month = m.group('month')
        day = 1
        if month is None:
            month = 1
        else:
            month = int(month)
            day = m.group('day')
            if day:
                day = int(day)
            else:
                day = 1
        return year, month, day

    def __extract_time(m):
        if not m:
            return 0, 0, 0
        hours = m.group('hours')
        if not hours:
            return 0, 0, 0
        hours = int(hours)
        minutes = int(m.group('minutes'))
        seconds = m.group('seconds')
        if seconds:
            seconds = int(seconds)
        else:
            seconds = 0
        return hours, minutes, seconds

    def __extract_tzd(m):
        '''Return the Time Zone Designator as an offset in seconds from UTC.'''
        if not m:
            return 0
        tzd = m.group('tzd')
        if not tzd:
            return 0
        if tzd == 'Z':
            return 0
        hours = int(m.group('tzdhours'))
        minutes = m.group('tzdminutes')
        if minutes:
            minutes = int(minutes)
        else:
            minutes = 0
        offset = (hours*60 + minutes) * 60
        if tzd[0] == '+':
            return -offset
        return offset

    __date_re = ('(?P<year>\d\d\d\d)'
                 '(?:(?P<dsep>-|)'
                 '(?:(?P<julian>\d\d\d)'
                 '|(?P<month>\d\d)(?:(?P=dsep)(?P<day>\d\d))?))?')
    __tzd_re = '(?P<tzd>[-+](?P<tzdhours>\d\d)(?::?(?P<tzdminutes>\d\d))|Z)'
    __tzd_rx = re.compile(__tzd_re)
    __time_re = ('(?P<hours>\d\d)(?P<tsep>:|)(?P<minutes>\d\d)'
                 '(?:(?P=tsep)(?P<seconds>\d\d(?:[.,]\d+)?))?'
                 + __tzd_re)
    __datetime_re = '%s(?:T%s)?' % (__date_re, __time_re)
    __datetime_rx = re.compile(__datetime_re)
    m = __datetime_rx.match(dateString)
    if (m is None) or (m.group() != dateString): return
    gmt = __extract_date(m) + __extract_time(m) + (0, 0, 0)
    if gmt[0] == 0: return
    return time.gmtime(time.mktime(gmt) + __extract_tzd(m) - time.timezone)
registerDateHandler(_parse_date_w3dtf)

def _parse_date_rfc822(dateString):
    '''Parse an RFC822, RFC1123, RFC2822, or asctime-style date'''
    data = dateString.split()
    if data[0][-1] in (',', '.') or data[0].lower() in rfc822._daynames:
        del data[0]
    if len(data) == 4:
        s = data[3]
        i = s.find('+')
        if i > 0:
            data[3:] = [s[:i], s[i+1:]]
        else:
            data.append('')
        dateString = " ".join(data)
    if len(data) < 5:
        dateString += ' 00:00:00 GMT'
    tm = rfc822.parsedate_tz(dateString)
    if tm:
        return time.gmtime(rfc822.mktime_tz(tm))
# rfc822.py defines several time zones, but we define some extra ones.
# 'ET' is equivalent to 'EST', etc.
_additional_timezones = {'AT': -400, 'ET': -500, 'CT': -600, 'MT': -700, 'PT': -800}
rfc822._timezones.update(_additional_timezones)
registerDateHandler(_parse_date_rfc822)

def _parse_date_perforce(aDateString):
	"""parse a date in yyyy/mm/dd hh:mm:ss TTT format"""
	# Fri, 2006/09/15 08:19:53 EDT
	_my_date_pattern = re.compile( \
		r'(\w{,3}), (\d{,4})/(\d{,2})/(\d{2}) (\d{,2}):(\d{2}):(\d{2}) (\w{,3})')

	dow, year, month, day, hour, minute, second, tz = \
		_my_date_pattern.search(aDateString).groups()
	months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
	dateString = "%s, %s %s %s %s:%s:%s %s" % (dow, day, months[int(month) - 1], year, hour, minute, second, tz)
	tm = rfc822.parsedate_tz(dateString)
	if tm:
		return time.gmtime(rfc822.mktime_tz(tm))
registerDateHandler(_parse_date_perforce)

def _parse_date(dateString):
    '''Parses a variety of date formats into a 9-tuple in GMT'''
    for handler in _date_handlers:
        try:
            date9tuple = handler(dateString)
            if not date9tuple: continue
            if len(date9tuple) != 9:
                if _debug: sys.stderr.write('date handler function must return 9-tuple\n')
                raise ValueError
            map(int, date9tuple)
            return date9tuple
        except Exception, e:
            if _debug: sys.stderr.write('%s raised %s\n' % (handler.__name__, repr(e)))
            pass
    return None

def _getCharacterEncoding(http_headers, xml_data):
    '''Get the character encoding of the XML document

    http_headers is a dictionary
    xml_data is a raw string (not Unicode)

    This is so much trickier than it sounds, it's not even funny.
    According to RFC 3023 ('XML Media Types'), if the HTTP Content-Type
    is application/xml, application/*+xml,
    application/xml-external-parsed-entity, or application/xml-dtd,
    the encoding given in the charset parameter of the HTTP Content-Type
    takes precedence over the encoding given in the XML prefix within the
    document, and defaults to 'utf-8' if neither are specified.  But, if
    the HTTP Content-Type is text/xml, text/*+xml, or
    text/xml-external-parsed-entity, the encoding given in the XML prefix
    within the document is ALWAYS IGNORED and only the encoding given in
    the charset parameter of the HTTP Content-Type header should be
    respected, and it defaults to 'us-ascii' if not specified.

    Furthermore, discussion on the atom-syntax mailing list with the
    author of RFC 3023 leads me to the conclusion that any document
    served with a Content-Type of text/* and no charset parameter
    must be treated as us-ascii.  (We now do this.)  And also that it
    must always be flagged as non-well-formed.  (We now do this too.)

    If Content-Type is unspecified (input was local file or non-HTTP source)
    or unrecognized (server just got it totally wrong), then go by the
    encoding given in the XML prefix of the document and default to
    'iso-8859-1' as per the HTTP specification (RFC 2616).

    Then, assuming we didn't find a character encoding in the HTTP headers
    (and the HTTP Content-type allowed us to look in the body), we need
    to sniff the first few bytes of the XML data and try to determine
    whether the encoding is ASCII-compatible.  Section F of the XML
    specification shows the way here:
    http://www.w3.org/TR/REC-xml/#sec-guessing-no-ext-info

    If the sniffed encoding is not ASCII-compatible, we need to make it
    ASCII compatible so that we can sniff further into the XML declaration
    to find the encoding attribute, which will tell us the true encoding.

    Of course, none of this guarantees that we will be able to parse the
    feed in the declared character encoding (assuming it was declared
    correctly, which many are not).  CJKCodecs and iconv_codec help a lot;
    you should definitely install them if you can.
    http://cjkpython.i18n.org/
    '''

    def _parseHTTPContentType(content_type):
        '''takes HTTP Content-Type header and returns (content type, charset)

        If no charset is specified, returns (content type, '')
        If no content type is specified, returns ('', '')
        Both return parameters are guaranteed to be lowercase strings
        '''
        content_type = content_type or ''
        content_type, params = cgi.parse_header(content_type)
        return content_type, params.get('charset', '').replace("'", '')

    sniffed_xml_encoding = ''
    xml_encoding = ''
    true_encoding = ''
    http_content_type, http_encoding = _parseHTTPContentType(http_headers.get('content-type'))
    # Must sniff for non-ASCII-compatible character encodings before
    # searching for XML declaration.  This heuristic is defined in
    # section F of the XML specification:
    # http://www.w3.org/TR/REC-xml/#sec-guessing-no-ext-info
    try:
        if xml_data[:4] == '\x4c\x6f\xa7\x94':
            # EBCDIC
            xml_data = _ebcdic_to_ascii(xml_data)
        elif xml_data[:4] == '\x00\x3c\x00\x3f':
            # UTF-16BE
            sniffed_xml_encoding = 'utf-16be'
            xml_data = unicode(xml_data, 'utf-16be').encode('utf-8')
        elif (len(xml_data) >= 4) and (xml_data[:2] == '\xfe\xff') and (xml_data[2:4] != '\x00\x00'):
            # UTF-16BE with BOM
            sniffed_xml_encoding = 'utf-16be'
            xml_data = unicode(xml_data[2:], 'utf-16be').encode('utf-8')
        elif xml_data[:4] == '\x3c\x00\x3f\x00':
            # UTF-16LE
            sniffed_xml_encoding = 'utf-16le'
            xml_data = unicode(xml_data, 'utf-16le').encode('utf-8')
        elif (len(xml_data) >= 4) and (xml_data[:2] == '\xff\xfe') and (xml_data[2:4] != '\x00\x00'):
            # UTF-16LE with BOM
            sniffed_xml_encoding = 'utf-16le'
            xml_data = unicode(xml_data[2:], 'utf-16le').encode('utf-8')
        elif xml_data[:4] == '\x00\x00\x00\x3c':
            # UTF-32BE
            sniffed_xml_encoding = 'utf-32be'
            xml_data = unicode(xml_data, 'utf-32be').encode('utf-8')
        elif xml_data[:4] == '\x3c\x00\x00\x00':
            # UTF-32LE
            sniffed_xml_encoding = 'utf-32le'
            xml_data = unicode(xml_data, 'utf-32le').encode('utf-8')
        elif xml_data[:4] == '\x00\x00\xfe\xff':
            # UTF-32BE with BOM
            sniffed_xml_encoding = 'utf-32be'
            xml_data = unicode(xml_data[4:], 'utf-32be').encode('utf-8')
        elif xml_data[:4] == '\xff\xfe\x00\x00':
            # UTF-32LE with BOM
            sniffed_xml_encoding = 'utf-32le'
            xml_data = unicode(xml_data[4:], 'utf-32le').encode('utf-8')
        elif xml_data[:3] == '\xef\xbb\xbf':
            # UTF-8 with BOM
            sniffed_xml_encoding = 'utf-8'
            xml_data = unicode(xml_data[3:], 'utf-8').encode('utf-8')
        else:
            # ASCII-compatible
            pass
        xml_encoding_match = re.compile('^<\?.*encoding=[\'"](.*?)[\'"].*\?>').match(xml_data)
    except:
        xml_encoding_match = None
    if xml_encoding_match:
        xml_encoding = xml_encoding_match.groups()[0].lower()
        if sniffed_xml_encoding and (xml_encoding in ('iso-10646-ucs-2', 'ucs-2', 'csunicode', 'iso-10646-ucs-4', 'ucs-4', 'csucs4', 'utf-16', 'utf-32', 'utf_16', 'utf_32', 'utf16', 'u16')):
            xml_encoding = sniffed_xml_encoding
    acceptable_content_type = 0
    application_content_types = ('application/xml', 'application/xml-dtd', 'application/xml-external-parsed-entity')
    text_content_types = ('text/xml', 'text/xml-external-parsed-entity')
    if (http_content_type in application_content_types) or \
       (http_content_type.startswith('application/') and http_content_type.endswith('+xml')):
        acceptable_content_type = 1
        true_encoding = http_encoding or xml_encoding or 'utf-8'
    elif (http_content_type in text_content_types) or \
         (http_content_type.startswith('text/')) and http_content_type.endswith('+xml'):
        acceptable_content_type = 1
        true_encoding = http_encoding or 'us-ascii'
    elif http_content_type.startswith('text/'):
        true_encoding = http_encoding or 'us-ascii'
    elif http_headers and (not http_headers.has_key('content-type')):
        true_encoding = xml_encoding or 'iso-8859-1'
    else:
        true_encoding = xml_encoding or 'utf-8'
    # some feeds claim to be gb2312 but are actually gb18030.
    # apparently MSIE and Firefox both do the following switch:
    if true_encoding.lower() == 'gb2312':
        true_encoding = 'gb18030'
    return true_encoding, http_encoding, xml_encoding, sniffed_xml_encoding, acceptable_content_type

def _toUTF8(data, encoding):
    '''Changes an XML data stream on the fly to specify a new encoding

    data is a raw sequence of bytes (not Unicode) that is presumed to be in %encoding already
    encoding is a string recognized by encodings.aliases
    '''
    if _debug: sys.stderr.write('entering _toUTF8, trying encoding %s\n' % encoding)
    # strip Byte Order Mark (if present)
    if (len(data) >= 4) and (data[:2] == '\xfe\xff') and (data[2:4] != '\x00\x00'):
        if _debug:
            sys.stderr.write('stripping BOM\n')
            if encoding != 'utf-16be':
                sys.stderr.write('trying utf-16be instead\n')
        encoding = 'utf-16be'
        data = data[2:]
    elif (len(data) >= 4) and (data[:2] == '\xff\xfe') and (data[2:4] != '\x00\x00'):
        if _debug:
            sys.stderr.write('stripping BOM\n')
            if encoding != 'utf-16le':
                sys.stderr.write('trying utf-16le instead\n')
        encoding = 'utf-16le'
        data = data[2:]
    elif data[:3] == '\xef\xbb\xbf':
        if _debug:
            sys.stderr.write('stripping BOM\n')
            if encoding != 'utf-8':
                sys.stderr.write('trying utf-8 instead\n')
        encoding = 'utf-8'
        data = data[3:]
    elif data[:4] == '\x00\x00\xfe\xff':
        if _debug:
            sys.stderr.write('stripping BOM\n')
            if encoding != 'utf-32be':
                sys.stderr.write('trying utf-32be instead\n')
        encoding = 'utf-32be'
        data = data[4:]
    elif data[:4] == '\xff\xfe\x00\x00':
        if _debug:
            sys.stderr.write('stripping BOM\n')
            if encoding != 'utf-32le':
                sys.stderr.write('trying utf-32le instead\n')
        encoding = 'utf-32le'
        data = data[4:]
    newdata = unicode(data, encoding)
    if _debug: sys.stderr.write('successfully converted %s data to unicode\n' % encoding)
    declmatch = re.compile('^<\?xml[^>]*?>')
    newdecl = '''<?xml version='1.0' encoding='utf-8'?>'''
    if declmatch.search(newdata):
        newdata = declmatch.sub(newdecl, newdata)
    else:
        newdata = newdecl + u'\n' + newdata
    return newdata.encode('utf-8')

def _stripDoctype(data):
    '''Strips DOCTYPE from XML document, returns (rss_version, stripped_data)

    rss_version may be 'rss091n' or None
    stripped_data is the same XML document, minus the DOCTYPE
    '''
    start = re.search('<\w',data)
    start = start and start.start() or -1
    head,data = data[:start+1], data[start+1:]

    entity_pattern = re.compile(r'^\s*<!ENTITY([^>]*?)>', re.MULTILINE)
    entity_results=entity_pattern.findall(head)
    head = entity_pattern.sub('', head)
    doctype_pattern = re.compile(r'^\s*<!DOCTYPE([^>]*?)>', re.MULTILINE)
    doctype_results = doctype_pattern.findall(head)
    doctype = doctype_results and doctype_results[0] or ''
    if doctype.lower().count('netscape'):
        version = 'rss091n'
    else:
        version = None

    # only allow in 'safe' inline entity definitions
    replacement=''
    if len(doctype_results)==1 and entity_results:
       safe_pattern=re.compile('\s+(\w+)\s+"(&#\w+;|[^&"]*)"')
       safe_entities=filter(lambda e: safe_pattern.match(e),entity_results)
       if safe_entities:
           replacement='<!DOCTYPE feed [\n  <!ENTITY %s>\n]>' % '>\n  <!ENTITY '.join(safe_entities)
    data = doctype_pattern.sub(replacement, head) + data

    return version, data, dict(replacement and safe_pattern.findall(replacement))

def parse(url_file_stream_or_string, etag=None, modified=None, agent=None, referrer=None, handlers=[], extra_headers={}):
    '''Parse a feed from a URL, file, stream, or string.

    extra_headers, if given, is a dict from http header name to value to add
    to the request; this overrides internally generated values.
    '''
    result = FeedParserDict()
    result['feed'] = FeedParserDict()
    result['entries'] = []
    if _XML_AVAILABLE:
        result['bozo'] = 0
    if type(handlers) == types.InstanceType:
        handlers = [handlers]
    try:
        f = _open_resource(url_file_stream_or_string, etag, modified, agent, referrer, handlers, extra_headers)
        data = f.read()
    except Exception, e:
        result['bozo'] = 1
        result['bozo_exception'] = e
        data = None
        f = None

    # if feed is gzip-compressed, decompress it
    if f and data and hasattr(f, 'headers'):
        if gzip and f.headers.get('content-encoding', '') == 'gzip':
            try:
                data = gzip.GzipFile(fileobj=_StringIO(data)).read()
            except Exception, e:
                # Some feeds claim to be gzipped but they're not, so
                # we get garbage.  Ideally, we should re-request the
                # feed without the 'Accept-encoding: gzip' header,
                # but we don't.
                result['bozo'] = 1
                result['bozo_exception'] = e
                data = ''
        elif zlib and f.headers.get('content-encoding', '') == 'deflate':
            try:
                data = zlib.decompress(data, -zlib.MAX_WBITS)
            except Exception, e:
                result['bozo'] = 1
                result['bozo_exception'] = e
                data = ''

    # save HTTP headers
    if hasattr(f, 'info'):
        info = f.info()
        etag = info.getheader('ETag')
        if etag:
            result['etag'] = etag
        last_modified = info.getheader('Last-Modified')
        if last_modified:
            result['modified'] = _parse_date(last_modified)
    if hasattr(f, 'url'):
        result['href'] = f.url
        result['status'] = 200
    if hasattr(f, 'status'):
        result['status'] = f.status
    if hasattr(f, 'headers'):
        result['headers'] = f.headers.dict
    if hasattr(f, 'close'):
        f.close()

    # there are four encodings to keep track of:
    # - http_encoding is the encoding declared in the Content-Type HTTP header
    # - xml_encoding is the encoding declared in the <?xml declaration
    # - sniffed_encoding is the encoding sniffed from the first 4 bytes of the XML data
    # - result['encoding'] is the actual encoding, as per RFC 3023 and a variety of other conflicting specifications
    http_headers = result.get('headers', {})
    result['encoding'], http_encoding, xml_encoding, sniffed_xml_encoding, acceptable_content_type = \
        _getCharacterEncoding(http_headers, data)
    if http_headers and (not acceptable_content_type):
        if http_headers.has_key('content-type'):
            bozo_message = '%s is not an XML media type' % http_headers['content-type']
        else:
            bozo_message = 'no Content-type specified'
        result['bozo'] = 1
        result['bozo_exception'] = NonXMLContentType(bozo_message)

    if data is not None:
        result['version'], data, entities = _stripDoctype(data)

    baseuri = http_headers.get('content-location', result.get('href'))
    baselang = http_headers.get('content-language', None)

    # if server sent 304, we're done
    if result.get('status', 0) == 304:
        result['version'] = ''
        result['debug_message'] = 'The feed has not changed since you last checked, ' + \
            'so the server sent no data.  This is a feature, not a bug!'
        return result

    # if there was a problem downloading, we're done
    if data is None:
        return result

    # determine character encoding
    use_strict_parser = 0
    known_encoding = 0
    tried_encodings = []
    # try: HTTP encoding, declared XML encoding, encoding sniffed from BOM
    for proposed_encoding in (result['encoding'], xml_encoding, sniffed_xml_encoding):
        if not proposed_encoding: continue
        if proposed_encoding in tried_encodings: continue
        tried_encodings.append(proposed_encoding)
        try:
            data = _toUTF8(data, proposed_encoding)
            known_encoding = use_strict_parser = 1
            break
        except:
            pass
    # if no luck and we have auto-detection library, try that
    if (not known_encoding) and chardet:
        try:
            proposed_encoding = chardet.detect(data)['encoding']
            if proposed_encoding and (proposed_encoding not in tried_encodings):
                tried_encodings.append(proposed_encoding)
                data = _toUTF8(data, proposed_encoding)
                known_encoding = use_strict_parser = 1
        except:
            pass
    # if still no luck and we haven't tried utf-8 yet, try that
    if (not known_encoding) and ('utf-8' not in tried_encodings):
        try:
            proposed_encoding = 'utf-8'
            tried_encodings.append(proposed_encoding)
            data = _toUTF8(data, proposed_encoding)
            known_encoding = use_strict_parser = 1
        except:
            pass
    # if still no luck and we haven't tried windows-1252 yet, try that
    if (not known_encoding) and ('windows-1252' not in tried_encodings):
        try:
            proposed_encoding = 'windows-1252'
            tried_encodings.append(proposed_encoding)
            data = _toUTF8(data, proposed_encoding)
            known_encoding = use_strict_parser = 1
        except:
            pass
    # if still no luck and we haven't tried iso-8859-2 yet, try that.
    if (not known_encoding) and ('iso-8859-2' not in tried_encodings):
        try:
            proposed_encoding = 'iso-8859-2'
            tried_encodings.append(proposed_encoding)
            data = _toUTF8(data, proposed_encoding)
            known_encoding = use_strict_parser = 1
        except:
            pass
    # if still no luck, give up
    if not known_encoding:
        result['bozo'] = 1
        result['bozo_exception'] = CharacterEncodingUnknown( \
            'document encoding unknown, I tried ' + \
            '%s, %s, utf-8, windows-1252, and iso-8859-2 but nothing worked' % \
            (result['encoding'], xml_encoding))
        result['encoding'] = ''
    elif proposed_encoding != result['encoding']:
        result['bozo'] = 1
        result['bozo_exception'] = CharacterEncodingOverride( \
            'documented declared as %s, but parsed as %s' % \
            (result['encoding'], proposed_encoding))
        result['encoding'] = proposed_encoding

    if not _XML_AVAILABLE:
        use_strict_parser = 0
    if use_strict_parser:
        # initialize the SAX parser
        feedparser = _StrictFeedParser(baseuri, baselang, 'utf-8')
        saxparser = xml.sax.make_parser(PREFERRED_XML_PARSERS)
        saxparser.setFeature(xml.sax.handler.feature_namespaces, 1)
        saxparser.setContentHandler(feedparser)
        saxparser.setErrorHandler(feedparser)
        source = xml.sax.xmlreader.InputSource()
        source.setByteStream(_StringIO(data))
        if hasattr(saxparser, '_ns_stack'):
            # work around bug in built-in SAX parser (doesn't recognize xml: namespace)
            # PyXML doesn't have this problem, and it doesn't have _ns_stack either
            saxparser._ns_stack.append({'http://www.w3.org/XML/1998/namespace':'xml'})
        try:
            saxparser.parse(source)
        except Exception, e:
            if _debug:
                import traceback
                traceback.print_stack()
                traceback.print_exc()
                sys.stderr.write('xml parsing failed\n')
            result['bozo'] = 1
            result['bozo_exception'] = feedparser.exc or e
            use_strict_parser = 0
    if not use_strict_parser:
        feedparser = _LooseFeedParser(baseuri, baselang, known_encoding and 'utf-8' or '', entities)
        feedparser.feed(data)
    result['feed'] = feedparser.feeddata
    result['entries'] = feedparser.entries
    result['version'] = result['version'] or feedparser.version
    result['namespaces'] = feedparser.namespacesInUse
    return result

class Serializer:
    def __init__(self, results):
        self.results = results

class TextSerializer(Serializer):
    def write(self, stream=sys.stdout):
        self._writer(stream, self.results, '')

    def _writer(self, stream, node, prefix):
        if not node: return
        if hasattr(node, 'keys'):
            keys = node.keys()
            keys.sort()
            for k in keys:
                if k in ('description', 'link'): continue
                if node.has_key(k + '_detail'): continue
                if node.has_key(k + '_parsed'): continue
                self._writer(stream, node[k], prefix + k + '.')
        elif type(node) == types.ListType:
            index = 0
            for n in node:
                self._writer(stream, n, prefix[:-1] + '[' + str(index) + '].')
                index += 1
        else:
            try:
                s = str(node).encode('utf-8')
                s = s.replace('\\', '\\\\')
                s = s.replace('\r', '')
                s = s.replace('\n', r'\n')
                stream.write(prefix[:-1])
                stream.write('=')
                stream.write(s)
                stream.write('\n')
            except:
                pass

class PprintSerializer(Serializer):
    def write(self, stream=sys.stdout):
        if self.results.has_key('href'):
            stream.write(self.results['href'] + '\n\n')
        from pprint import pprint
        pprint(self.results, stream)
        stream.write('\n')

if __name__ == '__main__':
    try:
        from optparse import OptionParser
    except:
        OptionParser = None

    if OptionParser:
        optionParser = OptionParser(version=__version__, usage="%prog [options] url_or_filename_or_-")
        optionParser.set_defaults(format="pprint")
        optionParser.add_option("-A", "--user-agent", dest="agent", metavar="AGENT", help="User-Agent for HTTP URLs")
        optionParser.add_option("-e", "--referer", "--referrer", dest="referrer", metavar="URL", help="Referrer for HTTP URLs")
        optionParser.add_option("-t", "--etag", dest="etag", metavar="TAG", help="ETag/If-None-Match for HTTP URLs")
        optionParser.add_option("-m", "--last-modified", dest="modified", metavar="DATE", help="Last-modified/If-Modified-Since for HTTP URLs (any supported date format)")
        optionParser.add_option("-f", "--format", dest="format", metavar="FORMAT", help="output results in FORMAT (text, pprint)")
        optionParser.add_option("-v", "--verbose", action="store_true", dest="verbose", default=False, help="write debugging information to stderr")
        (options, urls) = optionParser.parse_args()
        if options.verbose:
            _debug = 1
        if not urls:
            optionParser.print_help()
            sys.exit(0)
    else:
        if not sys.argv[1:]:
            print __doc__
            sys.exit(0)
        class _Options:
            etag = modified = agent = referrer = None
            format = 'pprint'
        options = _Options()
        urls = sys.argv[1:]

    zopeCompatibilityHack()

    serializer = globals().get(options.format.capitalize() + 'Serializer', Serializer)
    for url in urls:
        results = parse(url, etag=options.etag, modified=options.modified, agent=options.agent, referrer=options.referrer)
        serializer(results).write(sys.stdout)
