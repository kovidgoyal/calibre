#!/usr/bin/env python
# License: GPLv3 Copyright: 2026, Kovid Goyal <kovid at kovidgoyal.net>
'''Coalesce repeated TOC-like link errors for the Check book UI.'''

from __future__ import annotations

from collections import OrderedDict
from typing import TYPE_CHECKING

from calibre.ebooks.oeb.polish.check.links import BadDestinationFragment, CaseMismatch, DanglingLink

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from calibre.ebooks.oeb.polish.check.base import BaseError


def _coalesce_key(err: BaseError) -> tuple | None:
    if isinstance(err, DanglingLink):
        return ('dangling', err.target_name)
    if isinstance(err, CaseMismatch):
        # Group by source file so one UI row → one replace_links batch
        return ('case', err.name)
    if isinstance(err, BadDestinationFragment):
        return ('badfrag', err.name, err.bad_href)
    return None


def coalesce_toc_link_errors(errors: Sequence[BaseError]) -> list[BaseError]:
    '''Collapse many similar TOC/link errors into fewer UI rows.

    The first error in each group becomes the list item and gains
    ``has_multiple_locations`` / ``all_locations``. Sibling errors are stored on
    ``coalesced_siblings`` so fix-all can still see every underlying error.
    '''
    groups: OrderedDict[tuple, list[BaseError]] = OrderedDict()
    others: list[BaseError] = []
    for err in errors:
        key = _coalesce_key(err)
        if key is None:
            others.append(err)
        else:
            groups.setdefault(key, []).append(err)

    out: list[BaseError] = []
    for errs in groups.values():
        primary = errs[0]
        if len(errs) > 1:
            primary.has_multiple_locations = True
            primary.all_locations = [(e.name, e.line, e.col) for e in errs]
            primary.coalesced_siblings = errs[1:]  # type: ignore[attr-defined]
        else:
            primary.coalesced_siblings = []  # type: ignore[attr-defined]
        out.append(primary)
    out.extend(others)
    return out


def expand_coalesced_errors(errors: Iterable[BaseError]) -> list[BaseError]:
    '''Expand UI-coalesced errors back to the full fixable set.'''
    out: list[BaseError] = []
    for err in errors:
        out.append(err)
        out.extend(getattr(err, 'coalesced_siblings', ()) or ())
    return out
