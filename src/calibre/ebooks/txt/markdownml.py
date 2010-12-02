# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into Markdown formatted plain text
'''

import re

from lxml import etree

from calibre.utils.html2text import html2text

class MarkdownMLizer(object):

    def __init__(self, log):
        self.log = log

    def extract_content(self, oeb_book, opts):
        self.log.info('Converting XHTML to Markdown formatted TXT...')
        self.oeb_book = oeb_book
        self.opts = opts

        return self.mlize_spine()

    def mlize_spine(self):
        output = [u'']
        for item in self.oeb_book.spine:
            self.log.debug('Converting %s to Markdown formatted TXT...' % item.href)
            html = unicode(etree.tostring(item.data, encoding=unicode))
            if self.opts.remove_links:
                html = re.sub(r'<\s*a[^>]*>', '', html)
                html = re.sub(r'<\s*/\s*a\s*>', '', html)
            output += html2text(html)
        output = u''.join(output)

        return output
