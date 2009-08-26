# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into plain text
'''

import os, re

from lxml import etree

from calibre.ebooks.oeb.base import XHTML, XHTML_NS, barename, namespace
from calibre.ebooks.oeb.stylizer import Stylizer

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
    'block',
]

class TXTMLizer(object):

    def __init__(self, log):
        self.log = log

    def extract_content(self, oeb_book, opts):
        self.log.info('Converting XHTML to TXT...')
        self.oeb_book = oeb_book
        self.opts = opts
        return self.mlize_spine()

    def mlize_spine(self):
        output = u''
        output += self.get_toc()
        for item in self.oeb_book.spine:
            self.log.debug('Converting %s to TXT...' % item.href)
            stylizer = Stylizer(item.data, item.href, self.oeb_book, self.opts.output_profile)
            content = unicode(etree.tostring(item.data.find(XHTML('body')), encoding=unicode))
            content = self.remove_newlines(content)
            output += self.dump_text(etree.fromstring(content), stylizer)
        output = self.cleanup_text(output)

        return output

    def remove_newlines(self, text):
        self.log.debug('\tRemove newlines for processing...')
        text = text.replace('\r\n', ' ')
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')

        return text

    def get_toc(self):
        toc = u''
        if getattr(self.opts, 'inline_toc', None):
            self.log.debug('Generating table of contents...')
            toc += u'%s\n\n' % _(u'Table of Contents:')
            for item in self.oeb_book.toc:
                toc += u'* %s\n\n' % item.title
        return toc

    def cleanup_text(self, text):
        self.log.debug('\tClean up text...')
        # Replace bad characters.
        text = text.replace(u'\xc2', '')
        text = text.replace(u'\xa0', ' ')

        # Replace tabs, vertical tags and form feeds with single space.
        text = text.replace('\t+', ' ')
        text = text.replace('\v+', ' ')
        text = text.replace('\f+', ' ')

        # Single line paragraph.
        text = re.sub('(?<=.)%s(?=.)' % os.linesep, ' ', text)

        # Remove multiple spaces.
        text = re.sub('[  ]+', ' ', text)

        # Remove excessive newlines.
        text = re.sub('\n[ ]+\n', '\n\n', text)
        text = re.sub('\n{3,}', '\n\n', text)

        # Replace spaces at the beginning and end of lines
        text = re.sub('(?imu)^[ ]+', '', text)
        text = re.sub('(?imu)[ ]+$', '', text)

        return text

    def dump_text(self, elem, stylizer, end=''):
        '''
        @elem: The element in the etree that we are working on.
        @stylizer: The style information attached to the element.
        @end: The last two characters of the text from the previous element.
              This is used to determine if a blank line is needed when starting
              a new block element.
        '''

        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) != XHTML_NS:
            return u''

        text = u''
        style = stylizer.style(elem)

        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            return u''

        tag = barename(elem.tag)
        in_block = False

        # Are we in a paragraph block?
        if tag in BLOCK_TAGS or style['display'] in BLOCK_STYLES:
            in_block = True
            if not end.endswith(os.linesep + os.linesep) and hasattr(elem, 'text') and elem.text != None and elem.text.strip() != '':
                text += os.linesep + os.linesep

        # Proccess tags that contain text.
        if hasattr(elem, 'text') and elem.text != None and elem.text.strip() != '':
            text += elem.text

        for item in elem:
            text += self.dump_text(item, stylizer, text[-2:])

        if in_block:
            text += os.linesep + os.linesep

        if hasattr(elem, 'tail') and elem.tail != None and elem.tail.strip() != '':
            text += elem.tail

        return text
