# -*- coding: utf-8 -*-

__license__ = 'GPL 3'
__copyright__ = '2011, Leigh Parry <leighparry@blueyonder.co.uk>'
__docformat__ = 'restructuredtext en'

'''
Transform OEB content into Textile formatted plain text
'''
import re

from functools import partial

from calibre.ebooks.htmlz.oeb2html import OEB2HTML
from calibre.ebooks.oeb.base import XHTML, XHTML_NS, barename, namespace, rewrite_links
from calibre.ebooks.oeb.stylizer import Stylizer
from calibre.ebooks.txt.unsmarten import unsmarten

class TextileMLizer(OEB2HTML):

    def extract_content(self, oeb_book, opts):
        self.log.info('Converting XHTML to Textile formatted TXT...')
        self.opts = opts
        self.in_pre = False
        self.in_table = False
        self.links = {}
        self.list = []
        self.our_links = []
        self.in_a_link = False
        self.our_ids = []
        self.images = {}
        self.id_no_text = u''
        self.style_embed = []
        self.remove_space_after_newline = False
        self.base_hrefs = [item.href for item in oeb_book.spine]
        self.map_resources(oeb_book)

        self.style_bold = False
        self.style_italic = False
        self.style_under = False
        self.style_strike = False
        self.style_smallcap = False

        txt = self.mlize_spine(oeb_book)
        txt = unsmarten(txt)

        # Do some tidying up
        txt = self.tidy_up(txt)

        return txt

    def mlize_spine(self, oeb_book):
        output = [u'']
        for item in oeb_book.spine:
            self.log.debug('Converting %s to Textile formatted TXT...' % item.href)
            self.rewrite_ids(item.data, item)
            rewrite_links(item.data, partial(self.rewrite_link, page=item))
            stylizer = Stylizer(item.data, item.href, oeb_book, self.opts)
            output += self.dump_text(item.data.find(XHTML('body')), stylizer)
            output.append('\n\n')
        return ''.join(output)

    def tidy_up(self, text):
        # Needs tweaking and finetuning
        def check_escaping(text, tests):
            for t in tests:
                # I'm not checking for duplicated spans '%' as any that follow each other were being incorrectly merged
                txt = '%s' % t
                self.log.debug('DEBUG: ' + txt)
                if txt != '%':
                    text = re.sub(r'(\S)'+t+t+'(\S)', r'\1\2', text)
                text = re.sub(r'(\w)('+t+'\w+'+t+')', r'\1[\2]', text)
                text = re.sub(r'('+t+'\w+'+t+')(\w)', r'[\1]\2', text)
            return text

        # Now tidyup links and ids - remove ones that don't have a correponding opposite
        if self.opts.keep_links:
            for i in self.our_links:
                if i[0] == '#':
                    if i not in self.our_ids:
                        text = re.sub(r'"(.+)":'+i, '\1', text)
            for i in self.our_ids:
                if i not in self.our_links:
                    text = re.sub(r'\('+i+'\)', '', text)
                    
        # Note - I'm not checking for escaped '-' as this will also get hypenated words
        text = check_escaping(text, ['\^', '\*', '_', '\+', '~', '%'])

        text = re.sub(r'%\xa0+', r'%', text)                            #remove empty spans
        text = re.sub(r'%%', r'', text)                                 #remove empty spans
        text = re.sub(r'%([_+*-]+)%', r'\1', text)                      #remove spans from tagged output
        text = re.sub(r' +\n', r'\n', text)                             #remove spaces before a newline
        text = re.sub(r'^\n+', r'', text)                               #remove newlines at top of file
        text = re.sub(r'\npre\.\n?\nbc\.', r'\nbc.', text)              #correct blockcode paras
        text = re.sub(r'\nbq\.\n?\np.*\. ', r'\nbq. ', text)            #correct blockquote paras
#        text = re.sub(r'\n{4,}', r'\n\np. \n\n', text)                  #reduce blank lines + insert blank para
        text = re.sub(r'\n{3}', r'\n\n', text)                          #reduce blank lines
        text = re.sub(u'%\n(p[<>=]{1,2}\.)', r'%\n\n\1', text)
        text = re.sub(u'p[<>=]{1,2}\.\n\n?', r'', text)
        text = re.sub(r'\n(p.*\.\n)(p.*\.)', r'\n\2', text)
        text = re.sub(u'\np.*\.\xa0',   r'\np. ', text)                # blank paragraph
        text = re.sub(u'\n\xa0',   r'\np. ', text)                     # blank paragraph
        text = re.sub(r' {2,}\|', r' |', text)                               #sort out spaces in tables
        # Now put back spaces removed earlier as they're needed here
        text = re.sub(r'\np\.\n', r'\np. \n', text)
        text = re.sub(r' \n\n\n', r' \n\n', text)                          #reduce blank lines
        
        # started work on trying to fix footnotes
#        text = re.sub(r'\[\^"(\d+)":#.+\^\]', r'[\1]', text)
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

    def check_styles(self, style):
        txt = '{'
        if style['color'] and style['color'] != 'black':
            txt += 'color:'+style['color']+';'
        try:
            if style['background']:
                txt += 'background:'+style['background']+';'
        except:
            pass
        txt += '}'
        if txt == '{}': txt = ''
        return txt

    def check_halign(self, style):
        tests = {'left':'<','justify':'<>','center':'=','right':'>'}
        for i in tests:
            if style['text-align'] == i:
                return tests[i]
        return ''

    def check_valign(self, style):
        tests = {'top':'^','bottom':'~'} #, 'middle':'-'}
        for i in tests:
            if style['vertical-align'] == i:
                return tests[i]
        return ''

    def check_padding(self, style, tests):
        txt = ''
        for i in tests:
            try:
                ems = int(round(float(style[i[0]] / style['font-size'])))
                if ems >=1:
                    txt += i[1] * ems
            except:
                pass
        return txt

    def check_id_tag(self, attribs):
        txt = ''
        if attribs.has_key('id'): # and attribs['id'] in self.links.values():
            txt = '(#'+attribs['id']+ ')'
            self.our_ids.append('#'+attribs['id'])
            self.id_no_text = u'\xa0'
        return txt

    def build_block(self, tag, style, attribs):
        txt = '\n' + tag
        if self.opts.keep_links:
            txt += self.check_id_tag(attribs)
        txt += self.check_padding(style, [['padding-left','('],['padding-right',')']])
        txt += self.check_halign(style)
        txt += self.check_styles(style)
        return txt

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
        text = ['']
        style = stylizer.style(elem)
        tags = []
        tag = barename(elem.tag)
        attribs = elem.attrib
        
        # Ignore anything that is set to not be displayed.
        if style['display'] in ('none', 'oeb-page-head', 'oeb-page-foot') \
           or style['visibility'] == 'hidden':
            return ['']

        # Soft scene breaks.
        text.append(self.check_padding(style, ['margin-top',u'\n\n\xa0']))

        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div'):
            if tag == 'div':
                tag = 'p'
            block = self.build_block(tag, style, attribs)
            # Normal paragraph with no styling.
            if block == '\np':
                text.append('\n\n')
                tags.append('\n')
            else:
                text.append(block)
                text.append('. ')
                tags.append('\n')
            #self.style_embed = []

        if style['font-style'] == 'italic' or tag in ('i', 'em'):
            if tag not in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'cite'):
                if self.style_italic == False:
                    text.append('_')
                    tags.append('_')
                    self.style_embed.append ('_')
                    self.style_italic = True
        if style['font-weight'] in ('bold', 'bolder') or tag in ('b', 'strong'):
            if tag not in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'th'):
                if self.style_bold == False:
                    text.append('*')
                    tags.append('*')
                    self.style_embed.append ('*')
                    self.style_bold = True
        if style['text-decoration'] == 'underline' or tag in ('u', 'ins'):
            if tag != 'a':
                if self.style_under == False:
                    text.append('+')
                    tags.append('+')
                    self.style_embed.append ('+')
                    self.style_under = True
        if style['text-decoration'] == 'line-through' or tag in ('strike', 'del', 's'):
            if self.style_strike == False:
                text.append('-')
                tags.append('-')
                self.style_embed.append ('-')
                self.style_strike = True
        if tag == 'br':
            for i in reversed(self.style_embed):
                text.append(i)
            text.append('\n')
            for i in self.style_embed:
                text.append(i)
            tags.append('')
            self.remove_space_after_newline = True
        if tag == 'blockquote':
            text.append('\nbq. ')
            tags.append('\n')
        elif tag in ('abbr', 'acronym'):
            text.append('')
            txt = attribs['title']
            tags.append('(' + txt + ')')
        elif tag == 'sup':
            text.append('^')
            tags.append('^')
        elif tag == 'sub':
            text.append('~')
            tags.append('~')
        elif tag == 'code':
            if self.in_pre:
                text.append('\nbc. ')
                tags.append('')
            else:
                text.append('@')
                tags.append('@')
        elif tag == 'cite':
            text.append('??')
            tags.append('??')
        elif tag == 'hr':
            text.append('\n***')
            tags.append('\n')
        elif tag == 'pre':
            self.in_pre = True
            text.append('\npre. ')
            tags.append('pre\n')
        elif tag == 'a':
            if self.opts.keep_links:
                text.append('"')
                tags.append('a')
                if attribs.has_key('href'):
                    tags.append('":' + attribs['href'])
                    self.our_links.append(attribs['href'])
                if attribs.has_key('title'):
                    tags.append('(' + attribs['title'] + ')')
                self.in_a_link = True
        elif tag == 'img':
            if self.opts.keep_image_references:
                txt = '!' + self.check_halign(style)
                txt += self.check_valign(style)
                txt += attribs['src']
                text.append(txt)
                if attribs.has_key('alt'):
                    txt = attribs['alt']
                    if txt != '':
                        text.append('(' + txt + ')')
                tags.append('!')
        elif tag in ('ol', 'ul'):
            self.list.append({'name':tag, 'num':0})
            text.append('')
            tags.append(tag)
        elif tag == 'li':
            if self.list: li = self.list[-1]
            else: li = {'name':'ul', 'num':0}
            text.append('\n')
            if   li['name'] == 'ul': text.append('*'*len(self.list)+' ')
            elif li['name'] == 'ol': text.append('#'*len(self.list)+' ')
            tags.append('')
        elif tag == 'dl':
            text.append('\n')
            tags.append('')
        elif tag == 'dt':
            text.append('')
            tags.append('\n')
        elif tag == 'dd':
            text.append('    ')
            tags.append('')
        elif tag == 'dd':
            text.append('')
            tags.append('\n')
        elif tag == 'table':
            txt = self.build_block(tag, style, attribs)
            txt += '. \n'
            if txt != '\ntable. \n':
                text.append(txt)
            else:
                text.append('\n')
            tags.append('')
        elif tag == 'tr':
            txt = self.build_block('', style, attribs)
            txt += '. '
            if txt != '\n. ':
                txt = re.sub ('\n','',txt)
                text.append(txt)
            tags.append('|\n')
        elif tag == 'td':
            text.append('|')
            txt = ''
            txt += self.check_halign(style)
            txt += self.check_valign(style)
            if attribs.has_key ('colspan'):
                txt += '\\' + attribs['colspan']
            if attribs.has_key ('rowspan'):
                txt += '/' + attribs['rowspan']
            try:
                txt += self.check_styles(style)
            except:
                pass
            if txt != '':
                text.append(txt+'. ')
            tags.append('')
        elif tag == 'th':
            text.append('|_. ')
            tags.append('')
        elif tag == 'span':
            if style['font-variant'] == 'small-caps':
                if self.style_smallcap == False:
                    text.append('&')
                    tags.append('&')
                    self.style_smallcap = True
            else:
                if self.in_a_link == False:
                    txt = '%'
                    if self.opts.keep_links:
                        txt += self.check_id_tag(attribs)
                        txt += self.check_styles(style)
                    if txt != '%':
                        text.append(txt)
                        tags.append('%')

        if self.opts.keep_links and attribs.has_key('id'):
            if tag not in ('body', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'table'):
                text.append(self.check_id_tag(attribs))

        # Process the styles for any that we want to keep
        if tag not in ('body', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'hr', 'a', 'img', \
                'span', 'table', 'tr', 'td'):
            if not self.in_a_link:
                text.append(self.check_styles(style))
        
        # Process tags that contain text.
        if hasattr(elem, 'text') and elem.text:
            txt = elem.text
            if not self.in_pre:
                txt = self.remove_newlines(txt)
            text.append(txt)
            self.id_no_text = u''

        # Recurse down into tags within the tag we are in.
        for item in elem:
            text += self.dump_text(item, stylizer)

        # Close all open tags.
        tags.reverse()
        for t in tags:
            if tag in ('pre', 'ul', 'ol', 'li', 'table'):
                if tag == 'pre':
                    self.in_pre = False
                elif tag in ('ul', 'ol'):
                    if self.list: self.list.pop()
                    if not self.list: text.append('\n')
            else:
                if t == 'a':
                    self.in_a_link = False
                    t = ''
                text.append(self.id_no_text)
                self.id_no_text = u''
                if t == '*':
                    self.style_bold = False
                elif t == '_':
                    self.style_italic = False
                elif t == '+':
                    self.style_under = False
                elif t == '-':
                    self.style_strike = False
                elif t == '&':
                    self.style_smallcap = False
                if t in ('*', '_', '+', '-'):
                    txt = self.style_embed.pop()
                    text.append(txt)
                else:
                    text.append('%s' % t)

        # Soft scene breaks.
        text.append(self.check_padding(style, ['margin-bottom',u'\n\n\xa0']))

        # Add the text that is outside of the tag.
        if hasattr(elem, 'tail') and elem.tail:
            tail = elem.tail
            if not self.in_pre:
                tail = self.remove_newlines(tail)
            text.append(tail)

        return text
