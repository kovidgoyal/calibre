# -*- coding: utf-8 -*-

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Write content to TXT.
'''

import os
import re

from lxml import etree

from calibre import entity_to_unicode
from calibre.ebooks.oeb.base import XHTML

class TxtWriter(object):
    def __init__(self, newline, log):
        self.newline = newline
        self.log = log

    def dump(self, spine):
        out = u''
        for item in spine:
            content = unicode(etree.tostring(item.data.find(XHTML('body')), encoding=unicode))
            content = self.remove_newlines(content)
            content = self.strip_html(content)
            content = self.replace_html_symbols(content)
            content = self.cleanup_text(content)
            content = self.specified_newlines(content)
            out += content

            # Put two blank lines at end of file
            end = out[-3 * len(self.newline):]
            for i in range(3 - end.count(self.newline)):
                out += self.newline

        return out

    def strip_html(self, text):
        stripped = u''

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
        for entity in set(re.findall('&.+?;', content)):
            mo = re.search('(%s)' % entity[1:-1], content)
            content = content.replace(entity, entity_to_unicode(mo))

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

    def remove_newlines(self, text):
        text = text.replace('\r\n', ' ')
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')

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

