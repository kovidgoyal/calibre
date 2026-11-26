#!/usr/bin/env python
# License: GPLv3 Copyright: 2015, Kovid Goyal <kovid at kovidgoyal.net>

"""
Compatibility module for recipes and plugins written for css_selectors, the
selector engine calibre used before kgcss. calibre itself uses kgcss directly.

Differences from css_selectors:

* ``parse()`` is :func:`kgcss.parse_selectors`: ``specificity`` is a property
  that is a 3-tuple, not a method.
* ``Select`` accepts ``default_lang``, ``dispatch_map`` and ``trace`` and
  ignores them. ``invalidate_caches()`` must be called after changing the
  tree, as before.
* As in css_selectors, a ``Select`` made from an element that is not the root
  of its document only returns elements in the subtree of that element. The
  selectors are matched against the whole document, so ``div a`` matches the
  ``a`` elements of the subtree that are inside a ``div`` outside of it.
* Matching follows Selectors Level 4 more closely, see the kgcss
  documentation. Ids and classes still match case-insensitively, as they
  did in css_selectors.
"""

from collections.abc import Iterable, Iterator
from typing import overload

from kgcss import INAPPROPRIATE_PSEUDO_CLASSES, ElementTreeLike, ExpressionError, Selector, SelectorError, SelectorList, SelectorSyntaxError
from kgcss import Select as _Select
from kgcss import parse_selectors as parse

type SelectorArg = str | Selector | SelectorList | Iterable[Selector]

__all__ = ['INAPPROPRIATE_PSEUDO_CLASSES', 'ExpressionError', 'Select', 'SelectorError', 'SelectorSyntaxError', 'parse']


class Select[E](_Select[E]):
    """:class:`kgcss.Select` with the signature and behavior of css_selectors' ``Select``"""

    @overload
    def __init__(
        self,
        root: ElementTreeLike[E],
        default_lang: object = None,
        ignore_inappropriate_pseudo_classes: bool = False,
        dispatch_map: object = None,
        trace: object = False,
    ) -> None: ...
    @overload
    def __init__(
        self,
        root: E,
        default_lang: object = None,
        ignore_inappropriate_pseudo_classes: bool = False,
        dispatch_map: object = None,
        trace: object = False,
    ) -> None: ...
    def __init__(
        self,
        root: E | ElementTreeLike[E],
        default_lang: object = None,
        ignore_inappropriate_pseudo_classes: bool = False,
        dispatch_map: object = None,
        trace: object = False,
    ) -> None:
        # css_selectors matched ids and classes case-insensitively
        super().__init__(root, ignore_inappropriate_pseudo_classes, quirks_mode=True)
        self._subtree: E | None = None
        getroottree = getattr(self.root, 'getroottree', None)
        if getroottree is not None and getroottree().getroot() is not self.root:
            # css_selectors only returned elements of the subtree of root
            self._subtree = self.root

    def select(self, selector: SelectorArg, root: E | None = None) -> Iterator[E]:
        return super().select(selector, self._subtree if root is None else root)

    __call__ = select

    def has_matches(self, selector: SelectorArg, root: E | None = None) -> bool:
        return super().has_matches(selector, self._subtree if root is None else root)

    def invalidate_caches(self) -> None:
        "Take a new snapshot of the tree, after changing it"
        subtree = self._subtree
        super().__init__(self.root, self.ignore_inappropriate_pseudo_classes, quirks_mode=True)
        self._subtree = subtree
