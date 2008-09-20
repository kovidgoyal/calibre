#!/usr/bin/env python
"""encutils - encoding detection collection for Python

encutils
========
:Author: Christof Hoeke, see http://cthedot.de/encutils/
:Copyright: 2005-2008: Christof Hoeke
:License: encutils has a dual-license, please choose whatever you prefer:

    * encutils is published under the `LGPL 3 or later <http://cthedot.de/encutils/license/>`__
    * encutils is published under the  
      `Creative Commons License <http://creativecommons.org/licenses/by/3.0/>`__.
      
    This file is part of encutils.

    encutils is free software: you can redistribute it and/or modify
    it under the terms of the GNU Lesser General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    encutils is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Lesser General Public License for more details.

    You should have received a copy of the GNU Lesser General Public License
    along with encutils.  If not, see <http://www.gnu.org/licenses/>.
 

A collection of helper functions to detect encodings of text files (like HTML, XHTML, XML, CSS, etc.) retrieved via HTTP, file or string.

``getEncodingInfo`` is probably the main function of interest which uses
other supplied functions itself and gathers all information together and
supplies an ``EncodingInfo`` object with the following properties:

- ``encoding``: The guessed encoding
    Encoding is the explicit or implicit encoding or None and
    always lowercase.

- from HTTP response    
    * ``http_encoding``
    * ``http_media_type``

- from HTML <meta> element    
    * ``meta_encoding``
    * ``meta_media_type``

- from XML declaration
    * ``xml_encoding``

example::

    >>> import encutils
    >>> info = encutils.getEncodingInfo(url='http://cthedot.de/encutils/')
    
    >>> print info  # = str(info)
    utf-8
    
    >>> info        # = repr(info)
    <encutils.EncodingInfo object encoding='utf-8' mismatch=False at 0xb86d30>
    
    >>> print info.logtext
    HTTP media_type: text/html
    HTTP encoding: utf-8
    HTML META media_type: text/html
    HTML META encoding: utf-8
    Encoding (probably): utf-8 (Mismatch: False)


references
==========
XML
    RFC 3023 (http://www.ietf.org/rfc/rfc3023.txt)
    
    easier explained in 
        - http://feedparser.org/docs/advanced.html
        - http://www.xml.com/pub/a/2004/07/21/dive.html
        
HTML
    http://www.w3.org/TR/REC-html40/charset.html#h-5.2.2

TODO
====
- parse @charset of HTML elements?
- check for more texttypes if only text given
    
"""
__all__ = ['buildlog',
           'encodingByMediaType',
           'getHTTPInfo',
           'getMetaInfo',
           'detectXMLEncoding',
           'getEncodingInfo',
           'tryEncodings',
           'EncodingInfo']
__docformat__ = 'restructuredtext'
__author__ = 'Christof Hoeke'
__version__ = '0.8.3 $Id: __init__.py 1138 2008-03-15 18:24:46Z cthedot $'

import cgi
import HTMLParser
import httplib
import re
import StringIO
import sys
import types
import urllib

class _MetaHTMLParser(HTMLParser.HTMLParser):
    """parses given data for <meta http-equiv="content-type">"""
    content_type = None
    
    def handle_starttag(self, tag, attrs):
        if tag == 'meta' and not self.content_type:
            atts = dict([(a.lower(), v.lower()) for a, v in attrs])
            if atts.get('http-equiv', u'').strip() == u'content-type':
                self.content_type = atts.get('content')


# application/xml, application/xml-dtd, application/xml-external-parsed-entity, or a subtype like application/rss+xml.
_XML_APPLICATION_TYPE = 0

# text/xml, text/xml-external-parsed-entity, or a subtype like text/AnythingAtAll+xml
_XML_TEXT_TYPE = 1

# text/html
_HTML_TEXT_TYPE = 2

# any other of text/* like text/plain, ...
_TEXT_TYPE = 3

# any text/* like which defaults to UTF-8 encoding, for now only text/css
_TEXT_UTF8 = 5

# types not fitting in above types
_OTHER_TYPE = 4

class EncodingInfo(object):
    """
    All encoding related information, returned by ``getEncodingInfo``
    
    - ``encoding``: The guessed encoding
        Encoding is the explicit or implicit encoding or None and
        always lowercase.

    - from HTTP response    
        * ``http_encoding``
        * ``http_media_type``

    - from HTML <meta> element    
        * ``meta_encoding``
        * ``meta_media_type``

    - from XML declaration
        * ``xml_encoding``

    - ``mismatch``: True if mismatch between XML declaration and HTTP header
        Mismatch is True if any mismatches between HTTP header, XML
        declaration or textcontent (meta) are found. More detailed mismatch
        reports are written to the optional log or ``logtext``

        Mismatches are not necessarily errors as preferences are defined.
        For details see the specifications.

    - ``logtext``: if no log was given log reports are given here 
    
    """
    def __init__(self):
        """
        initializes all possible properties to ``None``, see class
        description
        """
        self.encoding = self.mismatch = self.logtext =\
            self.http_encoding = self.http_media_type =\
            self.meta_encoding = self.meta_media_type =\
            self.xml_encoding =\
                None
        
    def __str__(self):
        """
        ``str(EncodingInfo())`` outputs the guessed encoding itself or the empty string
        """
        if self.encoding:
            return self.encoding
        else:
            return u''
            
    def __repr__(self):
        return "<%s.%s object encoding=%r mismatch=%s at 0x%x>" % (
                self.__class__.__module__, self.__class__.__name__, 
                self.encoding, self.mismatch, id(self))


def buildlog(logname='encutils', level='INFO', stream=sys.stderr,
            filename=None, filemode="w",
            format='%(levelname)s\t%(message)s'):
    """
    helper to build a basic log
    
    - if ``filename`` is given returns a log logging to ``filename`` with
      mode ``filemode``
    - else uses a log streaming to ``stream`` which defaults to
      ``sys.stderr``
    - ``level`` defines the level of the log
    - ``format`` defines the formatter format of the log

    returns a log with the name ``logname``
    """
    import logging
    
    log = logging.getLogger(logname)
    
    if filename:
        hdlr = logging.FileHandler(filename, filemode)
    else:
        hdlr = logging.StreamHandler(stream)
        
    formatter = logging.Formatter(format)
    hdlr.setFormatter(formatter)

    log.addHandler(hdlr)
    log.setLevel(logging.__dict__.get(level, logging.INFO))

    return log    

def _getTextTypeByMediaType(media_type, log=None):
    """
    returns type as defined by constants above
    """
    if not media_type:
        return _OTHER_TYPE
    
    xml_application_types = [
        ur'application/.*?\+xml',
        u'application/xml',
        u'application/xml-dtd',
        u'application/xml-external-parsed-entity']
    xml_text_types = [
        ur'text\/.*?\+xml',
        u'text/xml',
        u'text/xml-external-parsed-entity']
    
    media_type = media_type.strip().lower()

    if media_type in xml_application_types or\
            re.match(xml_application_types[0], media_type, re.I|re.S|re.X):
        return _XML_APPLICATION_TYPE
    elif media_type in xml_text_types or\
            re.match(xml_text_types[0], media_type, re.I|re.S|re.X):
        return _XML_TEXT_TYPE
    elif media_type == u'text/html':
        return _HTML_TEXT_TYPE
    elif media_type == u'text/css':
        return _TEXT_UTF8
    elif media_type.startswith(u'text/'):
        return _TEXT_TYPE
    else:
        return _OTHER_TYPE    

def _getTextType(text, log=None):
    """
    checks if given text is XML (**naive test!**)
    used if no content-type given    
    """
    if text[:30].find(u'<?xml version=') != -1:
        return _XML_APPLICATION_TYPE
    else:
        return _OTHER_TYPE
    
def encodingByMediaType(media_type, log=None):
    """
    Returns a default encoding for the given media_type.
    For example ``'utf-8'`` for ``media_type='application/xml'``. 

    Refers to RFC 3023 and HTTP MIME specification.
   
    If no default encoding is available returns ``None``.
    """
    defaultencodings = {
        _XML_APPLICATION_TYPE: u'utf-8',
        _XML_TEXT_TYPE: u'ascii',
        _HTML_TEXT_TYPE: u'iso-8859-1', # should be None?
        _TEXT_TYPE: u'iso-8859-1', # should be None?
        _TEXT_UTF8: u'utf-8',
        _OTHER_TYPE: None}

    texttype = _getTextTypeByMediaType(media_type)
    encoding = defaultencodings.get(texttype, None)

    if log:
        if not encoding:
            log.debug(u'"%s" Media-Type has no default encoding',
                media_type)
        else:
            log.debug(
                u'Default encoding for Media Type "%s": %s',
                media_type, encoding)
    return encoding

def getHTTPInfo(response, log=None):
    """
    Returns ``(media_type, encoding)`` information from the response'
    Content-Type HTTP header. (Case of headers is ignored.)
    May be ``(None, None)`` e.g. if no Content-Type header is
    available.
    """
    info = response.info()
    media_type = info.gettype()
    encoding = info.getparam('charset') 

    if encoding:
        encoding = encoding.lower()

    if log:
        log.info(u'HTTP media_type: %s', media_type)
        log.info(u'HTTP encoding: %s', encoding)

    return media_type, encoding

def getMetaInfo(text, log=None):
    """
    Returns (media_type, encoding) information from (first)
    X/HTML Content-Type ``<meta>`` element if available.

    Normally in X/HTML:
        ``<meta http-equiv="Content-Type" content="media_type;
        charset=encoding"/>``
    """
    p = _MetaHTMLParser()
    p.feed(text)
    if p.content_type:
        media_type, params = cgi.parse_header(p.content_type)
        encoding = params.get('charset') # defaults to None
        if encoding:
            encoding = encoding.lower()
        if log:
            log.info(u'HTML META media_type: %s', media_type)
            log.info(u'HTML META encoding: %s', encoding)
    else:
        media_type = encoding = None

    return media_type, encoding

def detectXMLEncoding(fp, log=None, includeDefault=True):
    """
    Attempts to detect the character encoding of the xml file
    given by a file object fp. fp must not be a codec wrapped file
    object! fp may also be a string or unicode string

    The return value can be:
        - if detection of the BOM succeeds, the codec name of the
          corresponding unicode charset is returned

        - if BOM detection fails, the xml declaration is searched for
          the encoding attribute and its value returned. the "<"
          character has to be the very first in the file then (it's xml
          standard after all).

        - if BOM and xml declaration fail, utf-8 is returned according
          to XML 1.0.

    Based on a recipe by Lars Tiede:
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/363841
    which itself is based on Paul Prescotts recipe:
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/52257
    """
    if type(fp) in types.StringTypes:
        fp = StringIO.StringIO(fp)
    
    ### detection using BOM
    
    ## the BOMs we know, by their pattern
    bomDict={ # bytepattern: name              
             (0x00, 0x00, 0xFE, 0xFF) : "utf_32_be",        
             (0xFF, 0xFE, 0x00, 0x00) : "utf_32_le",
             (0xFE, 0xFF, None, None) : "utf_16_be", 
             (0xFF, 0xFE, None, None) : "utf_16_le", 
             (0xEF, 0xBB, 0xBF, None) : "utf-8",
            }

    ## go to beginning of file and get the first 4 bytes
    oldFP = fp.tell()
    fp.seek(0)
    (byte1, byte2, byte3, byte4) = tuple(map(ord, fp.read(4)))

    ## try bom detection using 4 bytes, 3 bytes, or 2 bytes
    bomDetection = bomDict.get((byte1, byte2, byte3, byte4))
    if not bomDetection:
        bomDetection = bomDict.get((byte1, byte2, byte3, None))
        if not bomDetection:
            bomDetection = bomDict.get((byte1, byte2, None, None))

    ## if BOM detected, we're done :-)
    if bomDetection:
        if log:
            log.info(u'XML BOM encoding: %s' % bomDetection)
        fp.seek(oldFP)
        return bomDetection

    ## still here? BOM detection failed.
    ##  now that BOM detection has failed we assume one byte character
    ##  encoding behaving ASCII
    
    ### search xml declaration for encoding attribute

    ## assume xml declaration fits into the first 2 KB (*cough*)
    fp.seek(0)
    buffer = fp.read(2048)

    ## set up regular expression
    xmlDeclPattern = r"""
    ^<\?xml             # w/o BOM, xmldecl starts with <?xml at the first byte
    .+?                 # some chars (version info), matched minimal
    encoding=           # encoding attribute begins
    ["']                # attribute start delimiter
    (?P<encstr>         # what's matched in the brackets will be named encstr
     [^"']+              # every character not delimiter (not overly exact!)
    )                   # closes the brackets pair for the named group
    ["']                # attribute end delimiter
    .*?                 # some chars optionally (standalone decl or whitespace)
    \?>                 # xmldecl end
    """
    xmlDeclRE = re.compile(xmlDeclPattern, re.VERBOSE)

    ## search and extract encoding string
    match = xmlDeclRE.search(buffer)
    fp.seek(oldFP)
    if match:
        enc = match.group("encstr").lower()
        if log:
            log.info(u'XML encoding="%s"' % enc)
        return enc
    else:
        if includeDefault:
            if log:
                log.info(u'XML encoding default utf-8')
            return u'utf-8'
        else:
            return None

def tryEncodings(text, log=None):
    """
    If installed uses chardet http://chardet.feedparser.org/ to detect
    encoding, else tries different encodings on text and returns the one
    that does not raise an exception which is not very advanced or may
    be totally wrong.

    Returns working encoding or None if no encoding does work at all.

    The returned encoding might nevertheless be not the one intended by the
    author as it is only checked if the text might be encoded in that
    encoding. Some texts might be working in "iso-8859-1" *and*
    "windows-1252" *and* "ascii" *and* "utf-8" and ...
    """
    try:
        import chardet
        encoding = chardet.detect(text)["encoding"]

    except ImportError:
        msg = 'Using simplified encoding detection, you might want to install chardet.'
        if log:
            log.warn(msg)
        else:
            print msg
        
        encodings = (
            'ascii',
            'iso-8859-1',
            'windows-1252',
            'utf-8'
            )
        encoding = None
        for e in encodings:
            try:
                text.encode(e)
            except (UnicodeEncodeError, UnicodeDecodeError):
                pass
            else:
                encoding = e
                break

    return encoding
            
def getEncodingInfo(response=None, text=u'', log=None, url=None):
    """
    Finds all encoding related information in given ``text``.
    Uses information in headers of supplied HTTPResponse, possible XML
    declaration and X/HTML ``<meta>`` elements.
    ``text`` will mostly be HTML or XML.
    
    Parameters
        - ``response``: HTTP response object,
          e.g. ``urllib.urlopen('url')``
        - ``text``: to guess encoding for, might include XML
          prolog with encoding pseudo attribute or HTML meta element 
        - ``log``: an optional logging logger to which messages may go, if
          no log given all log messages are available from resulting
          ``EncodingInfo``

    May also simply be called with ``getEncodingInfo(url='URL')`` which fetches
    the url and all needed information.

    Returns instance of ``EncodingInfo``.

    How the resulting encoding is retrieved
    =======================================
    XML
    ---
    RFC 3023 states if media type given in the Content-Type HTTP header is
    application/xml, application/xml-dtd,
    application/xml-external-parsed-entity, or any one of the subtypes of
    application/xml such as application/atom+xml or application/rss+xml
    etc then the character encoding is determined in this order:

    1. the encoding given in the charset parameter of the Content-Type HTTP
    header, or
    2. the encoding given in the encoding attribute of the XML declaration
    within the document, or
    3. utf-8.

    Mismatch possibilities:
        - HTTP + XMLdecla 
        - HTTP + HTMLmeta

        application/xhtml+xml ?
            XMLdecla + HTMLmeta   
        
    If the media type given in the Content-Type HTTP header is text/xml,
    text/xml-external-parsed-entity, or a subtype like text/Anything+xml,
    the encoding attribute of the XML declaration is ignored completely
    and the character encoding is determined in the order:
    1. the encoding given in the charset parameter of the Content-Type HTTP
    header, or
    2. ascii.

    Mismatch possibilities:
        - HTTP + XMLdecla 
        - HTTP + HTMLmeta 
        
        text/xhtml+xml
            XMLdecla + HTMLmeta 

    HTML
    ----
    For HTML served as text/html:
        http://www.w3.org/TR/REC-html40/charset.html#h-5.2.2 

    1. An HTTP "charset" parameter in a "Content-Type" field.
       (maybe defaults to ISO-8859-1, but should not assume this)
    2. A META declaration with "http-equiv" set to "Content-Type" and a
       value set for "charset".
    3. The charset attribute set on an element that designates an external
       resource. (NOT IMPLEMENTED HERE YET)

    Mismatch possibilities:
        - HTTP + HTMLmeta 
        
    TEXT
    ----
    For most text/* types the encoding will be reported as iso-8859-1. 
    Exceptions are XML formats send as text/* mime type (see above) and 
    text/css which has a default encoding of UTF-8. 
    """
    if url:
        try:
            response = urllib.urlopen(url)
            text = response.read()
        except IOError, e:
            print IOError(e)
            sys.exit(1)
        
    encinfo = EncodingInfo()

    logstream = StringIO.StringIO()
    if not log:
        log = buildlog(stream=logstream, format='%(message)s')
        
    # HTTP
    if response:
        encinfo.http_media_type, encinfo.http_encoding = getHTTPInfo(
            response, log)
        texttype = _getTextTypeByMediaType(encinfo.http_media_type, log)
    else:
        # check if maybe XML or (TODO:) HTML
        texttype = _getTextType(text, log)

    # XML (also XHTML served as text/html)
    if texttype == _XML_APPLICATION_TYPE or texttype == _XML_TEXT_TYPE:
        encinfo.xml_encoding = detectXMLEncoding(text, log)

    # XML (also XHTML served as text/html)
    if texttype == _HTML_TEXT_TYPE:
        encinfo.xml_encoding = detectXMLEncoding(text, log, includeDefault=False)

    # HTML
    if texttype == _HTML_TEXT_TYPE or texttype == _TEXT_TYPE:
        encinfo.meta_media_type, encinfo.meta_encoding = getMetaInfo(
            text, log)

    # guess
    # 1. HTTP charset?
    encinfo.encoding = encinfo.http_encoding
    encinfo.mismatch = False

    # 2. media_type?
    #   XML application/...
    if texttype == _XML_APPLICATION_TYPE:
        if not encinfo.encoding:
            encinfo.encoding = encinfo.xml_encoding
            # xml_encoding has default of utf-8            

    #   text/html
    elif texttype == _HTML_TEXT_TYPE:
        if not encinfo.encoding:
            encinfo.encoding = encinfo.meta_encoding
        if not encinfo.encoding:
            encinfo.encoding = encodingByMediaType(encinfo.http_media_type)
        if not encinfo.encoding:
            encinfo.encoding = tryEncodings(text)

    #   text/... + xml or text/*
    elif texttype == _XML_TEXT_TYPE or texttype == _TEXT_TYPE:
        if not encinfo.encoding:
            encinfo.encoding = encodingByMediaType(encinfo.http_media_type)

    # possible mismatches, checks if present at all and then if equal
    # HTTP + XML
    if encinfo.http_encoding and encinfo.xml_encoding and\
       encinfo.http_encoding <> encinfo.xml_encoding:
        encinfo.mismatch = True
        log.warn(u'"%s" (HTTP) <> "%s" (XML) encoding mismatch' %
                 (encinfo.http_encoding, encinfo.xml_encoding))
    # HTTP + Meta
    if encinfo.http_encoding and encinfo.meta_encoding and\
         encinfo.http_encoding <> encinfo.meta_encoding:
        encinfo.mismatch = True
        log.warn(u'"%s" (HTTP) <> "%s" (HTML <meta>) encoding mismatch' %
                 (encinfo.http_encoding, encinfo.meta_encoding))
    # XML + Meta
    if encinfo.xml_encoding and encinfo.meta_encoding and\
         encinfo.xml_encoding <> encinfo.meta_encoding:
        encinfo.mismatch = True
        log.warn(u'"%s" (XML) <> "%s" (HTML <meta>) encoding mismatch' %
                 (encinfo.xml_encoding, encinfo.meta_encoding))
                
    log.info(u'Encoding (probably): %s (Mismatch: %s)',
             encinfo.encoding, encinfo.mismatch)

    encinfo.logtext = logstream.getvalue()
    return encinfo


if __name__ == '__main__':
    import pydoc
    pydoc.help(__name__)