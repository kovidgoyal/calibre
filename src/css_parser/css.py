#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>

"The css_parser.css module, for plugins written for css_parser, see the css_parser package"

from kgcss.compat import (
    CSSCharsetRule,
    CSSComment,
    CSSFontFaceRule,
    CSSImportRule,
    CSSMediaRule,
    CSSNamespaceRule,
    CSSPageRule,
    CSSRule,
    CSSRuleList,
    CSSStyleDeclaration,
    CSSStyleRule,
    CSSStyleSheet,
    CSSUnknownRule,
    MediaList,
    Property,
    PropertyValue,
    Selector,
    SelectorList,
    Value,
)

__all__ = [
    'CSSCharsetRule',
    'CSSComment',
    'CSSFontFaceRule',
    'CSSImportRule',
    'CSSMediaRule',
    'CSSNamespaceRule',
    'CSSPageRule',
    'CSSRule',
    'CSSRuleList',
    'CSSStyleDeclaration',
    'CSSStyleRule',
    'CSSStyleSheet',
    'CSSUnknownRule',
    'MediaList',
    'Property',
    'PropertyValue',
    'Selector',
    'SelectorList',
    'Value',
]
