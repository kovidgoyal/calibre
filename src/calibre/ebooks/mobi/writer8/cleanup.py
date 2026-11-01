#!/usr/bin/env python
# License: GPLv3 Copyright: 2012, Kovid Goyal <kovid@kovidgoyal.net>

from typing import TYPE_CHECKING

from lxml import etree

from calibre.ebooks.oeb.base import XPath

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.oeb.base import Manifest, OEBBook
    from calibre.ebooks.oeb.stylizer import Stylizer
    from calibre.utils.logging import Log


class CSSCleanup:
    def __init__(self, log: Log, opts: Values) -> None:
        self.log, self.opts = log, opts

    def __call__(self, item: Manifest.Item, stylizer: Stylizer) -> None:
        root = item.data
        if not isinstance(root, etree._Element):  # only parsed XML has xpath()
            return

        # The Kindle touch displays all black pages if the height is set on
        # body
        for body in XPath('//h:body')(root):
            style = stylizer.style(body)
            style.drop('height')


def remove_duplicate_anchors(oeb: OEBBook) -> None:
    # The Kindle apparently has incorrect behavior for duplicate anchors, see
    # https://bugs.launchpad.net/calibre/+bug/1454199
    for item in oeb.spine:
        root = item.data
        if not isinstance(root, etree._Element):  # only parsed XML has xpath()
            continue
        seen = set()
        for tag in root.xpath('//*[@id or @name]'):
            for attr in ('id', 'name'):
                anchor = tag.get(attr)
                if anchor is not None:
                    if anchor in seen:
                        oeb.log.debug('Removing duplicate anchor:', anchor)
                        tag.attrib.pop(attr)
                    else:
                        seen.add(anchor)
