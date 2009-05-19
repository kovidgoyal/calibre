# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into PML markup
'''

import os, re

from calibre.ebooks.oeb.base import XHTML, XHTML_NS, barename, namespace
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.ebooks.pdb.ereader import image_name

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
    'h3'      : 'x1',
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

class PMLMLizer(object):
    def __init__(self, ignore_tables=False):
        self.ignore_tables = ignore_tables
        
    def extract_content(self, oeb_book, opts):
        oeb_book.logger.info('Converting XHTML to PML markup...')
        self.oeb_book = oeb_book
        self.opts = opts
        return self.pmlmlize_spine()
        
    def pmlmlize_spine(self):
        output = u''
        for item in self.oeb_book.spine:
            stylizer = Stylizer(item.data, item.href, self.oeb_book, self.opts.output_profile)
            output += self.add_page_anchor(item.href)
            output += self.dump_text(item.data.find(XHTML('body')), stylizer)
        output = self.clean_text(output)

        return output

    def add_page_anchor(self, href):
        href = os.path.splitext(os.path.basename(href))[0]
        return '\\Q="%s"' % href

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
        links = set(re.findall(r'(?<=\\q=").+?(?=")', text))
        for unused in anchors.difference(links):
            text = text.replace('\\Q="%s"' % unused, '')
        
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
        if tag == 'p' or style['display'] in ('block'):
            if 'block' not in tag_stack:
                tag_count += 1
                tag_stack.append('block')
        
        # Process tags that need special processing and that do not have inner
        # text. Usually these require an argument
        if tag == 'img':
            text += '\\m="%s"' % image_name(os.path.basename(elem.get('src'))).strip('\x00')
        if tag == 'hr':
            text += '\\w'
            width = elem.get('width')
            if width:
                text += '="%s%"' % width
            else:
                text += '="50%"'
        
        # Process style information that needs holds a single tag
        # Commented out because every page in an OEB book starts with this style
        #if style['page-break-before'] == 'always':
        #    text += '\\p'
        
        # Proccess tags that contain text.
        if hasattr(elem, 'text') and elem.text != None and elem.text.strip() != '':
            pml_tag = TAG_MAP.get(tag, None)
            if pml_tag and pml_tag not in tag_stack:
                tag_count += 1
                text += '\\%s' % pml_tag
                tag_stack.append(pml_tag)
                
            # Special processing of tags that require an argument.
            # Anchors links
            if tag == 'a' and 'q' not in tag_stack:
                href = elem.get('href')
                if href and '://' not in href:
                    if '#' in href:
                        href = href.partition('#')[2][1:]
                    href = os.path.splitext(os.path.basename(href))[0]
                    tag_count += 1
                    text += '\\q="%s"' % href
                    tag_stack.append('q')
            # Anchor ids
            id_name = elem.get('id')
            if id_name:
                text += '\\Q="%s"' % os.path.splitext(id_name)[0]

            # Processes style information
            for s in STYLES:
                style_tag = s[1].get(style[s[0]], None)
                if style_tag and style_tag not in tag_stack:
                    tag_count += 1
                    text += '\\%s' % style_tag
                    tag_stack.append(style_tag)
            # margin

            text += self.elem_text(elem, tag_stack)
            
        for item in elem:
            text += self.dump_text(item, stylizer, tag_stack)
        
        close_tag_list = []
        for i in range(0, tag_count):
            close_tag_list.insert(0, tag_stack.pop())
        text += self.close_tags(close_tag_list)
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'li', 'tr'):
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

