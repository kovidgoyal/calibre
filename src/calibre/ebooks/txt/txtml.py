__license__ = 'GPL 3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into plain text
'''

import re

from lxml import etree
from polyglot.builtins import string_or_bytes


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

HEADING_TAGS = [
    'h1',
    'h2',
    'h3',
    'h4',
    'h5',
    'h6',
]

SPACE_TAGS = [
    'td',
    'br',
]


class TXTMLizer:

    def __init__(self, log):
        self.log = log

    def extract_content(self, oeb_book, opts):
        self.log.info('Converting XHTML to TXT...')
        self.oeb_book = oeb_book
        self.opts = opts
        self.toc_titles = []
        self.toc_ids = []
        self.last_was_heading = False

        self.create_flat_toc(self.oeb_book.toc)

        return self.mlize_spine()

    def mlize_spine(self):
        from calibre.ebooks.oeb.base import XHTML
        from calibre.ebooks.oeb.stylizer import Stylizer
        from calibre.utils.xml_parse import safe_xml_fromstring
        output = ['']
        output.append(self.get_toc())
        for item in self.oeb_book.spine:
            self.log.debug('Converting %s to TXT...' % item.href)
            for x in item.data.iterdescendants(etree.Comment):
                if x.text and '--' in x.text:
                    x.text = x.text.replace('--', '__')
            content = etree.tostring(item.data, encoding='unicode')
            content = self.remove_newlines(content)
            content = safe_xml_fromstring(content)
            stylizer = Stylizer(content, item.href, self.oeb_book, self.opts, self.opts.output_profile)
            output += self.dump_text(content.find(XHTML('body')), stylizer, item)
            output += '\n\n\n\n\n\n'
        output = ''.join(output)
        output = '\n'.join(l.rstrip() for l in output.splitlines())
        output = self.cleanup_text(output)

        return output

    def remove_newlines(self, text):
        self.log.debug('\tRemove newlines for processing...')
        text = text.replace('\r\n', ' ')
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')
        # Condense redundant spaces created by replacing newlines with spaces.
        text = re.sub(r'[ ]{2,}', ' ', text)

        return text

    def get_toc(self):
        toc = ['']
        if getattr(self.opts, 'inline_toc', None):
            self.log.debug('Generating table of contents...')
            toc.append('%s\n\n' % _('Table of Contents:'))
            for item in self.toc_titles:
                toc.append('* %s\n\n' % item)
        return ''.join(toc)

    def create_flat_toc(self, nodes):
        '''
        Turns a hierarchical list of TOC href's into a flat list.
        '''
        for item in nodes:
            self.toc_titles.append(item.title)
            self.toc_ids.append(item.href)
            self.create_flat_toc(item.nodes)

    def cleanup_text(self, text):
        self.log.debug('\tClean up text...')
        # Replace bad characters.
        text = text.replace('\xa0', ' ')

        # Replace tabs, vertical tags and form feeds with single space.
        text = text.replace('\t+', ' ')
        text = text.replace('\v+', ' ')
        text = text.replace('\f+', ' ')

        # Single line paragraph.
        text = re.sub('(?<=.)\n(?=.)', ' ', text)

        # Remove multiple spaces.
        text = re.sub('[ ]{2,}', ' ', text)

        # Remove excessive newlines.
        text = re.sub('\n[ ]+\n', '\n\n', text)
        if self.opts.remove_paragraph_spacing:
            text = re.sub('\n{2,}', '\n', text)
            text = re.sub(r'(?msu)^(?P<t>[^\t\n]+?)$', lambda mo: '%s\n\n' % mo.group('t'), text)
            text = re.sub(r'(?msu)(?P<b>[^\n])\n+(?P<t>[^\t\n]+?)(?=\n)', lambda mo: '{}\n\n\n\n\n\n{}'.format(mo.group('b'), mo.group('t')), text)
        else:
            text = re.sub('\n{7,}', '\n\n\n\n\n\n', text)

        # Replace spaces at the beginning and end of lines
        # We don't replace tabs because those are only added
        # when remove paragraph spacing is enabled.
        text = re.sub('(?imu)^[ ]+', '', text)
        text = re.sub('(?imu)[ ]+$', '', text)

        # Remove empty space and newlines at the beginning of the document.
        text = re.sub(r'(?u)^[ \n]+', '', text)

        if self.opts.max_line_length:
            max_length = int(self.opts.max_line_length)
            if max_length < 25 and not self.opts.force_max_line_length:
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

    def dump_text(self, elem, stylizer, page):
        '''
        @elem: The element in the etree that we are working on.
        @stylizer: The style information attached to the element.
        @page: OEB page used to determine absolute urls.
        '''
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

        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            if hasattr(elem, 'tail') and elem.tail:
                return [elem.tail]
            return ['']

        tag = barename(elem.tag)
        tag_id = elem.attrib.get('id', None)
        in_block = False
        in_heading = False

        # Are we in a heading?
        # This can either be a heading tag or a TOC item.
        if tag in HEADING_TAGS or f'{page.href}#{tag_id}' in self.toc_ids:
            in_heading = True
            if not self.last_was_heading:
                text.append('\n\n\n\n\n\n')

        # Are we in a paragraph block?
        if tag in BLOCK_TAGS or style['display'] in BLOCK_STYLES:
            if self.opts.remove_paragraph_spacing and not in_heading:
                text.append('\t')
            in_block = True

        if tag in SPACE_TAGS:
            text.append(' ')

        # Hard scene breaks.
        if tag == 'hr':
            text.append('\n\n* * *\n\n')
        # Soft scene breaks.
        try:
            ems = int(round((float(style.marginTop) / style.fontSize) - 1))
            if ems >= 1:
                text.append('\n' * ems)
        except:
            pass

        # Process tags that contain text.
        if hasattr(elem, 'text') and elem.text:
            text.append(elem.text)

        # Recurse down into tags within the tag we are in.
        for item in elem:
            text += self.dump_text(item, stylizer, page)

        if in_block:
            text.append('\n\n')
        if in_heading:
            text.append('\n')
            self.last_was_heading = True
        else:
            self.last_was_heading = False

        if hasattr(elem, 'tail') and elem.tail:
            text.append(elem.tail)

        return text
