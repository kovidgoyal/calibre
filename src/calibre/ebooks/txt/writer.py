# -*- coding: utf-8 -*-
from __future__ import with_statement
'''
Write content to TXT.
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import os, re, sys

from calibre.ebooks.htmlsymbols import HTML_SYMBOLS

from BeautifulSoup import BeautifulSoup

class TxtWriter(object):
    def __init__(self, newline, log):
        self.newline = newline
        self.log = log

    def dump(self, spine, metadata):
        out = u''
        for item in spine:
            content = unicode(item)
            # Convert newlines to unix style \n for processing. These
            # will be changed to the specified type later in the process.
            content = self.unix_newlines(content)
            content = self.strip_html(content)
            content = self.replace_html_symbols(content)
            content = self.cleanup_text(content)
            content = self.specified_newlines(content)
            out += content

        # Prepend metadata
        if metadata.author != None and metadata.author != '':
            if metadata.title != None and metadata.title != '':
                out = (u'%s%s%s%s' % (metadata.author.upper(), self.newline, self.newline, self.newline)) + out
                out = (u'%s%s%s%s' % (metadata.title.upper(), self.newline, self.newline, self.newline)) + out

            # Put two blank lines at end of file
            end = out[-3 * len(self.newline):]
            for i in range(3 - end.count(self.newline)):
                out += self.newline

        return out

    def strip_html(self, html):
        stripped = u''
        
        for dom_tree in BeautifulSoup(html).findAll('body'):
            text = unicode(dom_tree)
            
            # Remove unnecessary tags
            for tag in ['script', 'style']:
                text = re.sub('(?imu)<[ ]*%s[ ]*.*?>(.*)</[ ]*%s[ ]*>' % (tag, tag), '', text)
            text = re.sub('<!--.*-->', '', text)
            text = re.sub('<\?.*?\?>', '', text)
            text = re.sub('<@.*?@>', '', text)
            text = re.sub('<%.*?%>', '', text)

            # Headings usually indicate Chapters.
            # We are going to use a marker to insert the proper number of
            # newline characters at the end of cleanup_text because cleanup_text
            # remove excessive (more than 2 newlines).
            for tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                text = re.sub('(?imu)<[ ]*%s[ ]*.*?>' % tag, '-vzxedxy-', text)
                text = re.sub('(?imu)</[ ]*%s[ ]*>' % tag, '-vlgzxey-', text)

            # Separate content with space.
            for tag in ['td']:
                text = re.sub('(?imu)</[ ]*%s[ ]*>', ' ', text)
            
            # Separate content with empty line.
            for tag in ['p', 'div', 'pre', 'li', 'table', 'tr']:
                text = re.sub('(?imu)</[ ]*%s[ ]*>' % tag, '\n\n', text)
            
            for tag in ['hr', 'br']:
                text = re.sub('(?imu)<[ ]*%s.*?>' % tag, '\n\n', text)
            
            # Remove any tags that do not need special processing.
            text = re.sub('<.*?>', '', text)
            
            stripped = stripped + text
            
        return stripped
        
    def replace_html_symbols(self, content):
        for symbol in HTML_SYMBOLS:
            for code in HTML_SYMBOLS[symbol]:
                content = content.replace(code, symbol)
        return content
        
    def cleanup_text(self, text):
        # Replace bad characters.
        text = text.replace(u'\xc2', '')
        text = text.replace(u'\xa0', ' ')
    
        # Replace tabs, vertical tags and form feeds with single space.
        text = text.replace('\t+', ' ')
        text = text.replace('\v+', ' ')
        text = text.replace('\f+', ' ')
    
        # Single line paragraph.
        text = re.sub('(?<=.)\n(?=.)', ' ', text)
        
        # Remove multiple spaces.
        text = re.sub('[  ]+', ' ', text)
        
        # Remove excessive newlines.
        text = re.sub('\n[ ]+\n', '\n\n', text)
        text = re.sub('\n{3,}', '\n\n', text)
        
        # Replace markers with the proper characters.
        text = text.replace('-vzxedxy-', '\n\n\n\n\n')
        text = text.replace('-vlgzxey-', '\n\n\n')
        
        # Replace spaces at the beginning and end of lines
        text = re.sub('(?imu)^[ ]+', '', text)
        text = re.sub('(?imu)[ ]+$', '', text)
        
        return text

    def unix_newlines(self, text):
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')
        
        return text
        
    def specified_newlines(self, text):
        if self.newline == '\n':
            return text
        
        return text.replace('\n', self.newline)        


class TxtNewlines(object):
    NEWLINE_TYPES = {
                        'system'  : os.linesep,
                        'unix'    : '\n',
                        'old_mac' : '\r',
                        'windows' : '\r\n'
                     }
                     
    def __init__(self, newline_type):
        self.newline = self.NEWLINE_TYPES.get(newline_type.lower(), os.linesep)


class TxtMetadata(object):
    def __init__(self):
        self.title = None
        self.author = None
