# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into FB2 markup
'''

import cStringIO
from base64 import b64encode
from datetime import datetime
import re
import uuid

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
        self.reset_state()
    
    def reset_state(self):
        # Used to ensure text and tags are always within <p> and </p>
        self.in_p = False
        # Mapping of image names. OEB allows for images to have the same name but be stored
        # in different directories. FB2 images are all in a flat layout so we rename all images
        # into a sequential numbering system to ensure there are no collisions between image names.
        self.image_hrefs = {}

    def extract_content(self, oeb_book, opts):
        self.log.info('Converting XHTML to FB2 markup...')
        self.oeb_book = oeb_book
        self.opts = opts
        
        return self.fb2mlize_spine()

    def fb2mlize_spine(self):
        self.reset_state()
        
        output = [self.fb2_header()]
        output.append(self.get_text())
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
        metadata = {}
        metadata['author_first'] = u''
        metadata['author_middle'] = u''
        metadata['author_last'] = u''
        metadata['title'] = self.oeb_book.metadata.title[0].value
        metadata['appname'] = __appname__
        metadata['version'] = __version__
        metadata['date'] = '%i.%i.%i' % (datetime.now().day, datetime.now().month, datetime.now().year)
        metadata['lang'] = u''.join(self.oeb_book.metadata.lang) if self.oeb_book.metadata.lang else 'en'
        metadata['id'] = '%s' % uuid.uuid4() 
        
        author_parts = self.oeb_book.metadata.creator[0].value.split(' ')
        if len(author_parts) == 1:
            metadata['author_last'] = author_parts[0]
        elif len(author_parts) == 2:
            metadata['author_first'] = author_parts[0]
            metadata['author_last'] = author_parts[1]
        else:
            metadata['author_first'] = author_parts[0]
            metadata['author_middle'] = ' '.join(author_parts[1:-2])
            metadata['author_last'] = author_parts[-1]
            
        for key, value in metadata.items():
            metadata[key] = prepare_string_for_xml(value)

        return u'<FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0" xmlns:xlink="http://www.w3.org/1999/xlink">' \
                '<description>' \
                    '<title-info>' \
                        '<genre>antique</genre>' \
                        '<author>' \
                            '<first-name>%(author_first)s</first-name>' \
                            '<middle-name>%(author_middle)s</middle-name>' \
                            '<last-name>%(author_last)s</last-name>' \
                        '</author>' \
                        '<book-title>%(title)s</book-title>' \
                        '<lang>%(lang)s</lang>' \
                    '</title-info>' \
                    '<document-info>' \
                        '<author>' \
                            '<first-name></first-name>' \
                            '<middle-name></middle-name>' \
                            '<last-name></last-name>' \
                        '</author>' \
                        '<program-used>%(appname)s %(version)s</program-used>' \
                        '<date>%(date)s</date>' \
                        '<id>%(id)s</id>' \
                        '<version>1.0</version>' \
                    '</document-info>' \
                '</description>' % metadata

    def fb2_footer(self):
        return u'</FictionBook>'

    def get_text(self):
        text = ['<body>']
        for item in self.oeb_book.spine:            
            self.log.debug('Converting %s to FictionBook2 XML' % item.href)
            stylizer = Stylizer(item.data, item.href, self.oeb_book, self.opts, self.opts.output_profile)
            text.append('<section>')
            text += self.dump_text(item.data.find(XHTML('body')), stylizer, item)
            text.append('</section>')
        return ''.join(text) + '</body>'

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
    
    def handle_simple_tag(self, tag, tags):
        s_out = []
        s_tags = []
        if tag not in tags:
            p_out, p_tags = self.ensure_p()
            s_out += p_out
            s_tags += p_tags
            s_out.append('<%s>' % tag)
            s_tags.append(tag)
        return s_out, s_tags

    def dump_text(self, elem_tree, stylizer, page, tag_stack=[]):
        '''
        This function is intended to be used in a recursive manner. dump_text will
        run though all elements in the elem_tree and call itself on each element.
        
        self.image_hrefs will be populated by calling this function.
        
        @param elem_tree: etree representation of XHTML content to be transformed.
        @param stylizer: Used to track the style of elements within the tree.
        @param page: OEB page used to determine absolute urls.
        @param tag_stack: List of open FB2 tags to take into account.
        
        @return: List of string representing the XHTML converted to FB2 markup.
        '''
        # Ensure what we are converting is not a string and that the fist tag is part of the XHTML namespace.
        if not isinstance(elem_tree.tag, basestring) or namespace(elem_tree.tag) != XHTML_NS:
            return []

        style = stylizer.style(elem_tree)
        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') or style['visibility'] == 'hidden':
            return []

        # FB2 generated output.
        fb2_out = []
        # FB2 tags in the order they are opened. This will be used to close the tags.
        tags = []
        # First tag in tree
        tag = barename(elem_tree.tag)

        # Process the XHTML tag if it needs to be converted to an FB2 tag.
        if tag == 'h1' and self.opts.h1_to_title or tag == 'h2' and self.opts.h2_to_title or tag == 'h3' and self.opts.h3_to_title:
            fb2_out.append('<title>')
            tags.append('title')
        if tag == 'img':
            # TODO: Check that the image is in the manifest and only write the tag if it is.
            if elem_tree.attrib.get('src', None):
                if page.abshref(elem_tree.attrib['src']) not in self.image_hrefs.keys():
                    self.image_hrefs[page.abshref(elem_tree.attrib['src'])] = '_%s.jpg' % len(self.image_hrefs.keys())
                p_txt, p_tag = self.ensure_p()
                fb2_out += p_txt
                tags += p_tag
                fb2_out.append('<image xlink:href="#%s" />' % self.image_hrefs[page.abshref(elem_tree.attrib['src'])])
        elif tag == 'br':
            if self.in_p:
                closed_tags = []
                open_tags = tag_stack+tags
                open_tags.reverse()
                for t in open_tags:
                    fb2_out.append('</%s>' % t)
                    closed_tags.append(t)
                    if t == 'p':
                        break
                fb2_out.append('<empty-line />')
                closed_tags.reverse()
                for t in closed_tags:
                    fb2_out.append('<%s>' % t)
            else:
                fb2_out.append('<empty-line />')
        elif tag in ('div', 'li', 'p'):
            p_text, added_p = self.close_open_p(tag_stack+tags)
            fb2_out += p_text
            if added_p:
                tags.append('p')
        elif tag == 'b':
            s_out, s_tags = self.handle_simple_tag('strong', tag_stack+tags)
            fb2_out += s_out
            tags += s_tags
        elif tag == 'i':
            s_out, s_tags = self.handle_simple_tag('emphasis', tag_stack+tags)
            fb2_out += s_out
            tags += s_tags

        # Processes style information.
        if style['font-style'] == 'italic':
            s_out, s_tags = self.handle_simple_tag('emphasis', tag_stack+tags)
            fb2_out += s_out
            tags += s_tags
        elif style['font-weight'] in ('bold', 'bolder'):
            s_out, s_tags = self.handle_simple_tag('strong', tag_stack+tags)
            fb2_out += s_out
            tags += s_tags
        
        # Process element text.
        if hasattr(elem_tree, 'text') and elem_tree.text:
            if not self.in_p:
                fb2_out.append('<p>')
            fb2_out.append(prepare_string_for_xml(elem_tree.text))
            if not self.in_p:
                fb2_out.append('</p>')

        # Process sub-elements.
        for item in elem_tree:
            fb2_out += self.dump_text(item, stylizer, page, tag_stack+tags)

        # Close open FB2 tags.
        tags.reverse()
        fb2_out += self.close_tags(tags)

        # Process element text that comes after the close of the XHTML tag but before the next XHTML tag.
        if hasattr(elem_tree, 'tail') and elem_tree.tail:
            if not self.in_p:
                fb2_out.append('<p>')
            fb2_out.append(prepare_string_for_xml(elem_tree.tail))
            if not self.in_p:
                fb2_out.append('</p>')

        return fb2_out

    def close_tags(self, tags):
        text = []
        for tag in tags:
            text.append('</%s>' % tag)
            if tag == 'p':
                self.in_p = False

        return text
