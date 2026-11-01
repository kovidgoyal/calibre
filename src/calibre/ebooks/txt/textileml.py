# License: GPLv3 Copyright: 2011, Leigh Parry <leighparry@blueyonder.co.uk>

"""
Transform OEB content into Textile formatted plain text
"""

import re
from functools import partial
from typing import TYPE_CHECKING

from lxml import etree

from calibre.ebooks import unit_convert
from calibre.ebooks.htmlz.oeb2html import OEB2HTML
from calibre.ebooks.oeb.base import XHTML, XHTML_NS, barename, namespace, rewrite_links
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.ebooks.textile.unsmarten import unsmarten

if TYPE_CHECKING:
    from optparse import Values

    from lxml.etree import _Attrib, _Element

    from calibre.ebooks.oeb.base import Manifest, OEBBook
    from calibre.ebooks.oeb.stylizer import Style


class TextileMLizer(OEB2HTML):
    MAX_EM = 10

    def extract_content(self, oeb_book: OEBBook, opts: Values) -> str:
        self.log.info('Converting XHTML to Textile formatted TXT...')
        self.opts = opts
        self.in_pre = False
        self.in_table = False
        self.links = {}
        self.list = []
        self.our_links = []
        self.in_a_link = False
        self.our_ids = []
        self.images = {}
        self.id_no_text = ''
        self.style_embed = []
        self.remove_space_after_newline = False
        self.base_hrefs = [item.href for item in oeb_book.spine]
        self.map_resources(oeb_book)

        self.style_bold = False
        self.style_italic = False
        self.style_under = False
        self.style_strike = False
        self.style_smallcap = False

        txt = self.mlize_spine(oeb_book)
        if self.opts.unsmarten_punctuation:
            txt = unsmarten(txt)

        # Do some tidying up
        txt = self.tidy_up(txt)

        return txt

    def mlize_spine(self, oeb_book: OEBBook) -> str:
        output = ['']
        for item in oeb_book.spine:
            self.log.debug(f'Converting {item.href} to Textile formatted TXT...')
            root = item.data
            assert isinstance(root, etree._Element)  # spine items are parsed (X)HTML documents
            self.rewrite_ids(root, item)
            rewrite_links(root, partial(self.rewrite_link, page=item))
            stylizer = Stylizer(root, item.href, oeb_book, self.opts, self.opts.output_profile)
            body = root.find(XHTML('body'))
            assert body is not None
            output += self.dump_text(body, stylizer)
            output.append('\n\n')
        return ''.join(output)

    def tidy_up(self, text: str) -> str:
        # May need tweaking and finetuning
        def check_escaping(text: str, tests: list[str]) -> str:
            for t in tests:
                # I'm not checking for duplicated spans '%' as any that follow each other were being incorrectly merged
                txt = f'{t}'
                if txt != '%':
                    text = re.sub(r'([^' + t + '|^\n])' + t + r'\]\[' + t + '([^' + t + '])', r'\1\2', text)
                    text = re.sub(r'([^' + t + '|^\n])' + t + t + '([^' + t + '])', r'\1\2', text)
                text = re.sub(r'(\s|[*_\'"])\[(' + t + '[a-zA-Z0-9 \'",.*_]+' + t + r')\](\s|[*_\'"?!,.])', r'\1\2\3', text)
            return text

        # Now tidyup links and ids - remove ones that don't have a corresponding opposite
        if self.opts.keep_links:
            for i in self.our_links:
                if i[0] == '#':
                    if i not in self.our_ids:
                        text = re.sub(r'"(.+)":' + i + r'(\s)', r'\1\2', text)
            for i in self.our_ids:
                if i not in self.our_links:
                    text = re.sub(r'%?\(' + i + '\\)\xa0?%?', '', text)

        # Remove obvious non-needed escaping, add sub/sup-script ones
        text = check_escaping(text, [r'\*', '_', r'\*'])
        # escape the super/sub-scripts if needed
        text = re.sub(r'(\w)([~^]\w+[~^])', r'\1[\2]', text)
        # escape the super/sub-scripts if needed
        text = re.sub(r'([~^]\w+[~^])(\w)', r'[\1]\2', text)

        # remove empty spans
        text = re.sub(r'%\xa0+', r'%', text)
        # remove empty spans - MAY MERGE SOME ?
        text = text.replace('%%', '')
        # remove spans from tagged output
        text = re.sub(r'%([_+*-]+)%', r'\1', text)
        # remove spaces before a newline
        text = re.sub(r' +\n', r'\n', text)
        # remove newlines at top of file
        text = re.sub(r'^\n+', '', text)
        # correct blockcode paras
        text = re.sub(r'\npre\.\n?\nbc\.', r'\nbc.', text)
        # correct blockquote paras
        text = re.sub(r'\nbq\.\n?\np.*?\. ', r'\nbq. ', text)

        # reduce blank lines
        text = re.sub(r'\n{3}', r'\n\np. \n\n', text)
        text = re.sub(r'%\n(p[<>=]{1,2}\.|p\.)', r'%\n\n\1', text)
        # Check span following blank para
        text = re.sub(r'\n+ +%', r' %', text)
        text = re.sub(r'p[<>=]{1,2}\.\n\n?', '', text)
        # blank paragraph
        text = re.sub(r'\n(p.*\.)\n', r'\n\1 \n\n', text)
        # blank paragraph
        text = text.replace('\n\xa0', '\np. ')
        # blank paragraph
        text = re.sub(r'\np[<>=]{1,2}?\. \xa0', r'\np. ', text)
        text = re.sub(r'(^|\n)(p.*\. ?\n)(p.*\.)', r'\1\3', text)
        text = re.sub(r'\n(p\. \n)(p.*\.|h.*\.)', r'\n\2', text)
        # sort out spaces in tables
        text = re.sub(r' {2,}\|', r' |', text)

        # Now put back spaces removed earlier as they're needed here
        text = re.sub(r'\np\.\n', r'\np. \n', text)
        # reduce blank lines
        text = re.sub(r' \n\n\n', r' \n\n', text)

        return text

    def remove_newlines(self, text: str) -> str:
        text = text.replace('\r\n', ' ')
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')
        # Condense redundant spaces created by replacing newlines with spaces.
        text = re.sub(r'[ ]{2,}', ' ', text)
        text = re.sub(r'\t+', '', text)
        if self.remove_space_after_newline == True:  # ruff: ignore[true-false-comparison]
            text = re.sub(r'^ +', '', text)
            self.remove_space_after_newline = False
        return text

    def check_styles(self, style: Style) -> str:
        txt = '{'
        if self.opts.keep_color:
            if 'color' in style.cssdict() and style['color'] != 'black':
                color = style.color
                assert isinstance(color, str)  # a validated CSS color or the 'black' default
                txt += 'color:' + color + ';'
            if 'background' in style.cssdict():
                background = style['background']
                assert isinstance(background, str)  # concatenating a non-str would raise anyway
                txt += 'background:' + background + ';'
        txt += '}'
        if txt == '{}':
            txt = ''
        return txt

    def check_halign(self, style: Style) -> str:
        tests = {'left': '<', 'justify': '<>', 'center': '=', 'right': '>'}
        for i, v in tests.items():
            if style['text-align'] == i:
                return v
        return ''

    def check_valign(self, style: Style) -> str:
        tests = {'top': '^', 'bottom': '~'}  # , 'middle':'-'}
        for i, v in tests.items():
            if style['vertical-align'] == i:
                return v
        return ''

    def check_padding(self, style: Style, stylizer: Stylizer) -> str:
        txt = ''
        left_padding_pts = 0
        left_margin_pts = 0

        def add(x: float | str, y: float | str) -> float:
            if isinstance(x, str):
                x = 0
            if isinstance(y, str):
                y = 0
            return x + y

        if 'padding-left' in style.cssdict() and style['padding-left'] != 'auto':
            left_padding_pts = unit_convert(style.paddingLeft, style.width, style.fontSize, stylizer.profile.dpi)
        if 'margin-left' in style.cssdict() and style['margin-left'] != 'auto':
            left_margin_pts = unit_convert(style.marginLeft, style.width, style.fontSize, stylizer.profile.dpi)
        left = add(left_margin_pts, left_padding_pts)
        emleft = min(round(left / stylizer.profile.fbase), self.MAX_EM)
        if emleft >= 1:
            txt += '(' * emleft
        right_padding_pts = 0
        right_margin_pts = 0
        if 'padding-right' in style.cssdict() and style['padding-right'] != 'auto':
            right_padding_pts = unit_convert(style.paddingRight, style.width, style.fontSize, stylizer.profile.dpi)
        if 'margin-right' in style.cssdict() and style['margin-right'] != 'auto':
            right_margin_pts = unit_convert(style.marginRight, style.width, style.fontSize, stylizer.profile.dpi)
        right = add(right_margin_pts, right_padding_pts)
        emright = min(round(right / stylizer.profile.fbase), self.MAX_EM)
        if emright >= 1:
            txt += ')' * emright

        return txt

    def check_id_tag(self, attribs: _Attrib) -> str:
        txt = ''
        if 'id' in attribs:
            txt = '(#' + attribs['id'] + ')'
            self.our_ids.append('#' + attribs['id'])
            self.id_no_text = '\xa0'
        return txt

    def build_block(self, tag: str, style: Style, attribs: _Attrib, stylizer: Stylizer) -> str:
        txt = '\n' + tag
        if self.opts.keep_links:
            txt += self.check_id_tag(attribs)
        txt += self.check_padding(style, stylizer)
        txt += self.check_halign(style)
        txt += self.check_styles(style)
        return txt

    def prepare_string_for_textile(self, txt: str) -> str:
        if re.search(r'(\s([*&_+\-~@%|]|\?{2})\S)|(\S([*&_+\-~@%|]|\?{2})\s)', txt):
            return f' =={txt}== '
        return txt

    def dump_text(self, elem: _Element, stylizer: Stylizer, page: Manifest.Item | None = None) -> list[str]:
        """
        @elem: The element in the etree that we are working on.
        @stylizer: The style information attached to the element.
        """

        # We can only processes tags. If there isn't a tag return any text.
        if not isinstance(elem.tag, str) or namespace(elem.tag) != XHTML_NS:
            p = elem.getparent()
            if p is not None and isinstance(p.tag, str) and namespace(p.tag) == XHTML_NS and elem.tail:
                return [elem.tail]
            return ['']

        # Setup our variables.
        text = ['']
        style = stylizer.style(elem)
        tags = []
        tag = barename(elem.tag)
        attribs = elem.attrib

        # Ignore anything that is set to not be displayed.
        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') or style['visibility'] == 'hidden':
            if hasattr(elem, 'tail') and elem.tail:
                return [elem.tail]
            return ['']

        # Soft scene breaks.
        if 'margin-top' in style.cssdict() and style['margin-top'] != 'auto':
            ems = min(int(round(float(style.marginTop) / style.fontSize) - 1), self.MAX_EM)
            if ems >= 1:
                text.append('\n\n\xa0' * ems)

        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div'):
            if tag == 'div':
                tag = 'p'
            text.append(self.build_block(tag, style, attribs, stylizer))
            text.append('. ')
            tags.append('\n')

        if style['font-style'] == 'italic' or tag in ('i', 'em'):
            if tag not in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'cite'):
                if self.style_italic == False:  # ruff: ignore[true-false-comparison]
                    if self.in_a_link:
                        text.append('_')
                        tags.append('_')
                    else:
                        text.append('[_')
                        tags.append('_]')
                    self.style_embed.append('_')
                    self.style_italic = True
        if style['font-weight'] in ('bold', 'bolder') or tag in ('b', 'strong'):
            if tag not in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'th'):
                if self.style_bold == False:  # ruff: ignore[true-false-comparison]
                    if self.in_a_link:
                        text.append('*')
                        tags.append('*')
                    else:
                        text.append('[*')
                        tags.append('*]')
                    self.style_embed.append('*')
                    self.style_bold = True
        if style['text-decoration'] == 'underline' or tag in ('u', 'ins'):
            if tag != 'a':
                if self.style_under == False:  # ruff: ignore[true-false-comparison]
                    text.append('[+')
                    tags.append('+]')
                    self.style_embed.append('+')
                    self.style_under = True
        if style['text-decoration'] == 'line-through' or tag in ('strike', 'del', 's'):
            if self.style_strike == False:  # ruff: ignore[true-false-comparison]
                text.append('[-')
                tags.append('-]')
                self.style_embed.append('-')
                self.style_strike = True
        if tag == 'br':
            text.extend(reversed(self.style_embed))
            text.append('\n')
            text.extend(self.style_embed)
            tags.append('')
            self.remove_space_after_newline = True
        if tag == 'blockquote':
            text.append('\nbq. ')
            tags.append('\n')
        elif tag in ('abbr', 'acronym'):
            text.append('')
            txt = attribs['title']
            tags.append('(' + txt + ')')
        elif tag == 'sup':
            text.append('^')
            tags.append('^')
        elif tag == 'sub':
            text.append('~')
            tags.append('~')
        elif tag == 'code':
            if self.in_pre:
                text.append('\nbc. ')
                tags.append('')
            else:
                text.append('@')
                tags.append('@')
        elif tag == 'cite':
            text.append('??')
            tags.append('??')
        elif tag == 'hr':
            text.append('\n***')
            tags.append('\n')
        elif tag == 'pre':
            self.in_pre = True
            text.append('\npre. ')
            tags.append('pre\n')
        elif tag == 'a':
            if self.opts.keep_links:
                if 'href' in attribs:
                    text.append('"')
                    tags.append('a')
                    tags.append('":' + attribs['href'])
                    self.our_links.append(attribs['href'])
                    if 'title' in attribs:
                        tags.append('(' + attribs['title'] + ')')
                    self.in_a_link = True
                else:
                    text.append('%')
                    tags.append('%')
        elif tag == 'img':
            if self.opts.keep_image_references:
                txt = '!' + self.check_halign(style)
                txt += self.check_valign(style)
                txt += attribs['src']
                text.append(txt)
                if 'alt' in attribs:
                    txt = attribs['alt']
                    if txt != '':
                        text.append('(' + txt + ')')
                tags.append('!')
            elif self.opts.use_alt_text_for_images:
                if alt := attribs.get('alt'):
                    txt = '!' + self.check_halign(style)
                    txt += self.check_valign(style)
                    txt += '(' + alt + ')'
                    text.append(txt)
                    tags.append('!')
        elif tag in ('ol', 'ul'):
            self.list.append({'name': tag, 'num': 0})
            text.append('')
            tags.append(tag)
        elif tag == 'li':
            if self.list:
                li = self.list[-1]
            else:
                li = {'name': 'ul', 'num': 0}
            text.append('\n')
            if li['name'] == 'ul':
                text.append('*' * len(self.list) + ' ')
            elif li['name'] == 'ol':
                text.append('#' * len(self.list) + ' ')
            tags.append('')
        elif tag == 'dl':
            text.append('\n')
            tags.append('')
        elif tag == 'dt':
            text.append('')
            tags.append('\n')
        elif tag == 'dd':
            text.append('    ')
            tags.append('')
        elif tag == 'dd':
            text.append('')
            tags.append('\n')
        elif tag == 'table':
            txt = self.build_block(tag, style, attribs, stylizer)
            txt += '. \n'
            if txt != '\ntable. \n':
                text.append(txt)
            else:
                text.append('\n')
            tags.append('')
        elif tag == 'tr':
            txt = self.build_block('', style, attribs, stylizer)
            txt += '. '
            if txt != '\n. ':
                txt = txt.replace('\n', '')
                text.append(txt)
            tags.append('|\n')
        elif tag == 'td':
            text.append('|')
            txt = ''
            txt += self.check_halign(style)
            txt += self.check_valign(style)
            if 'colspan' in attribs:
                txt += '\\' + attribs['colspan']
            if 'rowspan' in attribs:
                txt += '/' + attribs['rowspan']
            txt += self.check_styles(style)
            if txt != '':
                text.append(txt + '. ')
            tags.append('')
        elif tag == 'th':
            text.append('|_. ')
            tags.append('')
        elif tag == 'span':
            if style['font-variant'] == 'small-caps':
                if self.style_smallcap == False:  # ruff: ignore[true-false-comparison]
                    text.append('&')
                    tags.append('&')
                    self.style_smallcap = True
            elif self.in_a_link == False:  # ruff: ignore[true-false-comparison]
                txt = '%'
                if self.opts.keep_links:
                    txt += self.check_id_tag(attribs)
                    txt += self.check_styles(style)
                if txt != '%':
                    text.append(txt)
                    tags.append('%')

        if self.opts.keep_links and 'id' in attribs:
            if tag not in ('body', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'table'):
                text.append(self.check_id_tag(attribs))

        # Process the styles for any that we want to keep
        if tag not in (
            'body',
            'div',
            'h1',
            'h2',
            'h3',
            'h4',
            'h5',
            'h6',
            'p',
            'hr',
            'a',
            'img',
            'span',
            'table',
            'tr',
            'td',
        ):
            if not self.in_a_link:
                text.append(self.check_styles(style))

        # Process tags that contain text.
        if hasattr(elem, 'text') and elem.text:
            txt = elem.text
            if not self.in_pre:
                txt = self.prepare_string_for_textile(self.remove_newlines(txt))
            text.append(txt)
            self.id_no_text = ''

        # Recurse down into tags within the tag we are in.
        for item in elem:
            text += self.dump_text(item, stylizer)

        # Close all open tags.
        tags.reverse()
        for t in tags:
            if t in ('pre', 'ul', 'ol', 'li', 'table'):
                if t == 'pre':
                    self.in_pre = False
                elif t in ('ul', 'ol'):
                    if self.list:
                        self.list.pop()
                    if not self.list:
                        text.append('\n')
            else:
                if t == 'a':
                    self.in_a_link = False
                    t = ''
                text.append(self.id_no_text)
                self.id_no_text = ''
                if t in ('*]', '*'):
                    self.style_bold = False
                elif t in ('_]', '_'):
                    self.style_italic = False
                elif t == '+]':
                    self.style_under = False
                elif t == '-]':
                    self.style_strike = False
                elif t == '&':
                    self.style_smallcap = False
                if t in ('*]', '_]', '+]', '-]', '*', '_'):
                    txt = self.style_embed.pop()
                text.append(f'{t}')

        # Soft scene breaks.
        if 'margin-bottom' in style.cssdict() and style['margin-bottom'] != 'auto':
            ems = min(round((float(style.marginBottom) / style.fontSize) - 1), self.MAX_EM)
            if ems >= 1:
                text.append('\n\n\xa0' * ems)

        # Add the text that is outside of the tag.
        if hasattr(elem, 'tail') and elem.tail:
            tail = elem.tail
            if not self.in_pre:
                tail = self.prepare_string_for_textile(self.remove_newlines(tail))
            text.append(tail)

        return text
