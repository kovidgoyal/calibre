# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2010, Li Fanxi <lifanxi@freemindworld.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into SNB format
'''

import os
import re

from lxml import etree

from calibre.ebooks.oeb.base import XHTML, XHTML_NS, barename, namespace
from calibre.ebooks.oeb.stylizer import Stylizer

def ProcessFileName(fileName):
    # Flat the path 
    fileName = fileName.replace("/", "_").replace(os.sep, "_")
    # Handle bookmark for HTML file
    fileName = fileName.replace("#", "_")
    # Make it lower case
    fileName = fileName.lower()
    # Change extension from jpeg to jpg
    root, ext = os.path.splitext(fileName) 
    if ext in [ '.jpeg', '.jpg', '.gif', '.svg' ]:
        fileName = root + '.png'
    return fileName
    

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
    'tr',
]

BLOCK_STYLES = [
    'block',
]

SPACE_TAGS = [
    'td',
]

CALIBRE_SNB_IMG_TAG = "<$$calibre_snb_temp_img$$>"
CALIBRE_SNB_BM_TAG = "<$$calibre_snb_bm_tag$$>"

class SNBMLizer(object):
    
    curSubItem = ""
#    curText = [ ]

    def __init__(self, log):
        self.log = log

    def extract_content(self, oeb_book, item, subitems, opts):
        self.log.info('Converting XHTML to SNBC...')
        self.oeb_book = oeb_book
        self.opts = opts
        self.item = item
        self.subitems = subitems
        return self.mlize();


    def mlize(self):
        output = [ u'' ]
        stylizer = Stylizer(self.item.data, self.item.href, self.oeb_book, self.opts, self.opts.output_profile)
        content = unicode(etree.tostring(self.item.data.find(XHTML('body')), encoding=unicode))
        content = self.remove_newlines(content)
        trees = { }
        for subitem, subtitle in self.subitems:
            snbcTree = etree.Element("snbc")
            etree.SubElement(etree.SubElement(snbcTree, "head"), "title").text = subtitle
            etree.SubElement(snbcTree, "body")
            trees[subitem] = snbcTree
        output.append(u'%s%s\n\n' % (CALIBRE_SNB_BM_TAG, ""))
        output += self.dump_text(self.subitems, etree.fromstring(content), stylizer)
        output = self.cleanup_text(u''.join(output))

        subitem = ''
        for line in output.splitlines():
            line = line.strip(' \t\n\r')
            if len(line) != 0:
                if line.find(CALIBRE_SNB_IMG_TAG) == 0:
                    etree.SubElement(trees[subitem], "img").text = line[len(CALIBRE_SNB_IMG_TAG):]
                elif line.find(CALIBRE_SNB_BM_TAG) == 0:
                    subitem = line[len(CALIBRE_SNB_BM_TAG):]
                else:
                    etree.SubElement(trees[subitem], "text").text = etree.CDATA(unicode(u'\u3000\u3000' + line))
        return trees

    def remove_newlines(self, text):
        self.log.debug('\tRemove newlines for processing...')
        text = text.replace('\r\n', ' ')
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')

        return text

    def cleanup_text(self, text):
        self.log.debug('\tClean up text...')
        # Replace bad characters.
        text = text.replace(u'\xc2', '')
        text = text.replace(u'\xa0', ' ')
        text = text.replace(u'\xa9', '(C)')

        # Replace tabs, vertical tags and form feeds with single space.
        text = text.replace('\t+', ' ')
        text = text.replace('\v+', ' ')
        text = text.replace('\f+', ' ')

        # Single line paragraph.
        text = re.sub('(?<=.)%s(?=.)' % os.linesep, ' ', text)

        # Remove multiple spaces.
        text = re.sub('[ ]{2,}', ' ', text)

        # Remove excessive newlines.
        text = re.sub('\n[ ]+\n', '\n\n', text)
        if self.opts.remove_paragraph_spacing:
            text = re.sub('\n{2,}', '\n', text)
            text = re.sub('(?imu)^(?=.)', '\t', text)
        else:
            text = re.sub('\n{3,}', '\n\n', text)

        # Replace spaces at the beginning and end of lines
        text = re.sub('(?imu)^[ ]+', '', text)
        text = re.sub('(?imu)[ ]+$', '', text)

        if self.opts.max_line_length:
            max_length = self.opts.max_line_length
            if self.opts.max_line_length < 25 and not self.opts.force_max_line_length:
                max_length = 25
            short_lines = []
            lines = text.splitlines()
            for line in lines:
                while len(line) > max_length:
                    space = line.rfind(' ', 0, max_length)
                    if space != -1:
                        # Space was found.
                        short_lines.append(line[:space])
                        line = line[space + 1:]
                    else:
                        # Space was not found.
                        if self.opts.force_max_line_length:
                            # Force breaking at max_lenght.
                            short_lines.append(line[:max_length])
                            line = line[max_length:]
                        else:
                            # Look for the first space after max_length.
                            space = line.find(' ', max_length, len(line))
                            if space != -1:
                                # Space was found.
                                short_lines.append(line[:space])
                                line = line[space + 1:]
                            else:
                                # No space was found cannot break line.
                                short_lines.append(line)
                                line = ''
                # Add the text that was less than max_lengh to the list
                short_lines.append(line)
            text = '\n'.join(short_lines)

        return text

    def dump_text(self, subitems, elem, stylizer, end=''):

        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) != XHTML_NS:
            return ['']


        text = ['']
        style = stylizer.style(elem)

        if elem.attrib.get('id') != None and elem.attrib['id'] in [ href for href, title in subitems ]:
            if self.curSubItem != None and self.curSubItem != elem.attrib['id']:
                self.curSubItem = elem.attrib['id']
                text.append(u'%s%s\n\n' % (CALIBRE_SNB_BM_TAG, self.curSubItem))

        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            return ['']

        tag = barename(elem.tag)
        in_block = False

        # Are we in a paragraph block?
        if tag in BLOCK_TAGS or style['display'] in BLOCK_STYLES:
            in_block = True
            if not end.endswith(u'\n\n') and hasattr(elem, 'text') and elem.text:
                text.append(u'\n\n')

        if tag in SPACE_TAGS:
            if not end.endswith('u ') and hasattr(elem, 'text') and elem.text:
                text.append(u' ')

        if tag == 'img':
            text.append(u'%s%s' % (CALIBRE_SNB_IMG_TAG, ProcessFileName(elem.attrib['src'])))

        # Process tags that contain text.
        if hasattr(elem, 'text') and elem.text:
            text.append(elem.text)

        for item in elem:
            en = u''
            if len(text) >= 2:
                en = text[-1][-2:]
            text += self.dump_text(subitems, item, stylizer, en)

        if in_block:
            text.append(u'\n\n')

        if hasattr(elem, 'tail') and elem.tail:
            text.append(elem.tail)

        return text
