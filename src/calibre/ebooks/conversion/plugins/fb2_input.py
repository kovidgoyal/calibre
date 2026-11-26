# License: GPLv3 Copyright: 2008, Anatoly Shipitsin <norguhtar at gmail.com>

"""
Convert .fb2 files to .lrf
"""

import os
import re
from typing import IO, TYPE_CHECKING

from calibre import guess_type
from calibre.customize.conversion import InputFormatPlugin, OptionRecommendation
from calibre.utils.localization import _
from calibre.utils.resources import get_path as P

if TYPE_CHECKING:
    import unittest
    from optparse import Values

    from kgcss import Selector
    from lxml.etree import _Element

    from calibre.utils.logging import Log

FB2NS = 'http://www.gribuser.ru/xml/fictionbook/2.0'
FB21NS = 'http://www.gribuser.ru/xml/fictionbook/2.1'


def fb2_selector_to_html(selector: Selector) -> str:
    # FB2 <style name="x"> elements become <span class="x"> in the HTML
    from kgcss.selectors import AttributeSelector, TypeSelector

    text = selector.text
    edits: list[tuple[tuple[int, int], str]] = []
    for x in selector.walk():
        if isinstance(x, TypeSelector) and x.name == 'style':
            edits.append((x.span, 'span'))
        elif isinstance(x, AttributeSelector) and x.name == 'name' and x.operator == '=':
            start, end = x.span
            edits.append((x.span, re.sub(r'^\[\s*name', '[class', text[start:end])))
    for (start, end), repl in sorted(edits, reverse=True):
        text = text[:start] + repl + text[end:]
    return text


def fb2_css_to_html(css: str, log: Log | None = None) -> str:
    "The CSS of an FB2 file, for the HTML made from it"
    import logging

    from kgcss import RuleType, SelectorError, parse_stylesheet

    from calibre.ebooks.oeb.base import XHTML_NS

    # Type selectors match only XHTML elements
    sheet = parse_stylesheet(f'@namespace "{XHTML_NS}";\n' + css, log=logging.getLogger('calibre.css'))
    for rule in sheet.iter_rules(RuleType.STYLE):
        selectors: list[str] = []
        for selector in rule.selectors:
            try:
                selectors.append(fb2_selector_to_html(selector))
            except SelectorError as err:
                if log is not None:
                    log.warn(f'Ignoring invalid CSS selector in FB2 stylesheet: {selector.text!r} ({err})')
        if selectors:
            rule.selector_text = ', '.join(selectors)
        else:
            rule.selector_text = ':not(*)'  # matches nothing
    return sheet.css_text


class FB2Input(InputFormatPlugin):
    name = 'FB2 Input'
    author = 'Anatoly Shipitsin'
    description = _('Convert FB2 and FBZ files to HTML')
    file_types = {'fb2', 'fbz'}
    commit_name = 'fb2_input'

    recommendations = {
        ('level1_toc', '//h:h1', OptionRecommendation.MED),
        ('level2_toc', '//h:h2', OptionRecommendation.MED),
        ('level3_toc', '//h:h3', OptionRecommendation.MED),
    }

    options = {
        OptionRecommendation(
            name='no_inline_fb2_toc',
            recommended_value=False,
            level=OptionRecommendation.LOW,
            help=_('Do not insert a Table of Contents at the beginning of the book'),
        )
    }

    def convert(self, stream: IO[bytes], options: Values, file_ext: str, log: Log, accelerators: dict[str, str]) -> str:
        from lxml import etree

        from calibre.ebooks.chardet import xml_to_unicode
        from calibre.ebooks.metadata.fb2 import ensure_namespace, get_fb2_data
        from calibre.ebooks.metadata.meta import get_metadata
        from calibre.ebooks.metadata.opf2 import OPFCreator
        from calibre.ebooks.oeb.base import XLINK_NS
        from calibre.utils.xml_parse import safe_xml_fromstring

        self.log = log
        log.debug('Parsing XML...')
        raw = get_fb2_data(stream)[0]
        raw = raw.replace(b'\0', b'')
        raw = xml_to_unicode(raw, strip_encoding_pats=True, assume_utf8=True, resolve_entities=True)[0]
        try:
            doc = safe_xml_fromstring(raw)
        except etree.XMLSyntaxError:
            doc = safe_xml_fromstring(raw.replace('& ', '&amp;'))
        if doc is None:
            raise ValueError('The FB2 file is not valid XML')
        doc = ensure_namespace(doc)
        try:
            fb_ns = doc.nsmap[doc.prefix]
            if fb_ns not in (FB2NS, FB21NS):
                fb_ns = FB2NS
        except Exception:
            fb_ns = FB2NS

        NAMESPACES = {'f': fb_ns, 'l': XLINK_NS}
        stylesheets = doc.xpath('//*[local-name() = "stylesheet" and @type="text/css"]')
        css = ''
        for s in stylesheets:
            css += etree.tostring(s, encoding='unicode', method='text', with_tail=False) + '\n\n'
        if css:
            log.debug('Parsing stylesheet...')
            css = fb2_css_to_html(css, log)
        self.extract_embedded_content(doc)
        log.debug('Converting XML to HTML...')
        with open(P('templates/fb2.xsl'), 'rb') as f:
            ss = f.read().decode('utf-8')
        ss = ss.replace('__FB_NS__', fb_ns)
        if options.no_inline_fb2_toc:
            log('Disabling generation of inline FB2 TOC')
            ss = re.compile(r'<!-- BUILD TOC -->.*<!-- END BUILD TOC -->', re.DOTALL).sub('', ss)

        styledoc = safe_xml_fromstring(ss)

        transform = etree.XSLT(styledoc)
        result = transform(doc)

        # Handle links of type note and cite
        notes = {a.get('href')[1:]: a for a in result.xpath('//a[@link_note and @href]') if a.get('href').startswith('#')}
        cites = {a.get('link_cite'): a for a in result.xpath('//a[@link_cite]') if not a.get('href', '')}
        all_ids = set(result.xpath('//*/@id'))
        for cite, a in cites.items():
            note = notes.get(cite, None)
            if note:
                c = 1
                while f'cite{c}' in all_ids:
                    c += 1
                if not note.get('id', None):
                    note.set('id', f'cite{c}')
                    all_ids.add(note.get('id'))
                a.set('href', '#{}'.format(note.get('id')))
        for x in result.xpath('//*[@link_note or @link_cite]'):
            x.attrib.pop('link_note', None)
            x.attrib.pop('link_cite', None)

        for img in result.xpath('//img[@src]'):
            src = img.get('src')
            img.set('src', self.image_map.get(src, src))

        # make paragraphs <p> tags
        has_block_elements = etree.XPath('descendant::*[name()="div" or name()="table"]')
        for divp in result.xpath('//body/div[@class="paragraph"]'):
            if not has_block_elements(divp):
                divp.tag = 'p'

        index = str(result)
        with open('index.xhtml', 'wb') as f:
            f.write(index.encode('utf-8'))
        with open('inline-styles.css', 'wb') as f:
            f.write(css.encode('utf-8') or b' ')  # srv/render_book.py filters out empty files but index.xhtml links to this file
        stream.seek(0)
        mi = get_metadata(stream, 'fb2')
        if not mi.title:
            mi.title = _('Unknown')
        if not mi.authors:
            mi.authors = [_('Unknown')]
        cpath = None
        if mi.cover_data[1]:
            with open('fb2_cover_calibre_mi.jpg', 'wb') as f:
                f.write(mi.cover_data[1])
            cpath = os.path.abspath('fb2_cover_calibre_mi.jpg')
        else:
            for img in doc.xpath('//f:coverpage/f:image', namespaces=NAMESPACES):
                href = img.get(f'{{{XLINK_NS}}}href', img.get('href', None))
                if href is not None:
                    href = href.removeprefix('#')
                    cpath = os.path.abspath(href)
                    break

        opf = OPFCreator(os.getcwd(), mi)
        entries = [(f2, guess_type(f2)[0]) for f2 in os.listdir('.')]
        opf.create_manifest(entries)
        opf.create_spine(['index.xhtml'])
        if cpath:
            assert opf.guide is not None  # created by OPFCreator.__init__()
            opf.guide.set_cover(cpath)
        with open('metadata.opf', 'wb') as f:
            opf.render(f)
        return os.path.join(os.getcwd(), 'metadata.opf')

    def extract_embedded_content(self, doc: _Element) -> None:
        from calibre import guess_extension, sanitize_file_name
        from calibre.ebooks.fb2 import base64_decode

        self.image_map = {}
        for elem in doc.xpath('./*'):
            if elem.text and 'binary' in elem.tag and elem.get('id', ''):
                ct = elem.get('content-type', '').lower()
                fname = sanitize_file_name(elem.get('id'))
                if ct.startswith('image/'):
                    ext = guess_extension(ct)
                    if ext:
                        fname += ext
                        fname = sanitize_file_name(fname)
                        self.image_map[elem.get('id')] = fname
                raw = elem.text.strip()
                try:
                    data = base64_decode(raw)
                except TypeError:
                    self.log.exception('Binary data with id={} is corrupted, ignoring'.format(elem.get('id')))
                else:
                    with open(fname, 'wb') as f:
                        f.write(data)


def find_tests() -> unittest.TestSuite:
    import unittest

    class TestFB2CSS(unittest.TestCase):
        def test_fb2_css_to_html(self) -> None:
            from calibre.ebooks.oeb.base import XHTML_NS

            css = fb2_css_to_html('style[name="red"] { color: red }\np > style[ name = x ], .style #style p:not(style) { margin: 0 }\na[name~=x] { x: y }')
            self.assertEqual(
                css,
                f'@namespace url({XHTML_NS});\n'
                'span[class="red"] {\n  color: red;\n}\n'
                'p > span[class=x], .style #style p:not(span) {\n  margin: 0;\n}\n'
                'a[name~=x] {\n  x: y;\n}',
            )

    return unittest.defaultTestLoader.loadTestsFromTestCase(TestFB2CSS)
