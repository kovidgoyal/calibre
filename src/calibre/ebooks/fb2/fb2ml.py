# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into FB2 markup
'''

import cStringIO
from base64 import b64encode
import re

try:
    from PIL import Image
    Image
except ImportError:
    import Image

from lxml import etree

from calibre import prepare_string_for_xml
from calibre.constants import __appname__, __version__
from calibre.ebooks.oeb.base import XHTML, XHTML_NS, barename, namespace
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.ebooks.oeb.base import OEB_RASTER_IMAGES

TAG_MAP = {
    'b' : 'strong',
    'i' : 'emphasis',
    'p' : 'p',
    'li' : 'p',
    'div': 'p',
}

TAG_SPACE = []

TAG_IMAGES = [
    'img',
]

TAG_LINKS = [
]

BLOCK = [
    'p',
]

STYLES = [
    ('font-weight', {'bold'   : 'strong', 'bolder' : 'strong'}),
    ('font-style', {'italic' : 'emphasis'}),
]

class FB2MLizer(object):
    '''
    Todo: * Include more FB2 specific tags in the conversion.
          * Handle a tags.
          * Figure out some way to turn oeb_book.toc items into <section><title>
            <p> to allow for readers to generate toc from the document.
    '''

    def __init__(self, log):
        self.log = log
        self.image_hrefs = {}
        # Used to ensure text and tags are always within <p> and </p>
        self.in_p = False

    def extract_content(self, oeb_book, opts):
        self.log.info('Converting XHTML to FB2 markup...')
        self.oeb_book = oeb_book
        self.opts = opts
        return self.fb2mlize_spine()

    def fb2mlize_spine(self):
        self.image_hrefs = {}
        self.link_hrefs = {}
        output = [self.fb2_header()]
        output.append(self.get_text())
        output.append(self.fb2_body_footer())
        output.append(self.fb2mlize_images())
        output.append(self.fb2_footer())
        output = self.clean_text(u''.join(output))
        if self.opts.pretty_print:
            return u'<?xml version="1.0" encoding="UTF-8"?>\n%s' % etree.tostring(etree.fromstring(output), encoding=unicode, pretty_print=True)
        else:
            return u'<?xml version="1.0" encoding="UTF-8"?>' + output

    def clean_text(self, text):
        text = re.sub(r'(?miu)<section>\s*</section>', '', text)
        text = re.sub(r'(?miu)\s+</section>', '</section>', text)
        text = re.sub(r'(?miu)</section><section>', '</section>\n\n<section>', text)

        text = re.sub(r'(?miu)<p>\s*</p>', '', text)
        text = re.sub(r'(?miu)\s+</p>', '</p>', text)
        text = re.sub(r'(?miu)</p><p>', '</p>\n\n<p>', text)
        return text

    def fb2_header(self):
        author_first = u''
        author_middle = u''
        author_last = u''
        author_parts = self.oeb_book.metadata.creator[0].value.split(' ')

        if len(author_parts) == 1:
            author_last = author_parts[0]
        elif len(author_parts) == 2:
            author_first = author_parts[0]
            author_last = author_parts[1]
        else:
            author_first = author_parts[0]
            author_middle = ' '.join(author_parts[1:-2])
            author_last = author_parts[-1]

        return u'<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0" xmlns:xlink="http://www.w3.org/1999/xlink">' \
                '<description>' \
                    '<title-info>' \
                        '<genre></genre>' \
                        '<author>' \
                            '<first-name>%s</first-name>' \
                            '<middle-name>%s</middle-name>' \
                            '<last-name>%s</last-name>' \
                        '</author>' \
                        '<book-title>%s</book-title>' \
                        '<annotation><p/></annotation>' \
                    '</title-info>' \
                    '<document-info>' \
                        '<program-used>%s %s</program-used>' \
                    '</document-info>' \
                '</description><body>' % tuple(map(prepare_string_for_xml, (author_first, author_middle, author_last,
                        self.oeb_book.metadata.title[0].value, __appname__, __version__)))

    def get_text(self):
        text = []
        for item in self.oeb_book.spine:            
            self.log.debug('Converting %s to FictionBook2 XML' % item.href)
            stylizer = Stylizer(item.data, item.href, self.oeb_book, self.opts, self.opts.output_profile)
            text.append('<section>')
            text += self.dump_text(item.data.find(XHTML('body')), stylizer, item)
            text.append('</section>')
        return ''.join(text)

    def fb2_body_footer(self):
        return u'</body>'

    def fb2_footer(self):
        return u'</FictionBook>'

    def fb2mlize_images(self):
        images = []
        for item in self.oeb_book.manifest:
            if item.media_type in OEB_RASTER_IMAGES:
                try:
                    im = Image.open(cStringIO.StringIO(item.data)).convert('RGB')
                    data = cStringIO.StringIO()
                    im.save(data, 'JPEG')
                    data = data.getvalue()

                    raw_data = b64encode(data)
                    # Don't put the encoded image on a single line.
                    data = ''
                    col = 1
                    for char in raw_data:
                        if col == 72:
                            data += '\n'
                            col = 1
                        col += 1
                        data += char
                    images.append('<binary id="%s" content-type="%s">%s\n</binary>' % (self.image_hrefs.get(item.href, '_0000.JPEG'), item.media_type, data))
                except Exception as e:
                    self.log.error('Error: Could not include file %s because ' \
                        '%s.' % (item.href, e))
        return ''.join(images)

    def ensure_p(self):
        if self.in_p:
            return [], []
        else:
            self.in_p = True
            return ['<p>'], ['p']
        
    def insert_empty_line(self, tags):
        if self.in_p:
            text = ['']
            closed_tags = []
            tags.reverse()
            for t in tags:
                text.append('</%s>' % t)
                closed_tags.append(t)
                if t == 'p':
                    break
            text.append('<empty-line />')
            closed_tags.reverse()
            for t in closed_tags:
                text.append('<%s>' % t)
            return text
        else:
            return ['<empty-line />']

    def close_open_p(self, tags):
        text = ['']
        added_p = False
        
        if self.in_p:
            # Close all up to p. Close p. Reopen all closed tags including p.
            closed_tags = []
            tags.reverse()
            for t in tags:
                text.append('</%s>' % t)
                closed_tags.append(t)
                if t == 'p':
                    break
            closed_tags.reverse()
            for t in closed_tags:
                text.append('<%s>' % t)
        else:
            text.append('<p>')
            added_p = True
            self.in_p = True
        
        return text, added_p

    def dump_text(self, elem, stylizer, page, tag_stack=[]):
        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) != XHTML_NS:
            return []

        style = stylizer.style(elem)
        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            return []

        fb2_text = []
        tags = []

        tag = barename(elem.tag)

        if tag in TAG_IMAGES:
            if elem.attrib.get('src', None):
                if page.abshref(elem.attrib['src']) not in self.image_hrefs.keys():
                    self.image_hrefs[page.abshref(elem.attrib['src'])] = '_%s.jpg' % len(self.image_hrefs.keys())
                p_txt, p_tag = self.ensure_p()
                fb2_text += p_txt
                tags += p_tag
                fb2_text.append('<image xlink:href="#%s" />' % self.image_hrefs[page.abshref(elem.attrib['src'])])

        if tag == 'h1' and self.opts.h1_to_title or tag == 'h2' and self.opts.h2_to_title or tag == 'h3' and self.opts.h3_to_title:
            fb2_text.append('<title>')
            tags.append('title')
        if tag == 'br':
            fb2_text += self.insert_empty_line(tag_stack+tags)

        fb2_tag = TAG_MAP.get(tag, None)
        if fb2_tag == 'p':
            p_text, added_p = self.close_open_p(tag_stack+tags)
            fb2_text += p_text
            if added_p:
                tags.append('p')
        elif fb2_tag and fb2_tag not in tag_stack+tags:
            p_text, p_tags = self.ensure_p()
            fb2_text += p_text
            tags += p_tags
            fb2_text.append('<%s>' % fb2_tag)
            tags.append(fb2_tag)

        # Processes style information
        for s in STYLES:
            style_tag = s[1].get(style[s[0]], None)
            if style_tag and style_tag not in tag_stack+tags:
                p_text, p_tags = self.ensure_p()
                fb2_text += p_text
                tags += p_tags
                fb2_text.append('<%s>' % style_tag)
                tags.append(style_tag)

        if tag in TAG_SPACE:
            fb2_text.append(' ')

        if hasattr(elem, 'text') and elem.text:
            if not self.in_p:
                fb2_text.append('<p>')
            fb2_text.append(prepare_string_for_xml(elem.text))
            if not self.in_p:
                fb2_text.append('</p>')

        for item in elem:
            fb2_text += self.dump_text(item, stylizer, page, tag_stack+tags)

        tags.reverse()
        fb2_text += self.close_tags(tags)

        if hasattr(elem, 'tail') and elem.tail:
            if not self.in_p:
                fb2_text.append('<p>')
            fb2_text.append(prepare_string_for_xml(elem.tail))
            if not self.in_p:
                fb2_text.append('</p>')

        return fb2_text

    def close_tags(self, tags):
        text = []
        for tag in tags:
            text.append('</%s>' % tag)
            if tag == 'p':
                self.in_p = False

        return text
