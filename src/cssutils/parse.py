#!/usr/bin/env python
"""a validating CSSParser
"""
__all__ = ['CSSParser']
__docformat__ = 'restructuredtext'
__version__ = '$Id: parse.py 1418 2008-08-09 19:27:50Z cthedot $'

import codecs
import os
import urllib
from helper import Deprecated
import tokenize2
import cssutils

class CSSParser(object):
    """
    parses a CSS StyleSheet string or file and
    returns a DOM Level 2 CSS StyleSheet object

    Usage::

        parser = CSSParser()

        # optionally
        parser.setFetcher(fetcher)

        sheet = parser.parseFile('test1.css', 'ascii')

        print sheet.cssText
    """
    def __init__(self, log=None, loglevel=None, raiseExceptions=None,
                 fetcher=None):
        """
        log
            logging object
        loglevel
            logging loglevel
        raiseExceptions
            if log should simply log (default) or raise errors during
            parsing. Later while working with the resulting sheets
            the setting used in cssutils.log.raiseExeptions is used
        fetcher
            see ``setFetchUrl(fetcher)``
        """
        if log is not None:
            cssutils.log.setLog(log)
        if loglevel is not None:
            cssutils.log.setLevel(loglevel)

        # remember global setting
        self.__globalRaising = cssutils.log.raiseExceptions
        if raiseExceptions:
            self.__parseRaising = raiseExceptions
        else:
            # DEFAULT during parse
            self.__parseRaising = False

        self.__tokenizer = tokenize2.Tokenizer()
        self.setFetcher(fetcher)

    def __parseSetting(self, parse):
        """during parse exceptions may be handled differently depending on
        init parameter ``raiseExceptions``
        """
        if parse:
            cssutils.log.raiseExceptions = self.__parseRaising
        else:
            cssutils.log.raiseExceptions = self.__globalRaising

    def parseString(self, cssText, encoding=None, href=None, media=None,
                    title=None):
        """Return parsed CSSStyleSheet from given string cssText.
        Raises errors during retrieving (e.g. UnicodeDecodeError).

        cssText
            CSS string to parse
        encoding
            If ``None`` the encoding will be read from BOM or an @charset
            rule or defaults to UTF-8.
            If given overrides any found encoding including the ones for
            imported sheets.
            It also will be used to decode ``cssText`` if given as a (byte)
            string.
        href
            The href attribute to assign to the parsed style sheet.
            Used to resolve other urls in the parsed sheet like @import hrefs
        media
            The media attribute to assign to the parsed style sheet
            (may be a MediaList, list or a string)
        title
            The title attribute to assign to the parsed style sheet
        """
        self.__parseSetting(True)
        if isinstance(cssText, str):
            cssText = codecs.getdecoder('css')(cssText, encoding=encoding)[0]

        sheet = cssutils.css.CSSStyleSheet(href=href,
                                           media=cssutils.stylesheets.MediaList(media),
                                           title=title)
        sheet._setFetcher(self.__fetcher)
        # tokenizing this ways closes open constructs and adds EOF
        sheet._setCssTextWithEncodingOverride(self.__tokenizer.tokenize(cssText,
                                                                        fullsheet=True),
                                              encodingOverride=encoding)
        self.__parseSetting(False)
        return sheet

    def parseFile(self, filename, encoding=None,
                  href=None, media=None, title=None):
        """Retrieve and return a CSSStyleSheet from given filename.
        Raises errors during retrieving (e.g. IOError).

        filename
            of the CSS file to parse, if no ``href`` is given filename is
            converted to a (file:) URL and set as ``href`` of resulting
            stylesheet.
            If href is given it is set as ``sheet.href``. Either way
            ``sheet.href`` is used to resolve e.g. stylesheet imports via
            @import rules.
        encoding
            Value ``None`` defaults to encoding detection via BOM or an
            @charset rule.
            Other values override detected encoding for the sheet at
            ``filename`` including any imported sheets.

        for other parameters see ``parseString``
        """
        if not href:
            # prepend // for file URL, urllib does not do this?
            href = u'file:' + urllib.pathname2url(os.path.abspath(filename))

        return self.parseString(open(filename, 'rb').read(),
                                encoding=encoding, # read returns a str
                                href=href, media=media, title=title)

    def parseUrl(self, href, encoding=None, media=None, title=None):
        """Retrieve and return a CSSStyleSheet from given href (an URL).
        In case of any errors while reading the URL returns None.

        href
            URL of the CSS file to parse, will also be set as ``href`` of
            resulting stylesheet
        encoding
            Value ``None`` defaults to encoding detection via HTTP, BOM or an
            @charset rule.
            A value overrides detected encoding for the sheet at ``href``
            including any imported sheets.

        for other parameters see ``parseString``
        """
        encoding, enctype, text = cssutils.util._readUrl(href,
                                                         overrideEncoding=encoding)
        if enctype == 5:
            # do not used if defaulting to UTF-8
            encoding = None
            
        if text is not None:
            return self.parseString(text, encoding=encoding,
                                    href=href, media=media, title=title)

    def setFetcher(self, fetcher=None):
        """Replace the default URL fetch function with a custom one.
        The fetcher function gets a single parameter

        ``url``
            the URL to read

        and returns ``(encoding, content)`` where ``encoding`` is the HTTP
        charset normally given via the Content-Type header (which may simply
        omit the charset) and ``content`` being the (byte) string content.
        The Mimetype should be 'text/css' but this has to be checked by the
        fetcher itself (the default fetcher emits a warning if encountering
        a different mimetype).

        Calling ``setFetcher`` with ``fetcher=None`` resets cssutils
        to use its default function.
        """
        self.__fetcher = fetcher

    @Deprecated('Use cssutils.CSSParser().parseFile() instead.')
    def parse(self, filename, encoding=None,
              href=None, media=None, title=None):
        self.parseFile(filename, encoding, href, media, title)
