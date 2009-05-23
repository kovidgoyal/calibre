# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into RB compatible markup.
'''

import os
import re

from calibre.ebooks.oeb.base import XHTML, XHTML_NS, barename, namespace
from calibre.ebooks.oeb.stylizer import Stylizer

TAGS = [
    'b',
    'big',
    'blockquote',
    'br',
    'center',
    'code',
    'div',
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
    'hr',
    'i',
    'li',
    'ol',
    'p',
    'pre',
    'small',
    'sub',
    'sup',
    'ul',
]

LINK_TAGS = [
    'a',
]

STYLES = [
    ('font-weight', {'bold'   : 'b', 'bolder' : 'b'}),
    ('font-style', {'italic' : 'i'}),
    ('text-align', {'center' : 'center'}),
]

class RBMLizer(object):

    def __init__(self, name_map={}, ignore_tables=False):
        self.name_map = name_map
        self.ignore_tables = ignore_tables

    def extract_content(self, oeb_book, opts):
        oeb_book.logger.info('Converting XHTML to RB markup...')
        self.oeb_book = oeb_book
        self.opts = opts
        return self.mlize_spine()


    def mlize_spine(self):
        output = u'<HTML><HEAD><TITLE></TITLE></HEAD><BODY>'
        for item in self.oeb_book.spine:
            stylizer = Stylizer(item.data, item.href, self.oeb_book, self.opts.output_profile)
            output += self.add_page_anchor(item.href)
            output += self.dump_text(item.data.find(XHTML('body')), stylizer)
        output += u'</BODY></HTML>'
        output = self.clean_text(output)
        return output

    def add_page_anchor(self, href):
        href = os.path.splitext(os.path.basename(href))[0]
        return u'<A NAME="%s"></A>' % href

    def clean_text(self, text):        
        # Remove anchors that do not have links
        anchors = set(re.findall(r'(?<=<A NAME=").+?(?="></A>)', text))
        links = set(re.findall(r'(?<=<A HREF="#).+?(?=">)', text))
        for unused in anchors.difference(links):
            text = text.replace('<A NAME="%s"></A>' % unused, '')

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
        
        # Process tags that need special processing and that do not have inner
        # text. Usually these require an argument
        if tag == 'img':
            src = os.path.basename(elem.get('src'))
            name = self.name_map.get(src, src)
            text += '<IMG SRC="%s">' % name

        rb_tag = tag.upper() if tag in TAGS else None
        if rb_tag:
            tag_count += 1
            text += '<%s>' % rb_tag
            tag_stack.append(rb_tag)

        if tag in LINK_TAGS:
            href = elem.get('href')
            if href:
                if '://' not in href:
                    if '#' in href:
                        href = href.partition('#')[2]
                    href = os.path.splitext(os.path.basename(href))[0]
                tag_count += 1
                text += '<A HREF="%s">' % href
                tag_stack.append('A')

        # Anchor ids
        id_name = elem.get('id')
        if id_name:
            text += '<A NAME="%s"></A>' % os.path.splitext(id_name)[0]

        # Processes style information
        for s in STYLES:
            style_tag = s[1].get(style[s[0]], None)
            if style_tag:
                style_tag = style_tag.upper()
                tag_count += 1
                text += '<%s>' % style_tag
                tag_stack.append(style_tag)

        # Proccess tags that contain text.
        if hasattr(elem, 'text') and elem.text != None and elem.text.strip() != '':
            text += elem.text

        for item in elem:
            text += self.dump_text(item, stylizer, tag_stack)

        close_tag_list = []
        for i in range(0, tag_count):
            close_tag_list.insert(0, tag_stack.pop())

        text += self.close_tags(close_tag_list)

        if hasattr(elem, 'tail') and elem.tail != None and elem.tail.strip() != '':
                text += elem.tail

        return text

    def close_tags(self, tags):
        text = u''
        for i in range(0, len(tags)):
            tag = tags.pop()
            text += '</%s>' % tag

        return text
