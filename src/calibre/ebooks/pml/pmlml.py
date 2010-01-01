# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into PML markup
'''

import re

from calibre.ebooks.oeb.base import XHTML, XHTML_NS, barename, namespace
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.ebooks.pdb.ereader import image_name
from calibre.ebooks.pml import unipmlcode

TAG_MAP = {
    'b'       : 'B',
    'strong'  : 'B',
    'i'       : 'i',
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
    ('font-style', {'italic' : 'i'}),
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

        # This is used for adding \CX tags chapter markers. This is separate
        # from the optional inline toc.
        self.toc = {}
        for item in oeb_book.toc:
            page, mid, id = item.href.partition('#')
            if not self.toc.get(page, None):
                self.toc[page] = {}
            self.toc[page][id] = item.title

        return self.pmlmlize_spine()

    def pmlmlize_spine(self):
        self.image_hrefs = {}
        self.link_hrefs = {}
        output = [u'']
        output.append(self.get_cover_page())
        output.append(u'ghji87yhjko0Caliblre-toc-placeholder-for-insertion-later8ujko0987yjk')
        output.append(self.get_text())
        output = ''.join(output).replace(u'ghji87yhjko0Caliblre-toc-placeholder-for-insertion-later8ujko0987yjk', self.get_toc())
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
                output += ''.join(self.dump_text(item.data.find(XHTML('body')), stylizer, item))
        return output

    def get_toc(self):
        '''
        Generation of inline TOC
        '''

        toc = []
        if self.opts.inline_toc:
            self.log.debug('Generating table of contents...')
            toc.append(u'\\X0%s\\X0\n\n' % _('Table of Contents:'))
            for item in self.oeb_book.toc:
                if item.href in self.link_hrefs.keys():
                    toc.append('* \\q="#%s"%s\\q\n' % (self.link_hrefs[item.href], item.title))
                else:
                    self.oeb.warn('Ignoring toc item: %s not found in document.' % item)
        return ''.join(toc)

    def get_text(self):
        text = [u'']
        for item in self.oeb_book.spine:
            self.log.debug('Converting %s to PML markup...' % item.href)
            stylizer = Stylizer(item.data, item.href, self.oeb_book, self.opts.output_profile)
            text.append(self.add_page_anchor(item))
            text += self.dump_text(item.data.find(XHTML('body')), stylizer, item)
        return ''.join(text)

    def add_page_anchor(self, page):
        return self.get_anchor(page, '')

    def get_anchor(self, page, aid):
        aid = '%s#%s' % (page.href, aid)
        if aid not in self.link_hrefs.keys():
            self.link_hrefs[aid] = 'calibre_link-%s' % len(self.link_hrefs.keys())
        aid = self.link_hrefs[aid]
        return u'\\Q="%s"' % aid

    def remove_newlines(self, text):
        text = text.replace('\r\n', ' ')
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')
        return text

    def clean_text(self, text):
        # Remove excessive \p tags
        text = re.sub(r'\\p\s*\\p', '', text)

        # Remove anchors that do not have links
        anchors = set(re.findall(r'(?<=\\Q=").+?(?=")', text))
        links = set(re.findall(r'(?<=\\q="#).+?(?=")', text))
        for unused in anchors.difference(links):
            text = text.replace('\\Q="%s"' % unused, '')

        # Replace bad characters.
        text = text.replace(u'\xc2', '')
        text = text.replace(u'\xa0', ' ')

        # Turn all characters that cannot be represented by themself into their
        # PML code equivelent
        text = re.sub('[^\x00-\x7f]', lambda x: unipmlcode(x.group()), text)

        # Remove excess spaces at beginning and end of lines
        text = re.sub('(?m)^[ ]+', '', text)
        text = re.sub('(?m)[ ]+$', '', text)

        # Remove excessive spaces
        text = re.sub('[ ]{2,}', ' ', text)

        # Remove excessive newlines
        text = re.sub('\n[ ]+\n', '\n\n', text)
        text = re.sub('\n\n\n+', '\n\n', text)

        return text

    def dump_text(self, elem, stylizer, page, tag_stack=[]):
        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) != XHTML_NS:
            return []

        text = []
        style = stylizer.style(elem)

        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            return []

        tag = barename(elem.tag)
        tag_count = 0

        # Are we in a paragraph block?
        if tag in BLOCK_TAGS:# or style['display'] in BLOCK_STYLES:
            if 'block' not in tag_stack:
                tag_count += 1
                tag_stack.append('block')
                if self.opts.remove_paragraph_spacing:
                    text.append('\\t')

        # Process tags that need special processing and that do not have inner
        # text. Usually these require an argument
        if tag in IMAGE_TAGS:
            if elem.attrib.get('src', None):
                if page.abshref(elem.attrib['src']) not in self.image_hrefs.keys():
                    if len(self.image_hrefs.keys()) == 0:
                        self.image_hrefs[page.abshref(elem.attrib['src'])] = 'cover.png'
                    else:
                        self.image_hrefs[page.abshref(elem.attrib['src'])] = image_name('%s.png' % len(self.image_hrefs.keys()), self.image_hrefs.keys()).strip('\x00')
                text.append('\\m="%s"' % self.image_hrefs[page.abshref(elem.attrib['src'])])
        if tag == 'hr':
            w = '\\w'
            width = elem.get('width')
            if width:
                w += '="%s%%"' % width
            else:
                w += '="50%"'
            text.append(w)
        toc_id = elem.attrib.get('id', None)
        if toc_id:
            if self.toc.get(page.href, None):
                toc_title = self.toc[page.href].get(toc_id, None)
                if toc_title:
                    text.append('\\C0="%s"' % toc_title)

        # Process style information that needs holds a single tag
        # Commented out because every page in an OEB book starts with this style
        #if style['page-break-before'] == 'always':
        #    text.append('\\p')

        pml_tag = TAG_MAP.get(tag, None)
        if pml_tag and pml_tag not in tag_stack:
            tag_count += 1
            text.append('\\%s' % pml_tag)
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
                    text.append('\\q="#%s"' % href)
                tag_count += 1
                tag_stack.append('q')

        # Anchor ids
        id_name = elem.get('id')
        if id_name:
            text.append(self.get_anchor(page, id_name))

        # Processes style information
        for s in STYLES:
            style_tag = s[1].get(style[s[0]], None)
            if style_tag and style_tag not in tag_stack:
                tag_count += 1
                text.append('\\%s' % style_tag)
                tag_stack.append(style_tag)
        # margin

        # Proccess tags that contain text.
        if hasattr(elem, 'text') and elem.text:
            text.append(self.remove_newlines(elem.text))

        for item in elem:
            text += self.dump_text(item, stylizer, page, tag_stack)

        close_tag_list = []
        for i in range(0, tag_count):
            close_tag_list.insert(0, tag_stack.pop())
        text += self.close_tags(close_tag_list)
        if tag in SEPARATE_TAGS:
            text.append('\n')
            if not self.opts.remove_paragraph_spacing:
                text.append('\n')

        if 'block' not in tag_stack and text and text[-1] != '\n':
            text.append('\n')
            if not self.opts.remove_paragraph_spacing:
                text.append('\n')

        #if style['page-break-after'] == 'always':
        #    text.append('\\p')

        if hasattr(elem, 'tail') and elem.tail:
            text.append(self.remove_newlines(elem.tail))

        return text

    def close_tags(self, tags):
        text = [u'']
        for i in range(0, len(tags)):
            tag = tags.pop()
            if tag != 'block':
                text.append('\\%s' % tag)
        return text
