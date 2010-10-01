# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into RTF markup
'''

import os
import re
import cStringIO

from lxml import etree

from calibre.ebooks.oeb.base import XHTML, XHTML_NS, barename, namespace, \
    OEB_RASTER_IMAGES
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.ebooks.metadata import authors_to_string
from calibre.utils.filenames import ascii_text
from calibre.utils.magick.draw import save_cover_data_to, identify_data

TAGS = {
    'b': '\\b',
    'del': '\\deleted',
    'h1': '\\b \\par \\pard \\hyphpar',
    'h2': '\\b \\par \\pard \\hyphpar',
    'h3': '\\b \\par \\pard \\hyphpar',
    'h4': '\\b \\par \\pard \\hyphpar',
    'h5': '\\b \\par \\pard \\hyphpar',
    'h6': '\\b \\par \\pard \\hyphpar',
    'li': '\\par \\pard \\hyphpar \t',
    'p': '\\par \\pard \\hyphpar \t',
    'sub': '\\sub',
    'sup': '\\super',
    'u': '\\ul',
}

SINGLE_TAGS = {
    'br': '\n{\\line }\n',
    'div': '\n{\\line }\n',
}

SINGLE_TAGS_END = {
    'div': '\n{\\line }\n',
}

STYLES = [
    ('display', {'block': '\\par \\pard \\hyphpar'}),
    ('font-weight', {'bold': '\\b', 'bolder': '\\b'}),
    ('font-style', {'italic': '\\i'}),
    ('text-align', {'center': '\\qc', 'left': '\\ql', 'right': '\\qr'}),
    ('text-decoration', {'line-through': '\\strike', 'underline': '\\ul'}),
]

BLOCK_TAGS = [
    'p',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'li',
]

BLOCK_STYLES = [
    'block'
]

'''
TODO:
    * Tables
    * Fonts
'''

def txt2rtf(text):
    if not isinstance(text, unicode):
        return text
    buf = cStringIO.StringIO()
    for x in text:
        val = ord(x)
        if val <= 127:
            buf.write(x)
        else:
            repl = ascii_text(x)
            c = r'\uc{2}\u{0:d}{1}'.format(val, repl, len(repl))
            buf.write(c)
    return buf.getvalue()


class RTFMLizer(object):

    def __init__(self, log):
        self.log = log

    def extract_content(self, oeb_book, opts):
        self.log.info('Converting XHTML to RTF markup...')
        self.oeb_book = oeb_book
        self.opts = opts
        return self.mlize_spine()

    def mlize_spine(self):
        output = self.header()
        if 'titlepage' in self.oeb_book.guide:
            href = self.oeb_book.guide['titlepage'].href
            item = self.oeb_book.manifest.hrefs[href]
            if item.spine_position is None:
                stylizer = Stylizer(item.data, item.href, self.oeb_book,
                        self.opts, self.opts.output_profile)
                output += self.dump_text(item.data.find(XHTML('body')), stylizer)
                output += '{\\page } '
        for item in self.oeb_book.spine:
            self.log.debug('Converting %s to RTF markup...' % item.href)
            content = unicode(etree.tostring(item.data, encoding=unicode))
            content = self.remove_newlines(content)
            content = etree.fromstring(content)
            stylizer = Stylizer(content, item.href, self.oeb_book, self.opts, self.opts.output_profile)
            output += self.dump_text(content.find(XHTML('body')), stylizer)
        output += self.footer()
        output = self.insert_images(output)
        output = self.clean_text(output)

        return output

    def remove_newlines(self, text):
        self.log.debug('\tRemove newlines for processing...')
        text = text.replace('\r\n', ' ')
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')

        return text

    def header(self):
        return u'{\\rtf1{\\info{\\title %s}{\\author %s}}\\ansi\\ansicpg1252\\deff0\\deflang1033' % (self.oeb_book.metadata.title[0].value, authors_to_string([x.value for x in self.oeb_book.metadata.creator]))

    def footer(self):
        return ' }'

    def insert_images(self, text):
        for item in self.oeb_book.manifest:
            if item.media_type in OEB_RASTER_IMAGES:
                src = os.path.basename(item.href)
                data, width, height = self.image_to_hexstring(item.data)
                text = text.replace('SPECIAL_IMAGE-%s-REPLACE_ME' % src, '\n\n{\\*\\shppict{\\pict\\picw%i\\pich%i\\jpegblip \n%s\n}}\n\n' % (width, height, data))
        return text

    def image_to_hexstring(self, data):
        data = save_cover_data_to(data, 'cover.jpg', return_data=True)
        width, height = identify_data(data)[:2]

        raw_hex = ''
        for char in data:
            raw_hex += hex(ord(char)).replace('0x', '').rjust(2, '0')

        # Images must be broken up so that they are no longer than 129 chars
        # per line
        hex_string = ''
        col = 1
        for char in raw_hex:
            if col == 129:
                hex_string += '\n'
                col = 1
            col += 1
            hex_string += char

        return (hex_string, width, height)

    def clean_text(self, text):
        # Remove excess spaces at beginning and end of lines
        text = re.sub('(?m)^[ ]+', '', text)
        text = re.sub('(?m)[ ]+$', '', text)

        # Remove excessive newlines
        #text = re.sub('%s{1,1}' % os.linesep, '%s%s' % (os.linesep, os.linesep), text)
        text = re.sub('%s{3,}' % os.linesep, '%s%s' % (os.linesep, os.linesep), text)

        # Remove excessive spaces
        text = re.sub('[ ]{2,}', ' ', text)

        text = re.sub(r'(\{\\line \}\s*){3,}', r'{\\line }{\\line }', text)
        #text = re.compile(r'(\{\\line \}\s*)+(?P<brackets>}*)\s*\{\\par').sub(lambda mo: r'%s{\\par' % mo.group('brackets'), text)

        # Remove non-breaking spaces
        text = text.replace(u'\xa0', ' ')
        text = text.replace('\n\r', '\n')

        return text

    def dump_text(self, elem, stylizer, tag_stack=[]):
        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) != XHTML_NS:
            return u''

        text = u''
        style = stylizer.style(elem)

        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            return u''

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
            src = os.path.basename(elem.get('src'))
            block_start = ''
            block_end = ''
            if 'block' not in tag_stack:
                block_start = '{\\par \\pard \\hyphpar '
                block_end = '}'
            text += '%s SPECIAL_IMAGE-%s-REPLACE_ME %s' % (block_start, src, block_end)

        single_tag = SINGLE_TAGS.get(tag, None)
        if single_tag:
            text += single_tag

        rtf_tag = TAGS.get(tag, None)
        if rtf_tag and rtf_tag not in tag_stack:
            tag_count += 1
            text += '{%s\n' % rtf_tag
            tag_stack.append(rtf_tag)

        # Processes style information
        for s in STYLES:
            style_tag = s[1].get(style[s[0]], None)
            if style_tag and style_tag not in tag_stack:
                tag_count += 1
                text += '{%s\n' % style_tag
                tag_stack.append(style_tag)

        # Proccess tags that contain text.
        if hasattr(elem, 'text') and elem.text != None and elem.text.strip() != '':
            text += txt2rtf(elem.text)

        for item in elem:
            text += self.dump_text(item, stylizer, tag_stack)

        for i in range(0, tag_count):
            end_tag =  tag_stack.pop()
            if end_tag != 'block':
                text += u'}'

        single_tag_end = SINGLE_TAGS_END.get(tag, None)
        if single_tag_end:
            text += single_tag_end

        if hasattr(elem, 'tail') and elem.tail != None and elem.tail.strip() != '':
            if 'block' in tag_stack:
                text += '%s ' % txt2rtf(elem.tail)
            else:
                text += '{\\par \\pard \\hyphpar %s}' % txt2rtf(elem.tail)

        return text
