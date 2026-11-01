# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

"""
Transform OEB content into plain text
"""

import re
from typing import TYPE_CHECKING

from lxml import etree

from calibre.utils.localization import _

if TYPE_CHECKING:
    import unittest
    from collections.abc import Iterable
    from optparse import Values

    from lxml.etree import _Element

    from calibre.ebooks.oeb.base import TOC, Manifest, OEBBook
    from calibre.ebooks.oeb.stylizer import Stylizer
    from calibre.utils.logging import Log

BLOCK_TAGS = [
    'div',
    'p',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'li',
    'tr',
]

BLOCK_STYLES = [
    'block',
]

HEADING_TAGS = [
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
]

SPACE_TAGS = [
    'td',
    'br',
]


class TXTMLizer:
    def __init__(self, log: Log) -> None:
        self.log = log

    def extract_content(self, oeb_book: OEBBook, opts: Values) -> str:
        self.log.info('Converting XHTML to TXT...')
        self.oeb_book = oeb_book
        self.opts = opts
        self.toc_titles = []
        self.toc_ids = []
        self.last_was_heading = False

        self.create_flat_toc(self.oeb_book.toc)

        return self.mlize_spine()

    def mlize_spine(self) -> str:
        from calibre.ebooks.oeb.base import XHTML
        from calibre.ebooks.oeb.stylizer import Stylizer
        from calibre.utils.xml_parse import safe_xml_fromstring

        output = ['']
        output.append(self.get_toc())
        for item in self.oeb_book.spine:
            self.log.debug(f'Converting {item.href} to TXT...')
            root = item.data
            assert isinstance(root, etree._Element)  # spine items are parsed (X)HTML documents
            for x in root.iterdescendants(etree.Comment):
                if x.text and '--' in x.text:
                    x.text = x.text.replace('--', '__')
            content = etree.tostring(root, encoding='unicode')
            content = self.remove_newlines(content)
            content = safe_xml_fromstring(content)
            stylizer = Stylizer(content, item.href, self.oeb_book, self.opts, self.opts.output_profile)
            body = content.find(XHTML('body'))
            assert body is not None  # spine items always have a body, see parse_html()
            output += self.dump_text(body, stylizer, item)
            output += '\n\n\n\n\n\n'
        output = ''.join(output)
        output = '\n'.join(l.rstrip() for l in output.splitlines())
        output = self.cleanup_text(output)

        return output

    def remove_newlines(self, text: str) -> str:
        self.log.debug('\tRemove newlines for processing...')
        text = text.replace('\r\n', ' ')
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')
        # Condense redundant spaces created by replacing newlines with spaces.
        text = re.sub(r'[ ]{2,}', ' ', text)

        return text

    def get_toc(self) -> str:
        toc = ['']
        if getattr(self.opts, 'inline_toc', None):
            self.log.debug('Generating table of contents...')
            toc.append('{}\n\n'.format(_('Table of Contents:')))
            unihandecoder = None
            if getattr(self.opts, 'asciiize', False):
                from calibre.utils.localization import get_udc

                unihandecoder = get_udc()
            for item in self.toc_titles:
                if unihandecoder is not None:
                    item = unihandecoder.decode(item)
                toc.append(f'* {item}\n\n')
        return ''.join(toc)

    def create_flat_toc(self, nodes: Iterable[TOC]) -> None:
        """
        Turns a hierarchical list of TOC href's into a flat list.
        """
        for item in nodes:
            self.toc_titles.append(item.title)
            self.toc_ids.append(item.href)
            self.create_flat_toc(item.nodes)

    def cleanup_text(self, text: str) -> str:
        self.log.debug('\tClean up text...')
        # Replace bad characters.
        text = text.replace('\xa0', ' ')

        # Replace tabs, vertical tags and form feeds with single space.
        text = text.replace('\t+', ' ')
        text = text.replace('\v+', ' ')
        text = text.replace('\f+', ' ')

        # Single line paragraph.
        text = re.sub(r'(?<=.)\n(?=.)', ' ', text)

        # Remove multiple spaces.
        text = re.sub(r'[ ]{2,}', ' ', text)

        # Remove excessive newlines.
        text = re.sub(r'\n[ ]+\n', '\n\n', text)
        if self.opts.remove_paragraph_spacing:
            text = re.sub(r'\n{2,}', '\n', text)
            text = re.sub(r'(?msu)^(?P<t>[^\t\n]+?)$', lambda mo: '{}\n\n'.format(mo.group('t')), text)
            text = re.sub(
                r'(?msu)(?P<b>[^\n])\n+(?P<t>[^\t\n]+?)(?=\n)',
                lambda mo: '{}\n\n\n\n\n\n{}'.format(mo.group('b'), mo.group('t')),
                text,
            )
        else:
            text = re.sub(r'\n{7,}', '\n\n\n\n\n\n', text)

        # Replace spaces at the beginning and end of lines
        # We don't replace tabs because those are only added
        # when remove paragraph spacing is enabled.
        text = re.sub(r'(?imu)^[ ]+', '', text)
        text = re.sub(r'(?imu)[ ]+$', '', text)

        # Remove empty space and newlines at the beginning of the document.
        text = re.sub(r'(?u)^[ \n]+', '', text)

        if self.opts.max_line_length:
            max_length = int(self.opts.max_line_length)
            if max_length < 25 and not self.opts.force_max_line_length:
                max_length = 25
            short_lines = []
            lines = text.splitlines()
            for line in lines:
                while len(line) > max_length:
                    space = line.rfind(' ', 0, max_length)
                    if space != -1:
                        # Space was found.
                        short_lines.append(line[:space])
                        line = line[space + 1 :]
                    # Space was not found.
                    elif self.opts.force_max_line_length:
                        # Force breaking at max_lenght.
                        short_lines.append(line[:max_length])
                        line = line[max_length:]
                    else:
                        # Look for the first space after max_length.
                        space = line.find(' ', max_length, len(line))
                        if space != -1:
                            # Space was found.
                            short_lines.append(line[:space])
                            line = line[space + 1 :]
                        else:
                            # No space was found cannot break line.
                            short_lines.append(line)
                            line = ''
                # Add the text that was less than max_lengh to the list
                short_lines.append(line)
            text = '\n'.join(short_lines)

        return text

    def is_block(self, elem: _Element, stylizer: Stylizer) -> bool:
        from calibre.ebooks.oeb.base import XHTML_NS, barename, namespace

        if not isinstance(elem.tag, str) or namespace(elem.tag) != XHTML_NS:
            return False
        return barename(elem.tag) in BLOCK_TAGS or stylizer.style(elem)['display'] in BLOCK_STYLES

    def needs_block_separator(self, text: list[str]) -> bool:
        # True if the text output so far ends with non-whitespace content
        # that is not already terminated by a newline
        for chunk in reversed(text):
            stripped = chunk.rstrip(' \t')
            if stripped:
                return not stripped.endswith('\n')
        return False

    def dump_text(self, elem: _Element, stylizer: Stylizer, page: Manifest.Item) -> list[str]:
        """
        @elem: The element in the etree that we are working on.
        @stylizer: The style information attached to the element.
        @page: OEB page used to determine absolute urls.
        """
        from calibre.ebooks.oeb.base import XHTML_NS, barename, namespace

        if not isinstance(elem.tag, str) or namespace(elem.tag) != XHTML_NS:
            p = elem.getparent()
            if p is not None and isinstance(p.tag, str) and namespace(p.tag) == XHTML_NS and elem.tail:
                return [elem.tail]
            return ['']

        text = ['']
        style = stylizer.style(elem)

        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') or style['visibility'] == 'hidden':
            if hasattr(elem, 'tail') and elem.tail:
                return [elem.tail]
            return ['']

        tag = barename(elem.tag)
        tag_id = elem.attrib.get('id', None)
        in_block = False
        in_heading = False

        # Are we in a heading?
        # This can either be a heading tag or a TOC item.
        if tag in HEADING_TAGS or f'{page.href}#{tag_id}' in self.toc_ids:
            in_heading = True
            if not self.last_was_heading:
                text.append('\n\n\n\n\n\n')

        # Are we in a paragraph block?
        if tag in BLOCK_TAGS or style['display'] in BLOCK_STYLES:
            if self.opts.remove_paragraph_spacing and not in_heading:
                text.append('\t')
            in_block = True

        if tag in SPACE_TAGS:
            text.append(' ')

        # Hard scene breaks.
        if tag == 'hr':
            text.append('\n\n* * *\n\n')
        # Soft scene breaks.
        try:
            ems = round((float(style.marginTop) / style.fontSize) - 1)
            if ems >= 1:
                text.append('\n' * ems)
        except Exception:
            pass

        if self.opts.use_alt_text_for_images and tag == 'img' and (alt := elem.get('alt')):
            text.append(_('[Image: {}]').format(alt))
        # Process tags that contain text.
        if hasattr(elem, 'text') and elem.text:
            text.append(elem.text)

        # Recurse down into tags within the tag we are in.
        for item in elem:
            if self.is_block(item, stylizer) and self.needs_block_separator(text):
                # A block nested after inline content, for example:
                # <li>foo<ul><li>bar</li></ul></li> must start on a new line
                text.append('\n\n')
            text += self.dump_text(item, stylizer, page)

        if in_block:
            text.append('\n\n')
        if in_heading:
            text.append('\n')
            self.last_was_heading = True
        else:
            self.last_was_heading = False

        if hasattr(elem, 'tail') and elem.tail:
            text.append(elem.tail)

        return text


def find_tests() -> unittest.TestSuite:
    import unittest
    from pathlib import Path
    from tempfile import TemporaryDirectory

    from calibre.ebooks.conversion.plumber import Plumber
    from calibre.utils.logging import DevNull

    def convert(html: str, *recommendations: tuple[str, object, int]) -> str:
        with TemporaryDirectory() as tdir:
            src, dest = Path(tdir) / 'input.html', Path(tdir) / 'output.txt'
            src.write_text(html, encoding='utf-8')
            plumber = Plumber(str(src), str(dest), DevNull())
            plumber.merge_ui_recommendations(list(recommendations))
            plumber.run()
            return dest.read_text(encoding='utf-8')

    class TXTOutputTest(unittest.TestCase):
        def test_txt_nested_block_after_text(self) -> None:
            html = '<html><body><ul><li>foo<ul><li>bar</li></ul></li><li>baz</li></ul><div>x<span>y</span><div>z</div></div></body></html>'
            lines = [l for l in convert(html).splitlines() if l.strip()]
            self.assertEqual(lines, ['foo', 'bar', 'baz', 'xy', 'z'])
            lines = [l.strip() for l in convert(html, ('remove_paragraph_spacing', True, 3)).splitlines() if l.strip()]
            self.assertEqual(lines, ['foo', 'bar', 'baz', 'xy', 'z'])

    return unittest.defaultTestLoader.loadTestsFromTestCase(TXTOutputTest)
