# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into RTF markup
'''

import os
import re

from calibre.ebooks.oeb.base import XHTML, XHTML_NS, barename, namespace
from calibre.ebooks.oeb.stylizer import Stylizer

TAGS = {
    'b': '\\b',
    'del': '\\deleted',
    'h1': '\\b \\par \\pard \\hyphpar \\keep',
    'h2': '\\b \\par \\pard \\hyphpar \\keep',
    'h3': '\\b \\par \\pard \\hyphpar \\keep',
    'h4': '\\b \\par \\pard \\hyphpar \\keep',
    'h5': '\\b \\par \\pard \\hyphpar \\keep',
    'h6': '\\b \\par \\pard \\hyphpar \\keep',
    'li': '\\par \\pard \\hyphpar \\keep \t',
    'p': '\\par \\pard \\hyphpar \\keep \t',
    #'ol': '\\pn \\pnrestart \\pnlvlblt',
    'sub': '\\sub',
    'sup': '\\super',
    'u': '\\ul',
    #'ul': '\\pn \\pnrestart \\pndec',
}

SINGLE_TAGS = {
    'br': '{\\line }',
    'div': '{\\line }',
}

STYLES = [
    ('display', {'block': '\\par \\pard \\hyphpar \\keep'}),
    ('font-weight', {'bold': '\\b', 'bolder': '\\b'}),
    ('font-style', {'italic': '\\i'}),
#    ('page-break-before', {'always': '\\pagebb '}),
    ('text-align', {'center': '\\qc', 'left': '\\ql', 'right': '\\qr', 'justify': '\\qj'}),
    ('text-decoration', {'line-through': '\\strike', 'underline': '\\ul'}),
]

BLOCK_TAGS = [
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
    'block'
]

'''
TODO:
    * Tables
    * Images
    * Fonts
'''
class RTFMLizer(object):
    
    def __init__(self, ignore_tables=False):
        self.ignore_tables = ignore_tables

    def extract_content(self, oeb_book, opts):
        oeb_book.logger.info('Converting XHTML to RTF markup...')
        self.oeb_book = oeb_book
        self.opts = opts
        return self.mlize_spine()

    def mlize_spine(self):
        output = self.header()
        for item in self.oeb_book.spine:
            stylizer = Stylizer(item.data, item.href, self.oeb_book, self.opts.output_profile)
            output += self.dump_text(item.data.find(XHTML('body')), stylizer)
        output += self.footer()
        output = self.clean_text(output)

        return output

    def header(self):
        return u'{\\rtf1\\ansi\\ansicpg1252\\deff0\\deflang1033'

    def footer(self):
        return ' }'
    
    def clean_text(self, text):
        # Remove excess spaces at beginning and end of lines
        text = re.sub('(?m)^[ ]+', '', text)
        text = re.sub('(?m)[ ]+$', '', text)

        # Remove excessive newlines
        #text = re.sub('%s{1,1}' % os.linesep, '%s%s' % (os.linesep, os.linesep), text)
        text = re.sub('%s{3,}' % os.linesep, '%s%s' % (os.linesep, os.linesep), text)

        # Remove excessive spaces
        text = re.sub('[ ]{2,}', ' ', text)

        text = re.sub(r'(\{\\line \}){3,}', r'{\\line }{\\line }', text)
        text = re.sub(r'(\{\\line \})+\{\\par', r'{\\par', text)

        return text

    def dump_text(self, elem, stylizer, tag_stack=[]):
        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) != XHTML_NS:
            return u''

        text = u''
        style = stylizer.style(elem)

        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            return u''

        tag = barename(elem.tag)
        tag_count = 0
        
        # Are we in a paragraph block?
        if tag in BLOCK_TAGS or style['display'] in BLOCK_STYLES:
            if 'block' not in tag_stack:
                tag_count += 1
                tag_stack.append('block')

        single_tag = SINGLE_TAGS.get(tag, None)
        if single_tag:
            text += single_tag

        rtf_tag = TAGS.get(tag, None)
        if rtf_tag and rtf_tag not in tag_stack:
            tag_count += 1
            text += '{%s\n' % rtf_tag
            tag_stack.append(rtf_tag)

        # Processes style information
        for s in STYLES:
            style_tag = s[1].get(style[s[0]], None)
            if style_tag and style_tag not in tag_stack:
                tag_count += 1
                text += '{%s\n' % style_tag
                tag_stack.append(style_tag)

        # Proccess tags that contain text.
        if hasattr(elem, 'text') and elem.text != None and elem.text.strip() != '':
            text += '%s' % elem.text

        for item in elem:
            text += self.dump_text(item, stylizer, tag_stack)

        for i in range(0, tag_count):
            end_tag =  tag_stack.pop()
            if end_tag != 'block':
                text += u'}'

        if hasattr(elem, 'tail') and elem.tail != None and elem.tail.strip() != '':
            if 'block' in tag_stack:
                text += '%s ' % elem.tail
            else:
                text += '{\\par \\pard \\hyphpar \\keep %s}' % elem.tail
     
        return text
