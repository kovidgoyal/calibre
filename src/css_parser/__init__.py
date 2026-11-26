#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"""
Compatibility module for plugins written for css_parser, the CSS library
calibre used before kgcss. calibre itself uses kgcss directly.

The objects are those of :mod:`kgcss.compat`: css_parser-style views of kgcss
objects. The parsing functions, :func:`getUrls`, :func:`replaceUrls`,
:func:`resolveImports` and :class:`CSSParser` work as in css_parser. Logging
options and the global serializer preferences of css_parser are accepted and
ignored: kgcss writes CSS in a fixed, normalized form, see its documentation.
"""

import logging
from collections.abc import Callable

from css_parser import css
from kgcss.compat import getUrls, parseRule, parseString, parseStyle, replaceUrls, resolveImports, serialize

__all__ = ['CSSParser', 'css', 'getUrls', 'log', 'parseRule', 'parseString', 'parseStyle', 'replaceUrls', 'resolveImports', 'serialize']

type Fetcher = Callable[[str], tuple[str | None, str | bytes | None] | None]

#: Code written for css_parser sets the level of this logger, it has no effect
log = logging.getLogger('css_parser')


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
