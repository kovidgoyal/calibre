# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into Textile formatted plain text
'''

import re

from lxml import etree

from calibre.ebooks.oeb.base import XHTML
from calibre.utils.html2textile import html2textile

class TextileMLizer(object):

    def __init__(self, log):
        self.log = log

    def extract_content(self, oeb_book, opts):
        self.log.info('Converting XHTML to Textile formatted TXT...')
        self.oeb_book = oeb_book
        self.opts = opts

        return self.mlize_spine()

    def mlize_spine(self):
        output = [u'']

        for item in self.oeb_book.spine:
            self.log.debug('Converting %s to Textile formatted TXT...' % item.href)

            html = unicode(etree.tostring(item.data.find(XHTML('body')), encoding=unicode))

            if not self.opts.keep_links:
                html = re.sub(r'<\s*a[^>]*>', '', html)
                html = re.sub(r'<\s*/\s*a\s*>', '', html)
            if not self.opts.keep_image_references:
                html = re.sub(r'<\s*img[^>]*>', '', html)
                html = re.sub(r'<\s*img\s*>', '', html)

            text = html2textile(html)

            # Ensure the section ends with at least two new line characters.
            # This is to prevent the last paragraph from a section being
            # combined into the fist paragraph of the next.
            end_chars = text[-4:]
            # Convert all newlines to \n
            end_chars = end_chars.replace('\r\n', '\n')
            end_chars = end_chars.replace('\r', '\n')
            end_chars = end_chars[-2:]
            if not end_chars[1] == '\n':
                text += '\n\n'
            if end_chars[1] == '\n' and not end_chars[0] == '\n':
                text += '\n'

            output += text

        output = u''.join(output)

        return output
