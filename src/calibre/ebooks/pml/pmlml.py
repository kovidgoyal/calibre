# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into PML markup
'''

import os
import re

from calibre.ebooks.oeb.base import XHTML, XHTML_NS, barename, namespace
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.ebooks.pdb.ereader import image_name
from calibre import entity_to_unicode

TAG_MAP = {
    'b'       : 'B',
    'strong'  : 'B',
    'i'       : 'I',
    'small'   : 'k',
    'sub'     : 'Sb',
    'sup'     : 'Sp',
    'big'     : 'l',
    'del'     : 'o',
    'h1'      : 'x',
    'h2'      : 'X0',
    'h3'      : 'X1',
    'h4'      : 'X2',
    'h5'      : 'X3',
    'h6'      : 'X4',
    '!--'     : 'v',
}

STYLES = [
    ('font-weight', {'bold' : 'B', 'bolder' : 'B'}),
    ('font-style', {'italic' : 'I'}),
    ('text-decoration', {'underline' : 'u'}),
    ('text-align', {'right' : 'r', 'center' : 'c'}),
]

BLOCK_TAGS = [
    'p',
]

BLOCK_STYLES = [
    'block',
]

LINK_TAGS = [
    'a',
]

IMAGE_TAGS = [
    'img',
]

SEPARATE_TAGS = [
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'p',
    'div',
    'li',
    'tr',
]

class PMLMLizer(object):
    def __init__(self, log):
        self.log = log
        self.image_hrefs = {}
        self.link_hrefs = {}

    def extract_content(self, oeb_book, opts):
        self.log.info('Converting XHTML to PML markup...')
        self.oeb_book = oeb_book
        self.opts = opts
        return self.pmlmlize_spine()

    def pmlmlize_spine(self):
        self.image_hrefs = {}
        self.link_hrefs = {}
        output = u''
        output += self.get_cover_page()
        output += u'ghji87yhjko0Caliblre-toc-placeholder-for-insertion-later8ujko0987yjk'
        output += self.get_text()
        output = output.replace(u'ghji87yhjko0Caliblre-toc-placeholder-for-insertion-later8ujko0987yjk', self.get_toc())
        output = self.clean_text(output)
        return output

    def get_cover_page(self):
        output = u''
        if 'cover' in self.oeb_book.guide:
            output += '\\m="cover.png"\n'
            self.image_hrefs[self.oeb_book.guide['cover'].href] = 'cover.png'
        if 'titlepage' in self.oeb_book.guide:
            self.log.debug('Generating title page...')
            href = self.oeb_book.guide['titlepage'].href
            item = self.oeb_book.manifest.hrefs[href]
            if item.spine_position is None:
                stylizer = Stylizer(item.data, item.href, self.oeb_book, self.opts.output_profile)
                output += self.dump_text(item.data.find(XHTML('body')), stylizer, item)
        return output

    def get_toc(self):
        toc = u''
        if self.opts.inline_toc:
            self.log.debug('Generating table of contents...')
            toc += u'\\X0%s\\X0\n\n' % _('Table of Contents:')
            for item in self.oeb_book.toc:
                if item.href in self.link_hrefs.keys():
                    toc += '* \\q="#%s"%s\\q\n' % (self.link_hrefs[item.href], item.title)
                else:
                    self.oeb.warn('Ignoring toc item: %s not found in document.' % item)
        return toc

    def get_text(self):
        text = u''
        for item in self.oeb_book.spine:
            self.log.debug('Converting %s to PML markup...' % item.href)
            stylizer = Stylizer(item.data, item.href, self.oeb_book, self.opts.output_profile)
            text += self.add_page_anchor(item)
            text += self.dump_text(item.data.find(XHTML('body')), stylizer, item)
        return text

    def add_page_anchor(self, page):
        return self.get_anchor(page, '')

    def get_anchor(self, page, aid):
        aid = '%s#%s' % (page.href, aid)
        if aid not in self.link_hrefs.keys():
            self.link_hrefs[aid] = 'calibre_link-%s' % len(self.link_hrefs.keys())
        aid = self.link_hrefs[aid]
        return u'\\Q="%s"' % aid

    def clean_text(self, text):
        # Remove excess spaces at beginning and end of lines
        text = re.sub('(?m)^[ ]+', '', text)
        text = re.sub('(?m)[ ]+$', '', text)

        # Remove excessive newlines
        text = re.sub('%s{1,1}' % os.linesep, '%s%s' % (os.linesep, os.linesep), text)
        text = re.sub('%s{3,}' % os.linesep, '%s%s' % (os.linesep, os.linesep), text)
        text = re.sub('[ ]{2,}', ' ', text)

        # Remove excessive \p tags
        text = re.sub(r'\\p\s*\\p', '', text)

        # Remove anchors that do not have links
        anchors = set(re.findall(r'(?<=\\Q=").+?(?=")', text))
        links = set(re.findall(r'(?<=\\q="#).+?(?=")', text))
        for unused in anchors.difference(links):
            text = text.replace('\\Q="%s"' % unused, '')

        # Turn all html entities into unicode. This should not be necessary as
        # lxml should have already done this but we want to be sure it happens.
        for entity in set(re.findall('&.+?;', text)):
            mo = re.search('(%s)' % entity[1:-1], text)
            text = text.replace(entity, entity_to_unicode(mo))

        # Turn all unicode characters into their PML hex equivelent
        text = re.sub('[^\x00-\x7f]', lambda x: '\\U%04x' % ord(x.group()), text)

        return text

    def dump_text(self, elem, stylizer, page, tag_stack=[]):
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
        if tag in IMAGE_TAGS:
            if elem.attrib.get('src', None):
                if page.abshref(elem.attrib['src']) not in self.image_hrefs.keys():
                    if len(self.image_hrefs.keys()) == 0:
                        self.image_hrefs[page.abshref(elem.attrib['src'])] = 'cover.png'
                    else:
                        self.image_hrefs[page.abshref(elem.attrib['src'])] = image_name('%s' % len(self.image_hrefs.keys()), self.image_hrefs.keys()).strip('\x00')
        if tag == 'hr':
            text += '\\w'
            width = elem.get('width')
            if width:
                text += '="%s%%"' % width
            else:
                text += '="50%"'

        # Process style information that needs holds a single tag
        # Commented out because every page in an OEB book starts with this style
        #if style['page-break-before'] == 'always':
        #    text += '\\p'

        pml_tag = TAG_MAP.get(tag, None)
        if pml_tag and pml_tag not in tag_stack:
            tag_count += 1
            text += '\\%s' % pml_tag
            tag_stack.append(pml_tag)

        # Special processing of tags that require an argument.
        # Anchors links
        if tag in LINK_TAGS and 'q' not in tag_stack:
            href = elem.get('href')
            if href:
                href = page.abshref(href)
                if '://' not in href:
                    if '#' not in href:
                        href += '#'
                    if href not in self.link_hrefs.keys():
                        self.link_hrefs[href] = 'calibre_link-%s' % len(self.link_hrefs.keys())
                    href = self.link_hrefs[href]
                    text += '\\q="#%s"' % href
                tag_count += 1
                tag_stack.append('q')

        # Anchor ids
        id_name = elem.get('id')
        if id_name:
            text += self.get_anchor(page, id_name)

        # Processes style information
        for s in STYLES:
            style_tag = s[1].get(style[s[0]], None)
            if style_tag and style_tag not in tag_stack:
                tag_count += 1
                text += '\\%s' % style_tag
                tag_stack.append(style_tag)
        # margin

        # Proccess tags that contain text.
        if hasattr(elem, 'text') and elem.text != None and elem.text.strip() != '':
            text += self.elem_text(elem, tag_stack)

        for item in elem:
            text += self.dump_text(item, stylizer, page, tag_stack)

        close_tag_list = []
        for i in range(0, tag_count):
            close_tag_list.insert(0, tag_stack.pop())
        text += self.close_tags(close_tag_list)
        if tag in SEPARATE_TAGS:
            text += os.linesep + os.linesep

        if 'block' not in tag_stack:
            text += os.linesep + os.linesep

        #if style['page-break-after'] == 'always':
        #    text += '\\p'

        if hasattr(elem, 'tail') and elem.tail != None and elem.tail.strip() != '':
            text += self.elem_tail(elem, tag_stack)

        return text

    def elem_text(self, elem, tag_stack):
        return self.block_text(elem.text, 'block' in tag_stack)

    def elem_tail(self, elem, tag_stack):
        return self.block_text(elem.tail, 'block' in tag_stack)

    def block_text(self, text, in_block):
        if in_block:
            text = text.replace('\n\r', ' ')
            text = text.replace('\n', ' ')
            text = text.replace('\r', ' ')
        return text

    def close_tags(self, tags):
        text = u''
        for i in range(0, len(tags)):
            tag = tags.pop()
            if tag != 'block':
                text += '\\%s' % tag
        return text

