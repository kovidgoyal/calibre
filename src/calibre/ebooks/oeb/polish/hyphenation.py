#!/usr/bin/env python
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

from calibre.ebooks.oeb.base import OEB_DOCS
from polyglot.builtins import iteritems


def add_soft_hyphens(container, report=None):
    from calibre.utils.hyphenation.hyphenate import add_soft_hyphens_to_html
    for name, mt in iteritems(container.mime_map):
        if mt not in OEB_DOCS:
            continue
        add_soft_hyphens_to_html(container.parsed(name), container.mi.language)
        container.dirty(name)
    if report is not None:
        report(_('Soft hyphens added'))


def remove_soft_hyphens(container, report=None):
    from calibre.utils.hyphenation.hyphenate import remove_soft_hyphens_from_html
    for name, mt in iteritems(container.mime_map):
        if mt not in OEB_DOCS:
            continue
        remove_soft_hyphens_from_html(container.parsed(name))
        container.dirty(name)
    if report is not None:
        report(_('Soft hyphens removed'))
