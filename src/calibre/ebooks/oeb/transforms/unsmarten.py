# License: GPLv3 Copyright: 2011, John Schember <john@nachtimwald.com>

from typing import TYPE_CHECKING

from lxml import etree

from calibre.ebooks.oeb.base import OEB_DOCS, XPath, barename
from calibre.utils.unsmarten import unsmarten_text

if TYPE_CHECKING:
    from optparse import Values

    from lxml.etree import _Element

    from calibre.ebooks.conversion.plumber import OptionValues
    from calibre.ebooks.oeb.base import OEBBook


class UnsmartenPunctuation:
    def __init__(self) -> None:
        self.html_tags = XPath('descendant::h:*')

    def unsmarten(self, root: _Element) -> None:
        for x in self.html_tags(root):
            if barename(x.tag) != 'pre':
                if getattr(x, 'text', None):
                    x.text = unsmarten_text(x.text)
                if getattr(x, 'tail', None) and x.tail:
                    x.tail = unsmarten_text(x.tail)

    def __call__(self, oeb: OEBBook, context: Values | OptionValues) -> None:
        bx = XPath('//h:body')
        for x in oeb.manifest.items:
            if x.media_type in OEB_DOCS:
                root = x.data
                assert isinstance(root, etree._Element)  # media_type is in OEB_DOCS
                for body in bx(root):
                    self.unsmarten(body)
