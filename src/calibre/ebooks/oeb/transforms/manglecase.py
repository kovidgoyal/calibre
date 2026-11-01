# License: GPLv3 Copyright: 2008, Marshall T. Vandegrift <llasram@gmail.com>

"""
CSS case-mangling transform.
"""

from typing import TYPE_CHECKING, Self

from lxml import etree

from calibre.ebooks.oeb.base import CSS_MIME, XHTML, XHTML_NS, namespace
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.utils.icu import lower as icu_lower
from calibre.utils.icu import title_case as icu_title
from calibre.utils.icu import upper as icu_upper

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.oeb.base import OEBBook

CASE_MANGLER_CSS = '''
.calibre_lowercase {
    font-variant: normal;
    font-size: 0.65em;
}
'''

TEXT_TRANSFORMS = {'capitalize', 'uppercase', 'lowercase'}


class CaseMangler:
    @classmethod
    def config[T](cls, cfg: T) -> T:
        return cfg

    @classmethod
    def generate(cls, opts: Values) -> Self:
        return cls()

    def __call__(self, oeb: OEBBook, context: Values) -> None:
        oeb.logger.info('Applying case-transforming CSS...')
        self.oeb = oeb
        self.opts = context
        self.profile = context.source
        self.mangle_spine()

    def mangle_spine(self) -> None:
        id, href = self.oeb.manifest.generate('manglecase', 'manglecase.css')
        self.oeb.manifest.add(id, href, CSS_MIME, data=CASE_MANGLER_CSS)
        for item in self.oeb.spine:
            html = item.data
            assert isinstance(html, etree._Element)  # spine items are always (X)HTML documents
            relhref = item.relhref(href)
            head = html.find(XHTML('head'))
            assert head is not None  # parse_html() ensures there is a <head>
            etree.SubElement(head, XHTML('link'), rel='stylesheet', href=relhref, type=CSS_MIME)
            stylizer = Stylizer(html, item.href, self.oeb, self.opts, self.profile)
            body = html.find(XHTML('body'))
            assert body is not None  # parse_html() ensures there is a <body>
            self.mangle_elem(body, stylizer)

    def text_transform(self, transform: str, text: str) -> str:
        if transform == 'capitalize':
            return icu_title(text)
        elif transform == 'uppercase':
            return icu_upper(text)
        elif transform == 'lowercase':
            return icu_lower(text)
        return text

    def split_text(self, text: str) -> list[str]:
        results = ['']
        isupper = text[0].isupper()
        for char in text:
            if char.isupper() == isupper:
                results[-1] += char
            else:
                isupper = not isupper
                results.append(char)
        return results

    def smallcaps_elem(self, elem: etree._Element, attr: str) -> None:
        texts = self.split_text(getattr(elem, attr))
        setattr(elem, attr, None)
        last = elem if attr == 'tail' else None
        attrib = {'class': 'calibre_lowercase'}
        for text in texts:
            if text.isupper():
                if last is None:
                    elem.text = text
                else:
                    last.tail = text
            else:
                child = elem.makeelement(XHTML('span'), attrib=attrib)
                child.text = text.upper()
                if last is None:
                    elem.insert(0, child)
                else:
                    # addnext() moves the tail for some reason
                    tail = last.tail
                    last.addnext(child)
                    last.tail = tail
                    child.tail = None
                last = child

    def mangle_elem(self, elem: etree._Element, stylizer: Stylizer) -> None:
        tag = elem.tag
        if not isinstance(tag, str) or namespace(tag) != XHTML_NS:
            return
        children = list(elem)
        style = stylizer.style(elem)
        transform = style['text-transform']
        variant = style['font-variant']
        if elem.text:
            if isinstance(transform, str) and transform in TEXT_TRANSFORMS:
                elem.text = self.text_transform(transform, elem.text)
            if variant == 'small-caps':
                self.smallcaps_elem(elem, 'text')
        for child in children:
            self.mangle_elem(child, stylizer)
            if child.tail:
                if isinstance(transform, str) and transform in TEXT_TRANSFORMS:
                    child.tail = self.text_transform(transform, child.tail)
                if variant == 'small-caps':
                    self.smallcaps_elem(child, 'tail')
