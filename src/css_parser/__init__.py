#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""
Compatibility module for plugins written for css_parser, the CSS library
calibre used before kgcss. calibre itself uses kgcss directly.

The objects are those of :mod:`kgcss.compat`: css_parser-style views of kgcss
objects. The parsing functions, :func:`getUrls`, :func:`replaceUrls`,
:func:`resolveImports` and :class:`CSSParser` work as in css_parser. The
logging options and the serializer preferences of css_parser (``log``,
``ser.prefs``) are accepted and ignored: kgcss writes CSS in a fixed,
normalized form, see its documentation, and problems in CSS are not logged.
``profile.validate()`` uses kgcss's value grammar, see
:mod:`css_parser.profiles`. ``parseUrl()`` is not supported.
"""

from collections.abc import Callable

from css_parser import css, profiles, stylesheets
from css_parser.profiles import Profiles, profile
from css_parser.serialize import CSSSerializer
from kgcss.compat import getUrls, parseRule, parseString, parseStyle, replaceUrls, resolveImports

__all__ = [
    'CSSParser',
    'CSSSerializer',
    'Profiles',
    'css',
    'getUrls',
    'log',
    'parseFile',
    'parseRule',
    'parseString',
    'parseStyle',
    'profile',
    'profiles',
    'replaceUrls',
    'resolveImports',
    'ser',
    'stylesheets',
]

type Fetcher = Callable[[str], tuple[str | None, str | bytes | None] | None]


class ErrorHandler:
    "css_parser.log, whose settings are accepted and ignored"

    raiseExceptions = False

    def setLog(self, log: object) -> None:
        pass

    def setLevel(self, level: int) -> None:
        pass


log = ErrorHandler()
#: The serializer of css_parser, whose preferences are accepted and ignored
ser = CSSSerializer()


def parseFile(
    filename: str, encoding: str | None = None, href: str | None = None, media: object = None, title: object = None, validate: object = None
) -> css.CSSStyleSheet:
    from pathlib import Path

    with open(filename, 'rb') as f:
        data = f.read()
    return parseString(data, encoding, href or Path(filename).absolute().as_uri())


class CSSParser:
    "A parser with the API of css_parser's CSSParser. Only the fetcher, for @import rules, is used."

    def __init__(
        self,
        log: object = None,
        loglevel: object = None,
        raiseExceptions: object = None,
        fetcher: Fetcher | None = None,
        parseComments: object = True,
        validate: object = True,
    ) -> None:
        self.fetcher = fetcher

    def setFetcher(self, fetcher: Fetcher | None = None) -> None:
        self.fetcher = fetcher

    def parseString(
        self,
        cssText: str | bytes,
        encoding: str | None = None,
        href: str | None = None,
        media: object = None,
        title: object = None,
        validate: object = None,
    ) -> css.CSSStyleSheet:
        return parseString(cssText, encoding, href, fetcher=self.fetcher)

    def parseStyle(self, cssText: str, encoding: str = 'utf-8', validate: object = None) -> css.CSSStyleDeclaration:
        return parseStyle(cssText, encoding)

    def parseFile(
        self, filename: str, encoding: str | None = None, href: str | None = None, media: object = None, title: object = None, validate: object = None
    ) -> css.CSSStyleSheet:
        return parseFile(filename, encoding, href)
