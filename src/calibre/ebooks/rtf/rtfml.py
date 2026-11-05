# License: GPLv3 Copyright: 2009, John Schember <john@nachtimwald.com>

"""
Transform OEB content into RTF markup
"""

import io
import os
import re
from binascii import hexlify
from typing import TYPE_CHECKING

from lxml import etree

from calibre.ebooks.metadata import authors_to_string
from calibre.utils.img import save_cover_data_to
from calibre.utils.imghdr import identify

if TYPE_CHECKING:
    from optparse import Values

    from lxml.etree import _Element

    from calibre.ebooks.oeb.base import OEBBook
    from calibre.ebooks.oeb.stylizer import Stylizer
    from calibre.utils.logging import Log

TAGS = {
    'b': '\\b',
    'del': '\\deleted',
    'h1': '\\s1 \\afs32',
    'h2': '\\s2 \\afs28',
    'h3': '\\s3 \\afs28',
    'h4': '\\s4 \\afs23',
    'h5': '\\s5 \\afs23',
    'h6': '\\s6 \\afs21',
    'i': '\\i',
    'li': '\t',
    'p': '\t',
    'sub': '\\sub',
    'sup': '\\super',
    'u': '\\ul',
}

SINGLE_TAGS = {
    'br': '\n{\\line }\n',
}

STYLES = [
    ('font-weight', {'bold': '\\b', 'bolder': '\\b'}),
    ('font-style', {'italic': '\\i'}),
    ('text-align', {'center': '\\qc', 'left': '\\ql', 'right': '\\qr'}),
    ('text-decoration', {'line-through': '\\strike', 'underline': '\\ul'}),
]

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
]

BLOCK_STYLES = ['block']

'''
TODO:
    * Tables
    * Fonts
'''


def txt2rtf(text: str) -> str:
    buf = io.StringIO()
    for x in text:
        val = ord(x)
        if x in '\\{}':
            buf.write('\\' + x)
        elif val == 160:
            buf.write(r'\~')
        elif val <= 127:
            buf.write(x)
        elif val <= 0xFFFF:
            # \u takes a signed 16-bit value, ? is the single (\uc1) fallback character
            buf.write(f'\\u{val - 0x10000 if val > 0x7FFF else val}?')
        else:
            # Characters outside the BMP are written as a UTF-16 surrogate pair
            val -= 0x10000
            buf.write(f'\\u{(0xD800 | (val >> 10)) - 0x10000}?\\u{(0xDC00 | (val & 0x3FF)) - 0x10000}?')
    return buf.getvalue()


class RTFMLizer:
    def __init__(self, log: Log) -> None:
        self.log = log

    def extract_content(self, oeb_book: OEBBook, opts: Values) -> str:
        self.log.info('Converting XHTML to RTF markup...')
        self.oeb_book = oeb_book
        self.opts = opts
        return self.mlize_spine()

    def mlize_spine(self) -> str:
        from calibre.ebooks.oeb.base import XHTML
        from calibre.ebooks.oeb.stylizer import Stylizer
        from calibre.utils.xml_parse import safe_xml_fromstring

        output = self.header()
        if 'titlepage' in self.oeb_book.guide:
            href = self.oeb_book.guide['titlepage'].href
            item = self.oeb_book.manifest.hrefs[href]
            if item.spine_position is None:
                root = item.data
                assert isinstance(root, etree._Element)  # the titlepage is an (X)HTML document
                stylizer = Stylizer(root, item.href, self.oeb_book, self.opts, self.opts.output_profile)
                self.currently_dumping_item = item
                body = root.find(XHTML('body'))
                assert body is not None
                output += self.dump_text(body, stylizer)
                output += r'{\page }'
        for item in self.oeb_book.spine:
            self.log.debug(f'Converting {item.href} to RTF markup...')
            # Removing comments is needed as comments with -- inside them can
            # cause fromstring() to fail
            root = item.data
            assert isinstance(root, etree._Element)  # spine items are parsed (X)HTML documents
            content = re.sub(r'<!--.*?-->', '', etree.tostring(root, encoding='unicode'), flags=re.DOTALL)
            content = self.remove_newlines(content)
            content = self.remove_tabs(content)
            content = safe_xml_fromstring(content)
            stylizer = Stylizer(content, item.href, self.oeb_book, self.opts, self.opts.output_profile)
            self.currently_dumping_item = item
            body = content.find(XHTML('body'))
            assert body is not None  # spine items always have a body, see parse_html()
            output += self.dump_text(body, stylizer)
            output += r'{\page }'
        output += self.footer()
        output = self.insert_images(output)
        output = self.clean_text(output)

        return output

    def remove_newlines(self, text: str) -> str:
        self.log.debug('\tRemove newlines for processing...')
        text = text.replace('\r\n', ' ')
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')

        return text

    def remove_tabs(self, text: str) -> str:
        self.log.debug('Replace tabs with space for processing...')
        text = text.replace('\t', ' ')

        return text

    def header(self) -> str:
        title = txt2rtf(self.oeb_book.metadata.title[0].value)
        author = txt2rtf(authors_to_string([x.value for x in self.oeb_book.metadata.creator]))
        header = f'{{\\rtf1\\ansi\\ansicpg1252\\uc1\\deff0\\deflang1033{{\\info{{\\title {title}}}{{\\author {author}}}}}\n'
        return header + (
            '{\\fonttbl{\\f0\\froman\\fprq2\\fcharset0 Times New Roman;}}\n'
            '{\\stylesheet{\\ql \\li0\\ri0\\nowidctlpar\\wrapdefault\\faauto\\rin0\\lin0\\itap0 \\rtlch\\fcs1 \\af0\\afs24\\alang1033 \\ltrch\\fcs0 \\fs24\\lang1033\\cgrid\\langnp1033 \\snext0 Normal;}\n'  # ruff: ignore[line-too-long]
            '{\\s1\\ql \\li0\\ri0\\sb240\\sa120\\keepn\\nowidctlpar\\wrapdefault\\faauto\\outlinelevel0\\rin0\\lin0\\itap0 \\rtlch\\fcs1 \\ab\\af0\\afs32\\alang1033 \\ltrch\\fcs0 \\b\\fs32\\lang1033\\cgrid\\langnp1033 \\sbasedon0 \\snext0 heading 1;}\n'  # ruff: ignore[line-too-long]
            '{\\s2\\ql \\li0\\ri0\\sb240\\sa120\\keepn\\nowidctlpar\\wrapdefault\\faauto\\outlinelevel1\\rin0\\lin0\\itap0 \\rtlch\\fcs1 \\ab\\ai\\af0\\afs28\\alang1033 \\ltrch\\fcs0 \\b\\i\\fs28\\lang1033\\cgrid\\langnp1033 \\sbasedon0 \\snext0 heading 2;}\n'  # ruff: ignore[line-too-long]
            '{\\s3\\ql \\li0\\ri0\\sb240\\sa120\\keepn\\nowidctlpar\\wrapdefault\\faauto\\outlinelevel2\\rin0\\lin0\\itap0 \\rtlch\\fcs1 \\ab\\af0\\afs28\\alang1033 \\ltrch\\fcs0 \\b\\fs28\\lang1033\\cgrid\\langnp1033 \\sbasedon0 \\snext0 heading 3;}\n'  # ruff: ignore[line-too-long]
            '{\\s4\\ql \\li0\\ri0\\sb240\\sa120\\keepn\\nowidctlpar\\wrapdefault\\faauto\\outlinelevel3\\rin0\\lin0\\itap0 \\rtlch\\fcs1 \\ab\\ai\\af0\\afs23\\alang1033 \\ltrch\\fcs0 \\b\\i\\fs23\\lang1033\\cgrid\\langnp1033 \\sbasedon0 \\snext0 heading 4;}\n'  # ruff: ignore[line-too-long]
            '{\\s5\\ql \\li0\\ri0\\sb240\\sa120\\keepn\\nowidctlpar\\wrapdefault\\faauto\\outlinelevel4\\rin0\\lin0\\itap0 \\rtlch\\fcs1 \\ab\\af0\\afs23\\alang1033 \\ltrch\\fcs0 \\b\\fs23\\lang1033\\cgrid\\langnp1033 \\sbasedon0 \\snext0 heading 5;}\n'  # ruff: ignore[line-too-long]
            '{\\s6\\ql \\li0\\ri0\\sb240\\sa120\\keepn\\nowidctlpar\\wrapdefault\\faauto\\outlinelevel5\\rin0\\lin0\\itap0 \\rtlch\\fcs1 \\ab\\af0\\afs21\\alang1033 \\ltrch\\fcs0 \\b\\fs21\\lang1033\\cgrid\\langnp1033 \\sbasedon0 \\snext0 heading 6;}}\n'  # ruff: ignore[line-too-long]
        )

    def footer(self) -> str:
        return ' }'

    def insert_images(self, text: str) -> str:
        from calibre.ebooks.oeb.base import OEB_RASTER_IMAGES

        for item in self.oeb_book.manifest:
            if item.media_type in OEB_RASTER_IMAGES:
                src = item.href
                try:
                    idata = item.data
                    assert isinstance(idata, bytes)  # raster images are unparsed bytes, errors are logged below
                    data, width, height = self.image_to_hexstring(idata)
                except Exception:
                    self.log.exception(f'Image {item.href} is corrupted, ignoring')
                    repl = '\n\n'
                else:
                    repl = '\n\n{\\*\\shppict{\\pict\\jpegblip\\picw%i\\pich%i \n%s\n}}\n\n' % (width, height, data)  # ruff: ignore[printf-string-formatting]
                text = text.replace(f'SPECIAL_IMAGE-{src}-REPLACE_ME', repl)
        return text

    def image_to_hexstring(self, data: bytes) -> tuple[str, int, int]:
        # Images must be hex-encoded in 128 character lines
        data = save_cover_data_to(data)
        width, height = identify(data)[1:]
        lines = []
        v = memoryview(data)
        for i in range(0, len(data), 64):
            lines.append(hexlify(v[i : i + 64]))
        hex_string = b'\n'.join(lines).decode('ascii')
        return hex_string, width, height

    def clean_text(self, text: str) -> str:
        # Remove excessive newlines
        text = re.sub(rf'{os.linesep}{{3,}}', f'{os.linesep}{os.linesep}', text)

        # Remove excessive spaces
        text = re.sub(r'[ ]{2,}', ' ', text)
        text = re.sub(r'\t{2,}', '\t', text)
        text = text.replace('\t ', '\t')

        # Remove excessive line breaks
        text = re.sub(r'(\{\\line \}\s*){3,}', r'{\\line }{\\line }', text)

        # Remove non-breaking spaces
        text = text.replace('\xa0', ' ')
        text = text.replace('\n\r', '\n')

        return text

    def dump_text(self, elem: _Element, stylizer: Stylizer, tag_stack: list[str] | None = None) -> str:
        from calibre.ebooks.oeb.base import XHTML_NS, barename, namespace, urlnormalize

        if tag_stack is None:
            tag_stack = []
        if not isinstance(elem.tag, str) or namespace(elem.tag) != XHTML_NS:
            p = elem.getparent()
            if p is not None and isinstance(p.tag, str) and namespace(p.tag) == XHTML_NS and elem.tail:
                return txt2rtf(elem.tail)
            return ''

        text = ''
        style = stylizer.style(elem)

        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') or style['visibility'] == 'hidden':
            if hasattr(elem, 'tail') and elem.tail:
                return txt2rtf(elem.tail)
            return ''

        tag = barename(elem.tag)
        tag_count = 0

        # Are we in a paragraph block?
        if tag in BLOCK_TAGS or style['display'] in BLOCK_STYLES:
            if 'block' not in tag_stack:
                tag_count += 1
                tag_stack.append('block')

        # Process tags that need special processing and that do not have inner
        # text. Usually these require an argument
        if tag == 'img':
            src = elem.get('src')
            if src:
                src = urlnormalize(self.currently_dumping_item.abshref(src))
                block_start = ''
                block_end = ''
                if 'block' not in tag_stack:
                    block_start = r'{\par\pard\hyphpar '
                    block_end = '}'
                text += f'{block_start} SPECIAL_IMAGE-{src}-REPLACE_ME {block_end}'

        single_tag = SINGLE_TAGS.get(tag, None)
        if single_tag:
            text += single_tag

        rtf_tag = TAGS.get(tag, None)
        if rtf_tag and rtf_tag not in tag_stack:
            tag_count += 1
            text += f'{{{rtf_tag}\n'
            tag_stack.append(rtf_tag)

        # Processes style information
        for s in STYLES:
            style_tag = s[1].get(style[s[0]], None)
            if style_tag and style_tag not in tag_stack:
                tag_count += 1
                text += f'{{{style_tag}\n'
                tag_stack.append(style_tag)

        # Process tags that contain text.
        if hasattr(elem, 'text') and elem.text:
            text += txt2rtf(elem.text)

        for item in elem:
            text += self.dump_text(item, stylizer, tag_stack)

        for i in range(tag_count):
            end_tag = tag_stack.pop()
            if end_tag != 'block':
                if tag in BLOCK_TAGS:
                    text += r'\par\pard\plain\hyphpar}'
                else:
                    text += '}'

        if hasattr(elem, 'tail') and elem.tail:
            if 'block' in tag_stack:
                text += f'{txt2rtf(elem.tail)}'
            else:
                text += rf'{{\par\pard\hyphpar {txt2rtf(elem.tail)}}}'

        return text
