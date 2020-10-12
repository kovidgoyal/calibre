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
from polyglot.builtins import unicode_type, string_or_bytes


def ProcessFileName(fileName):
    # Flat the path
    fileName = fileName.replace("/", "_").replace(os.sep, "_")
    # Handle bookmark for HTML file
    fileName = fileName.replace("#", "_")
    # Make it lower case
    fileName = fileName.lower()
    # Change all images to jpg
    root, ext = os.path.splitext(fileName)
    if ext in ['.jpeg', '.jpg', '.gif', '.svg', '.png']:
        fileName = root + '.jpg'
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
CALIBRE_SNB_PRE_TAG = "<$$calibre_snb_pre_tag$$>"


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
        return self.mlize()

    def merge_content(self, old_tree, oeb_book, item, subitems, opts):
        newTrees = self.extract_content(oeb_book, item, subitems, opts)
        body = old_tree.find(".//body")
        if body is not None:
            for subName in newTrees:
                newbody = newTrees[subName].find(".//body")
                for entity in newbody:
                    body.append(entity)

    def mlize(self):
        from calibre.ebooks.oeb.base import XHTML
        from calibre.ebooks.oeb.stylizer import Stylizer
        from calibre.utils.xml_parse import safe_xml_fromstring
        output = [u'']
        stylizer = Stylizer(self.item.data, self.item.href, self.oeb_book, self.opts, self.opts.output_profile)
        content = etree.tostring(self.item.data.find(XHTML('body')), encoding='unicode')
#        content = self.remove_newlines(content)
        trees = {}
        for subitem, subtitle in self.subitems:
            snbcTree = etree.Element("snbc")
            snbcHead = etree.SubElement(snbcTree, "head")
            etree.SubElement(snbcHead, "title").text = subtitle
            if self.opts and self.opts.snb_hide_chapter_name:
                etree.SubElement(snbcHead, "hidetitle").text = "true"
            etree.SubElement(snbcTree, "body")
            trees[subitem] = snbcTree
        output.append('%s%s\n\n' % (CALIBRE_SNB_BM_TAG, ""))
        output += self.dump_text(self.subitems, safe_xml_fromstring(content), stylizer)[0]
        output = self.cleanup_text(''.join(output))

        subitem = ''
        bodyTree = trees[subitem].find(".//body")
        for line in output.splitlines():
            pos = line.find(CALIBRE_SNB_PRE_TAG)
            if pos == -1:
                line = line.strip(' \t\n\r\u3000')
            else:
                etree.SubElement(bodyTree, "text").text = \
                    etree.CDATA(line[pos+len(CALIBRE_SNB_PRE_TAG):])
                continue
            if len(line) != 0:
                if line.find(CALIBRE_SNB_IMG_TAG) == 0:
                    prefix = ProcessFileName(os.path.dirname(self.item.href))
                    if prefix != '':
                        etree.SubElement(bodyTree, "img").text = \
                            prefix + '_' + line[len(CALIBRE_SNB_IMG_TAG):]
                    else:
                        etree.SubElement(bodyTree, "img").text = \
                            line[len(CALIBRE_SNB_IMG_TAG):]
                elif line.find(CALIBRE_SNB_BM_TAG) == 0:
                    subitem = line[len(CALIBRE_SNB_BM_TAG):]
                    bodyTree = trees[subitem].find(".//body")
                else:
                    if self.opts and not self.opts.snb_dont_indent_first_line:
                        prefix = '\u3000\u3000'
                    else:
                        prefix = ''
                    etree.SubElement(bodyTree, "text").text = \
                        etree.CDATA(unicode_type(prefix + line))
                if self.opts and self.opts.snb_insert_empty_line:
                    etree.SubElement(bodyTree, "text").text = \
                        etree.CDATA('')

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
        text = text.replace('\xc2', '')
        text = text.replace('\xa0', ' ')
        text = text.replace('\xa9', '(C)')

        # Replace tabs, vertical tags and form feeds with single space.
        text = text.replace('\t+', ' ')
        text = text.replace('\v+', ' ')
        text = text.replace('\f+', ' ')

        # Single line paragraph.
        text = re.sub('(?<=.)%s(?=.)' % os.linesep, ' ', text)

        # Remove multiple spaces.
        # text = re.sub('[ ]{2,}', ' ', text)

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

        if self.opts.snb_max_line_length:
            max_length = self.opts.snb_max_line_length
            if self.opts.max_line_length < 25:  # and not self.opts.force_max_line_length:
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
                        if False and self.opts.force_max_line_length:
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

    def dump_text(self, subitems, elem, stylizer, end='', pre=False, li=''):
        from calibre.ebooks.oeb.base import XHTML_NS, barename, namespace

        if not isinstance(elem.tag, string_or_bytes) \
           or namespace(elem.tag) != XHTML_NS:
            p = elem.getparent()
            if p is not None and isinstance(p.tag, string_or_bytes) and namespace(p.tag) == XHTML_NS \
                    and elem.tail:
                return [elem.tail]
            return ['']

        text = ['']
        style = stylizer.style(elem)

        if elem.attrib.get('id') is not None and elem.attrib['id'] in [href for href, title in subitems]:
            if self.curSubItem is not None and self.curSubItem != elem.attrib['id']:
                self.curSubItem = elem.attrib['id']
                text.append('\n\n%s%s\n\n' % (CALIBRE_SNB_BM_TAG, self.curSubItem))

        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            if hasattr(elem, 'tail') and elem.tail:
                return [elem.tail]
            return ['']

        tag = barename(elem.tag)
        in_block = False

        # Are we in a paragraph block?
        if tag in BLOCK_TAGS or style['display'] in BLOCK_STYLES:
            in_block = True
            if not end.endswith('\n\n') and hasattr(elem, 'text') and elem.text:
                text.append('\n\n')

        if tag in SPACE_TAGS:
            if not end.endswith('u ') and hasattr(elem, 'text') and elem.text:
                text.append(' ')

        if tag == 'img':
            text.append('\n\n%s%s\n\n' % (CALIBRE_SNB_IMG_TAG, ProcessFileName(elem.attrib['src'])))

        if tag == 'br':
            text.append('\n\n')

        if tag == 'li':
            li = '- '

        pre = (tag == 'pre' or pre)
        # Process tags that contain text.
        if hasattr(elem, 'text') and elem.text:
            if pre:
                text.append(('\n\n%s' % CALIBRE_SNB_PRE_TAG).join((li + elem.text).splitlines()))
            else:
                text.append(li + elem.text)
            li = ''

        for item in elem:
            en = ''
            if len(text) >= 2:
                en = text[-1][-2:]
            t = self.dump_text(subitems, item, stylizer, en, pre, li)[0]
            text += t

        if in_block:
            text.append('\n\n')

        if hasattr(elem, 'tail') and elem.tail:
            if pre:
                text.append(('\n\n%s' % CALIBRE_SNB_PRE_TAG).join(elem.tail.splitlines()))
            else:
                text.append(li + elem.tail)
            li = ''

        return text, li
