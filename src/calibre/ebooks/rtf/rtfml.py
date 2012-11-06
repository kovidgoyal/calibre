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

from calibre.ebooks.metadata import authors_to_string
from calibre.utils.magick.draw import save_cover_data_to, identify_data

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

BLOCK_STYLES = [
    'block'
]

'''
TODO:
    * Tables
    * Fonts
'''

def txt2rtf(text):
    # Escape { and } in the text.
    text = text.replace('{', r'\'7b')
    text = text.replace('}', r'\'7d')

    if not isinstance(text, unicode):
        return text

    buf = cStringIO.StringIO()
    for x in text:
        val = ord(x)
        if val == 160:
            buf.write('\\~')
        elif val <= 127:
            buf.write(x)
        else:
            c = r'\u{0:d}?'.format(val)
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
        from calibre.ebooks.oeb.base import XHTML
        from calibre.ebooks.oeb.stylizer import Stylizer
        output = self.header()
        if 'titlepage' in self.oeb_book.guide:
            href = self.oeb_book.guide['titlepage'].href
            item = self.oeb_book.manifest.hrefs[href]
            if item.spine_position is None:
                stylizer = Stylizer(item.data, item.href, self.oeb_book,
                        self.opts, self.opts.output_profile)
                self.currently_dumping_item = item
                output += self.dump_text(item.data.find(XHTML('body')), stylizer)
                output += '{\\page }'
        for item in self.oeb_book.spine:
            self.log.debug('Converting %s to RTF markup...' % item.href)
            content = unicode(etree.tostring(item.data, encoding=unicode))
            content = self.remove_newlines(content)
            content = self.remove_tabs(content)
            content = etree.fromstring(content)
            stylizer = Stylizer(content, item.href, self.oeb_book, self.opts, self.opts.output_profile)
            self.currently_dumping_item = item
            output += self.dump_text(content.find(XHTML('body')), stylizer)
            output += '{\\page }'
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

    def remove_tabs(self, text):
        self.log.debug('\Replace tabs with space for processing...')
        text = text.replace('\t', ' ')

        return text

    def header(self):
        header = u'{\\rtf1{\\info{\\title %s}{\\author %s}}\\ansi\\ansicpg1252\\deff0\\deflang1033\n' % (self.oeb_book.metadata.title[0].value, authors_to_string([x.value for x in self.oeb_book.metadata.creator]))
        return header + \
            '{\\fonttbl{\\f0\\froman\\fprq2\\fcharset128 Times New Roman;}{\\f1\\froman\\fprq2\\fcharset128 Times New Roman;}{\\f2\\fswiss\\fprq2\\fcharset128 Arial;}{\\f3\\fnil\\fprq2\\fcharset128 Arial;}{\\f4\\fnil\\fprq2\\fcharset128 MS Mincho;}{\\f5\\fnil\\fprq2\\fcharset128 Tahoma;}{\\f6\\fnil\\fprq0\\fcharset128 Tahoma;}}\n' \
            '{\\stylesheet{\\ql \\li0\\ri0\\nowidctlpar\\wrapdefault\\faauto\\rin0\\lin0\\itap0 \\rtlch\\fcs1 \\af25\\afs24\\alang1033 \\ltrch\\fcs0 \\fs24\\lang1033\\langfe255\\cgrid\\langnp1033\\langfenp255 \\snext0 Normal;}\n' \
            '{\\s1\\ql \\li0\\ri0\\sb240\\sa120\\keepn\\nowidctlpar\\wrapdefault\\faauto\\outlinelevel0\\rin0\\lin0\\itap0 \\rtlch\\fcs1 \\ab\\af0\\afs32\\alang1033 \\ltrch\\fcs0 \\b\\fs32\\lang1033\\langfe255\\loch\\f1\\hich\\af1\\dbch\\af26\\cgrid\\langnp1033\\langfenp255 \\sbasedon15 \\snext16 \\slink21 heading 1;}\n' \
            '{\\s2\\ql \\li0\\ri0\\sb240\\sa120\\keepn\\nowidctlpar\\wrapdefault\\faauto\\outlinelevel1\\rin0\\lin0\\itap0 \\rtlch\\fcs1 \\ab\\ai\\af0\\afs28\\alang1033 \\ltrch\\fcs0 \\b\\i\\fs28\\lang1033\\langfe255\\loch\\f1\\hich\\af1\\dbch\\af26\\cgrid\\langnp1033\\langfenp255 \\sbasedon15 \\snext16 \\slink22 heading 2;}\n' \
            '{\\s3\\ql \\li0\\ri0\\sb240\\sa120\\keepn\\nowidctlpar\\wrapdefault\\faauto\\outlinelevel2\\rin0\\lin0\\itap0 \\rtlch\\fcs1 \\ab\\af0\\afs28\\alang1033 \\ltrch\\fcs0 \\b\\fs28\\lang1033\\langfe255\\loch\\f1\\hich\\af1\\dbch\\af26\\cgrid\\langnp1033\\langfenp255 \\sbasedon15 \\snext16 \\slink23 heading 3;}\n' \
            '{\\s4\\ql \\li0\\ri0\\sb240\\sa120\\keepn\\nowidctlpar\\wrapdefault\\faauto\\outlinelevel3\\rin0\\lin0\\itap0 \\rtlch\\fcs1 \\ab\\ai\\af0\\afs23\\alang1033 \\ltrch\\fcs0\\b\\i\\fs23\\lang1033\\langfe255\\loch\\f1\\hich\\af1\\dbch\\af26\\cgrid\\langnp1033\\langfenp255 \\sbasedon15 \\snext16 \\slink24 heading 4;}\n' \
            '{\\s5\\ql \\li0\\ri0\\sb240\\sa120\\keepn\\nowidctlpar\\wrapdefault\\faauto\\outlinelevel4\\rin0\\lin0\\itap0 \\rtlch\\fcs1 \\ab\\af0\\afs23\\alang1033 \\ltrch\\fcs0 \\b\\fs23\\lang1033\\langfe255\\loch\\f1\\hich\\af1\\dbch\\af26\\cgrid\\langnp1033\\langfenp255 \\sbasedon15 \\snext16 \\slink25 heading 5;}\n' \
            '{\\s6\\ql \\li0\\ri0\\sb240\\sa120\\keepn\\nowidctlpar\\wrapdefault\\faauto\\outlinelevel5\\rin0\\lin0\\itap0 \\rtlch\\fcs1 \\ab\\af0\\afs21\\alang1033 \\ltrch\\fcs0 \\b\\fs21\\lang1033\\langfe255\\loch\\f1\\hich\\af1\\dbch\\af26\\cgrid\\langnp1033\\langfenp255 \\sbasedon15 \\snext16 \\slink26 heading 6;}}\n'

    def footer(self):
        return ' }'

    def insert_images(self, text):
        from calibre.ebooks.oeb.base import OEB_RASTER_IMAGES

        for item in self.oeb_book.manifest:
            if item.media_type in OEB_RASTER_IMAGES:
                src = item.href
                try:
                    data, width, height = self.image_to_hexstring(item.data)
                except:
                    self.log.warn('Image %s is corrupted, ignoring'%item.href)
                    repl = '\n\n'
                else:
                    repl = '\n\n{\\*\\shppict{\\pict\\jpegblip\\picw%i\\pich%i \n%s\n}}\n\n' % (width, height, data)
                text = text.replace('SPECIAL_IMAGE-%s-REPLACE_ME' % src, repl)
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
        # Remove excessive newlines
        text = re.sub('%s{3,}' % os.linesep, '%s%s' % (os.linesep, os.linesep), text)

        # Remove excessive spaces
        text = re.sub('[ ]{2,}', ' ', text)
        text = re.sub('\t{2,}', '\t', text)
        text = re.sub('\t ', '\t', text)

        # Remove excessive line breaks
        text = re.sub(r'(\{\\line \}\s*){3,}', r'{\\line }{\\line }', text)

        # Remove non-breaking spaces
        text = text.replace(u'\xa0', ' ')
        text = text.replace('\n\r', '\n')

        return text

    def dump_text(self, elem, stylizer, tag_stack=[]):
        from calibre.ebooks.oeb.base import (XHTML_NS, namespace, barename,
                urlnormalize)

        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) != XHTML_NS:
            p = elem.getparent()
            if p is not None and isinstance(p.tag, basestring) and namespace(p.tag) == XHTML_NS \
                    and elem.tail:
                return elem.tail
            return u''

        text = u''
        style = stylizer.style(elem)

        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            if hasattr(elem, 'tail') and elem.tail:
                return elem.tail
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
            src = elem.get('src')
            if src:
                src = urlnormalize(self.currently_dumping_item.abshref(src))
                block_start = ''
                block_end = ''
                if 'block' not in tag_stack:
                    block_start = '{\\par\\pard\\hyphpar '
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
        if hasattr(elem, 'text') and elem.text:
            text += txt2rtf(elem.text)

        for item in elem:
            text += self.dump_text(item, stylizer, tag_stack)

        for i in range(0, tag_count):
            end_tag =  tag_stack.pop()
            if end_tag != 'block':
                if tag in BLOCK_TAGS:
                    text += u'\\par\\pard\\plain\\hyphpar}'
                else:
                    text += u'}'

        if hasattr(elem, 'tail') and elem.tail:
            if 'block' in tag_stack:
                text += '%s' % txt2rtf(elem.tail)
            else:
                text += '{\\par\\pard\\hyphpar %s}' % txt2rtf(elem.tail)

        return text
