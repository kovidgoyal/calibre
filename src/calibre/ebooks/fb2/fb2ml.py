# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into FB2 markup
'''

import os
from base64 import b64encode

from calibre.ebooks.oeb.base import XHTML, XHTML_NS, barename, namespace
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.ebooks.oeb.base import OEB_IMAGES
from calibre.constants import __appname__, __version__

from BeautifulSoup import BeautifulSoup

TAG_MAP = {
    'b' : 'strong',
    'i' : 'emphasis',
    'p' : 'p',
    'div' : 'p',
}

STYLES = [
    ('font-weight', {'bold'   : 'strong', 'bolder' : 'strong'}),
    ('font-style', {'italic' : 'emphasis'}),
]

class FB2MLizer(object):
    def __init__(self, ignore_tables=False):
        self.ignore_tables = ignore_tables
        
    def extract_content(self, oeb_book, opts):
        oeb_book.logger.info('Converting XHTML to FB2 markup...')
        self.oeb_book = oeb_book
        self.opts = opts
        return self.fb2mlize_spine()
        
    def fb2mlize_spine(self):
        output = self.fb2_header()
        for item in self.oeb_book.spine:
            stylizer = Stylizer(item.data, item.href, self.oeb_book, self.opts.output_profile)
            output += self.dump_text(item.data.find(XHTML('body')), stylizer)
        output += self.fb2_body_footer()
        output += self.fb2mlize_images()
        output += self.fb2_footer()
        output = self.clean_text(output)
        return BeautifulSoup(output.encode('utf-8')).prettify()

    def fb2_header(self):
        return u'<?xml version="1.0" encoding="utf-8"?> ' \
        '<FictionBook xmlns:xlink="http://www.w3.org/1999/xlink" ' \
        'xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"> ' \
        '<description><title-info><book-title>%s</book-title> ' \
        '</title-info><document-info> ' \
        '<program-used>%s - %s</program-used></document-info> ' \
        '</description><body><section>' % (self.oeb_book.metadata.title[0].value, __appname__, __version__)
        
    def fb2_body_footer(self):
        return u'</section></body>'
        
    def fb2_footer(self):
        return u'</FictionBook>'

    def fb2mlize_images(self):
        images = u''
        for item in self.oeb_book.manifest:
            if item.media_type in OEB_IMAGES:
                data = b64encode(item.data)
                images += '<binary id="%s" content-type="%s">%s</binary>' % (os.path.basename(item.href),  item.media_type, data)
        return images

    def clean_text(self, text):
        return text.replace('&', '')

    def dump_text(self, elem, stylizer, tag_stack=[]):
        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) != XHTML_NS:
            return u''
            
        fb2_text = u''
        style = stylizer.style(elem)

        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            return u''
        
        tag = barename(elem.tag)
        if tag == 'img':
            fb2_text += '<image xlink:herf="#%s" />' % os.path.basename(elem.attrib['src'])
        
        tag_count = 0
        if hasattr(elem, 'text') and elem.text != None and elem.text.strip() != '':
            fb2_tag = TAG_MAP.get(tag, 'p')
            if fb2_tag and fb2_tag not in tag_stack:
                tag_count += 1
                fb2_text += '<%s>' % fb2_tag
                tag_stack.append(fb2_tag)

            # Processes style information
            for s in STYLES:
                style_tag = s[1].get(style[s[0]], None)
                if style_tag:
                    tag_count += 1
                    fb2_text += '<%s>' % style_tag
                    tag_stack.append(style_tag)

            fb2_text += elem.text
        
        for item in elem:
            fb2_text += self.dump_text(item, stylizer, tag_stack)

        close_tag_list = []
        for i in range(0, tag_count):
            close_tag_list.insert(0, tag_stack.pop())
            
        fb2_text += self.close_tags(close_tag_list)

        if hasattr(elem, 'tail') and elem.tail != None and elem.tail.strip() != '':
            if 'p' not in tag_stack:
                fb2_text += '<p>%s</p>' % elem.tail
            else:
                fb2_text += elem.tail
            
        return fb2_text

    def close_tags(self, tags):
        fb2_text = u''
        for i in range(0, len(tags)):
            fb2_tag = tags.pop()
            fb2_text += '</%s>' % fb2_tag

        return fb2_text

