#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid@kovidgoyal.net>

from typing import IO, TYPE_CHECKING

from calibre.customize.conversion import InputFormatPlugin
from calibre.utils.localization import _

if TYPE_CHECKING:
    from optparse import Values

    from calibre.ebooks.oeb.base import OEBBook
    from calibre.utils.logging import Log


class LITInput(InputFormatPlugin):
    name = 'LIT Input'
    author = 'Marshall T. Vandegrift'
    description = _('Convert LIT files to HTML')
    file_types = {'lit'}
    commit_name = 'lit_input'

    def convert(self, stream: IO[bytes], options: Values, file_ext: str, log: Log, accelerators: dict[str, str]) -> OEBBook:
        from calibre.ebooks.conversion.plumber import create_oebbook
        from calibre.ebooks.lit.reader import LitReader

        self.log = log
        return create_oebbook(log, stream, options, reader=LitReader)

    def postprocess_book(self, oeb: OEBBook, opts: Values, log: Log) -> None:
        from lxml import etree

        from calibre.ebooks.oeb.base import XHTML, XHTML_NS, XPath

        for item in oeb.spine:
            root = item.data
            if not isinstance(root, etree._Element):
                continue
            for bad in ('metadata', 'guide'):
                metadata = XPath('//h:' + bad)(root)
                if metadata:
                    for x in metadata:
                        x.getparent().remove(x)
            body = XPath('//h:body')(root)
            if body:
                body = body[0]
                if len(body) == 1 and body[0].tag == XHTML('pre'):
                    pre = body[0]
                    import copy

                    from calibre.ebooks.chardet import xml_to_unicode
                    from calibre.ebooks.txt.processor import convert_basic, separate_paragraphs_single_line
                    from calibre.utils.xml_parse import safe_xml_fromstring

                    self.log('LIT file with all text in single <pre> tag detected')
                    html = separate_paragraphs_single_line(pre.text)
                    html = convert_basic(html).replace('<html>', f'<html xmlns="{XHTML_NS}">')
                    html = xml_to_unicode(html, strip_encoding_pats=True, resolve_entities=True)[0]
                    if opts.smarten_punctuation:
                        # SmartyPants skips text inside <pre> tags
                        from calibre.ebooks.conversion.preprocess import smarten_punctuation

                        html = smarten_punctuation(html, self.log)
                    root = safe_xml_fromstring(html)
                    body = XPath('//h:body')(root)
                    pre.tag = XHTML('div')
                    pre.text = ''
                    for elem in body:
                        ne = copy.deepcopy(elem)
                        pre.append(ne)
