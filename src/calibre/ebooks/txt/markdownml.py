# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '''2011, John Schember <john@nachtimwald.com>
2011, Leigh Parry <leighparry@blueyonder.co.uk>'''
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into Textile formatted plain text
'''
import re

from functools import partial

from calibre.ebooks.htmlz.oeb2html import OEB2HTML
from calibre.ebooks.oeb.base import XHTML, XHTML_NS, barename, namespace, rewrite_links
from calibre.ebooks.oeb.stylizer import Stylizer

class MarkdownMLizer(OEB2HTML):

    def extract_content(self, oeb_book, opts):
        self.log.info('Converting XHTML to Markdown formatted TXT...')
        self.opts = opts
        self.in_code = False
        self.in_pre = False
        self.list = []
        self.blockquotes = 0
        self.remove_space_after_newline = False
        self.base_hrefs = [item.href for item in oeb_book.spine]
        self.map_resources(oeb_book)

        self.style_bold = False
        self.style_italic = False

        txt = self.mlize_spine(oeb_book)

        # Do some tidying up
        txt = self.tidy_up(txt)

        return txt

    def mlize_spine(self, oeb_book):
        output = [u'']
        for item in oeb_book.spine:
            self.log.debug('Converting %s to Markdown formatted TXT...' % item.href)
            self.rewrite_ids(item.data, item)
            rewrite_links(item.data, partial(self.rewrite_link, page=item))
            stylizer = Stylizer(item.data, item.href, oeb_book, self.opts, self.opts.output_profile)
            output += self.dump_text(item.data.find(XHTML('body')), stylizer)
            output.append('\n\n')
        return ''.join(output)

    def tidy_up(self, text):
        # Remove blank space form beginning of paragraph.
        text = re.sub('(?msu)^[ ]{1,3}', '', text)
        # pre has 4 spaces. We trimmed 3 so anything with a space left is a pre.
        text = re.sub('(?msu)^[ ]', '    ', text)
        
        # Remove tabs that aren't at the beinning of a line
        new_text = []
        for l in text.splitlines():
            start = re.match('\t+', l)
            if start:
                start = start.group()
            else:
                start = ''
            l = re.sub('\t', '', l)
            new_text.append(start + l)
        text = '\n'.join(new_text)
        
        # Remove spaces from blank lines.
        text = re.sub('(?msu)^[ ]+$', '', text)
        
        # Reduce blank lines
        text = re.sub('(?msu)\n{7,}', '\n' * 6, text)
        
        # Remove blank lines at beginning and end of document.
        text = re.sub('^\s*', '', text)
        text = re.sub('\s*$', '\n\n', text)

        return text

    def remove_newlines(self, text):
        text = text.replace('\r\n', ' ')
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')
        # Condense redundant spaces created by replacing newlines with spaces.
        text = re.sub(r'[ ]{2,}', ' ', text)
        text = re.sub(r'\t+', '', text)
        if self.remove_space_after_newline == True:
            text = re.sub(r'^ +', '', text)
            self.remove_space_after_newline = False
        return text

    def prepare_string_for_markdown(self, txt):
        txt = re.sub(r'([\\`*_{}\[\]()#+!])', r'\\\1', txt)
        return txt
    
    def prepare_string_for_pre(self, txt):
        new_text = []
        for l in txt.splitlines():
            new_text.append('    ' + l)
        return '\n'.join(new_text)

    def dump_text(self, elem, stylizer):
        '''
        @elem: The element in the etree that we are working on.
        @stylizer: The style information attached to the element.
        '''

        # We can only processes tags. If there isn't a tag return any text.
        if not isinstance(elem.tag, basestring) \
           or namespace(elem.tag) != XHTML_NS:
            p = elem.getparent()
            if p is not None and isinstance(p.tag, basestring) and namespace(p.tag) == XHTML_NS \
                    and elem.tail:
                return [elem.tail]
            return ['']

        # Setup our variables.
        text = []
        style = stylizer.style(elem)
        tags = []
        tag = barename(elem.tag)
        attribs = elem.attrib
        
        # Ignore anything that is set to not be displayed.
        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            if hasattr(elem, 'tail') and elem.tail:
                return [elem.tail]
            return ['']

        # Soft scene breaks.
        if 'margin-top' in style.cssdict() and style['margin-top'] != 'auto':
            ems = int(round(float(style.marginTop) / style.fontSize) - 1)
            if ems >= 1:
                text.append(u'\n\n' * ems)

        bq = '> ' * self.blockquotes
        # Block level elements
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div'):
            h_tag = ''
            if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                h_tag = '#' * int(tag[1]) + ' '
            text.append('\n' + bq + h_tag)
            tags.append('\n')
            self.remove_space_after_newline = True

        if style['font-style'] == 'italic' or tag in ('i', 'em'):
            if tag not in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'cite'):
                if self.style_italic == False:
                    text.append('*')
                    tags.append('*')
                    self.style_italic = True
        if style['font-weight'] in ('bold', 'bolder') or tag in ('b', 'strong'):
            if tag not in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'th'):
                if self.style_bold == False:
                    text.append('**')
                    tags.append('**')
                    self.style_bold = True
        if tag == 'br':
            text.append('  \n')
            self.remove_space_after_newline = True
        if tag == 'blockquote':
            self.blockquotes += 1
            tags.append('>')
            text.append('> ' * self.blockquotes)
        elif tag == 'code':
            if not self.in_pre and not self.in_code:
                text.append('`')
                tags.append('`')
                self.in_code = True
        elif tag == 'pre':
            if not self.in_pre:
                text.append('\n')
                tags.append('pre')
                self.in_pre = True
        elif tag == 'hr':
            text.append('\n* * *')
            tags.append('\n')
        elif tag == 'a':
            # Only write links with absolute (external) urls.
            if self.opts.keep_links and attribs.has_key('href') and '://' in attribs['href']:
                title = ''
                if attribs.has_key('title'):
                    title = ' "' + attribs['title'] + '"'
                    remove_space = self.remove_space_after_newline
                    title = self.remove_newlines(title)
                    self.remove_space_after_newline = remove_space
                text.append('[')
                tags.append('](' + attribs['href'] + title + ')')
        elif tag == 'img':
            if self.opts.keep_image_references:
                txt = '!'
                if attribs.has_key('alt'):
                    remove_space = self.remove_space_after_newline
                    txt += '[' + self.remove_newlines(attribs['alt']) + ']'
                    self.remove_space_after_newline = remove_space
                txt += '(' + attribs['src'] + ')'
                text.append(txt)
        elif tag in ('ol', 'ul'):
            tags.append(tag)
            # Add the list to our lists of lists so we can track
            # nested lists.
            self.list.append({'name': tag, 'num': 0})
        elif tag == 'li':
            # Get the last list from our list of lists
            if self.list:
                li = self.list[-1]
            else:
                li = {'name': 'ul', 'num': 0}
            # Add a new line to start the item
            text.append('\n')
            # Add indent if we have nested lists.
            list_count = len(self.list)
            # We only care about indenting nested lists.
            if (list_count - 1) > 0:
                text.append('\t' * (list_count - 1))
            # Add blockquote if we have a blockquote in a list item.
            text.append(bq)
            # Write the proper sign for ordered and unorded lists.
            if li['name'] == 'ul':
                text.append('+ ')
            elif li['name'] == 'ol':
                li['num'] += 1
                text.append(unicode(li['num']) + '. ')

        # Process tags that contain text.
        if hasattr(elem, 'text') and elem.text:
            txt = elem.text
            if self.in_pre:
                txt = self.prepare_string_for_pre(txt)
            elif self.in_code:
                txt = self.remove_newlines(txt)
            else:
                txt = self.prepare_string_for_markdown(self.remove_newlines(txt))
            text.append(txt)

        # Recurse down into tags within the tag we are in.
        for item in elem:
            text += self.dump_text(item, stylizer)

        # Close all open tags.
        tags.reverse()
        for t in tags:
            if t in ('pre', 'ul', 'ol', '>'):
                if t == 'pre':
                    self.in_pre = False
                    text.append('\n')
                elif t == '>':
                    self.blockquotes -= 1
                elif t in ('ul', 'ol'):
                    if self.list:
                        self.list.pop()
                    text.append('\n')
            else:
                if t == '**':
                    self.style_bold = False
                elif t == '*':
                    self.style_italic = False
                elif t == '`':
                    self.in_code = False
                text.append('%s' % t)

        # Soft scene breaks.
        if 'margin-bottom' in style.cssdict() and style['margin-bottom'] != 'auto':
            ems = int(round((float(style.marginBottom) / style.fontSize) - 1))
            if ems >= 1:
                text.append(u'\n\n' * ems)

        # Add the text that is outside of the tag.
        if hasattr(elem, 'tail') and elem.tail:
            tail = elem.tail
            if self.in_pre:
                tail = self.prepare_string_for_pre(tail)
            elif self.in_code:
                tail = self.remove_newlines(tail)
            else:
                tail = self.prepare_string_for_markdown(self.remove_newlines(tail))
            text.append(tail)

        return text
