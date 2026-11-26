#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

"""
Compatibility module for recipes and plugins written for css_selectors, the
selector engine calibre used before kgcss. calibre itself uses kgcss directly.

Differences from css_selectors:

* ``parse()`` is :func:`kgcss.parse_selectors`: ``specificity`` is a property
  that is a 3-tuple, not a method.
* ``Select`` accepts ``default_lang``, ``dispatch_map`` and ``trace`` and
  ignores them, and has no ``invalidate_caches()``: make a new ``Select``
  after changing the tree.
* Matching follows Selectors Level 4 more closely, see the kgcss
  documentation. Ids and classes still match case-insensitively, as they
  did in css_selectors.
"""

from typing import TYPE_CHECKING

from kgcss import INAPPROPRIATE_PSEUDO_CLASSES, ExpressionError, SelectorError, SelectorSyntaxError
from kgcss import Select as _Select
from kgcss import parse_selectors as parse

if TYPE_CHECKING:
    from kgcss.matching import Element

__all__ = ['INAPPROPRIATE_PSEUDO_CLASSES', 'ExpressionError', 'Select', 'SelectorError', 'SelectorSyntaxError', 'parse']


class Select(_Select):
    """:class:`kgcss.Select` with the signature of css_selectors' ``Select``,
    matching ids and classes case-insensitively as it did"""

    def __init__(
        self,
        root: Element,
        default_lang: object = None,
        ignore_inappropriate_pseudo_classes: bool = False,
        dispatch_map: object = None,
        trace: object = False,
    ) -> None:
        super().__init__(root, ignore_inappropriate_pseudo_classes, quirks_mode=True)
