#!/usr/bin/env python
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from typing import TYPE_CHECKING, cast

from calibre.ebooks.oeb.base import OEB_DOCS
from calibre.utils.localization import _

if TYPE_CHECKING:
    from collections.abc import Callable

    from lxml.etree import _Element

    from calibre.ebooks.oeb.polish.container import Container


def add_soft_hyphens(container: Container, report: Callable[[str], object] | None = None) -> None:
    from calibre.utils.hyphenation.hyphenate import add_soft_hyphens_to_html

    for name, mt in container.mime_map.items():
        if mt not in OEB_DOCS:
            continue
        add_soft_hyphens_to_html(cast('_Element', container.parsed(name)), container.mi.language)  # HTML files are parsed into lxml trees
        container.dirty(name)
    if report is not None:
        report(_('Soft hyphens added'))


def remove_soft_hyphens(container: Container, report: Callable[[str], object] | None = None) -> None:
    from calibre.utils.hyphenation.hyphenate import remove_soft_hyphens_from_html

    for name, mt in container.mime_map.items():
        if mt not in OEB_DOCS:
            continue
        remove_soft_hyphens_from_html(cast('_Element', container.parsed(name)))  # HTML files are parsed into lxml trees
        container.dirty(name)
    if report is not None:
        report(_('Soft hyphens removed'))
