# -*- coding: utf-8 -*-

# Copyright (c) 2010, Webreactor - Marcin Lulek <info@webreactor.eu>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#    * Redistributions of source code must retain the above copyright
#      notice, this list of conditions and the following disclaimer.
#    * Redistributions in binary form must reproduce the above copyright
#      notice, this list of conditions and the following disclaimer in the
#      documentation and/or other materials provided with the distribution.
#    * Neither the name of the <organization> nor the
#      names of its contributors may be used to endorse or promote products
#      derived from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL <COPYRIGHT HOLDER> BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


from lxml import etree
from calibre.ebooks.oeb.base import barename

class EchoTarget:

    def __init__(self):
        self.final_output = []
        self.block = False
        self.ol_ident = 0
        self.ul_ident = 0
        self.list_types = []
        self.haystack = []

    def start(self, tag, attrib):
        tag = barename(tag)

        newline = '\n'
        dot = ''
        new_tag = ''

        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            new_tag = tag
            dot = '. '
        elif tag == 'p':
                new_tag = ''
                dot = ''
        elif tag == 'blockquote':
            new_tag = 'bq'
            dot = '. '
        elif tag in ('b', 'strong'):
            new_tag = '*'
            newline = ''
        elif tag in ('em', 'i'):
            new_tag = '_'
            newline = ''
        elif tag == 'cite':
            new_tag = '??'
            newline = ''
        elif tag == 'del':
            new_tag = '-'
            newline = ''
        elif tag == 'ins':
            new_tag = '+'
            newline = ''
        elif tag == 'sup':
            new_tag = '^'
            newline = ''
        elif tag == 'sub':
            new_tag = '~'
            newline = ''
        elif tag == 'span':
            new_tag = '%'
            newline = ''
        elif tag == 'a':
            self.block = True
            if 'title' in attrib:
                self.a_part = {'title':attrib.get('title'),
                               'href':attrib.get('href', '')}
            else:
                self.a_part = {'title':None, 'href':attrib.get('href', '')}
            new_tag = ''
            newline = ''

        elif tag == 'img':
            if 'alt' in attrib:
                new_tag = ' !%s(%s)' % (attrib.get('src'), attrib.get('title'),)
            else:
                new_tag = ' !%s' % attrib.get('src')
            newline = ''

        elif tag in ('ul', 'ol'):
            new_tag = ''
            newline = ''
            self.list_types.append(tag)
            if tag == 'ul':
                self.ul_ident += 1
            else:
                self.ol_ident += 1

        elif tag == 'li':
            indent = self.ul_ident + self.ol_ident
            if self.list_types[-1] == 'ul':
                new_tag = '*' * indent + ' '
                newline = '\n'
            else:
                new_tag = '#' * indent + ' '
                newline = '\n'


        if tag not in ('ul', 'ol'):
            textile = '%(newline)s%(tag)s%(dot)s' % \
                                 {
                                  'newline':newline,
                                  'tag':new_tag,
                                  'dot':dot
                                  }
            if not self.block:
                self.final_output.append(textile)
            else:
                self.haystack.append(textile)

    def end(self, tag):
        tag = barename(tag)

        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p'):
            self.final_output.append('\n')
        elif tag in ('b', 'strong'):
            self.final_output.append('*')
        elif tag in ('em', 'i'):
            self.final_output.append('_')
        elif tag == 'cite':
            self.final_output.append('??')
        elif tag == 'del':
            self.final_output.append('-')
        elif tag == 'ins':
            self.final_output.append('+')
        elif tag == 'sup':
            self.final_output.append('^')
        elif tag == 'sub':
            self.final_output.append('~')
        elif tag == 'span':
            self.final_output.append('%')
        elif tag == 'a':
            if self.a_part['title']:
                textilized = ' "%s (%s)":%s ' % (
                                                 ''.join(self.haystack),
                                                 self.a_part.get('title'),
                                                 self.a_part.get('href'),
                                                 )
                self.haystack = []
            else:
                textilized = ' "%s":%s ' % (
                                                 ''.join(self.haystack),
                                                 self.a_part.get('href'),
                                                 )
                self.haystack = []
            self.final_output.append(textilized)
            self.block = False
        elif tag == 'img':
            self.final_output.append('!')
        elif tag == 'ul':
            self.ul_ident -= 1
            self.list_types.pop()
            if len(self.list_types) == 0:
                self.final_output.append('\n')
        elif tag == 'ol':
            self.ol_ident -= 1
            self.list_types.pop()
            if len(self.list_types) == 0:
                self.final_output.append('\n')

    def data(self, data):
        #we dont want any linebreaks inside our tags
        node_data = data.replace('\n','')
        if not self.block:
            self.final_output.append(node_data)
        else:
            self.haystack.append(node_data)

    def comment(self, text):
        pass

    def close(self):
        return "closed!"


def html2textile(html):
    #1st pass
    #clean the whitespace and convert html to xhtml
    parser = etree.HTMLParser()
    tree = etree.fromstring(html, parser)
    xhtml = etree.tostring(tree, method="xml")
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.XML(xhtml, parser)
    cleaned_html = etree.tostring(root)
    #2nd pass build textile
    target = EchoTarget()
    parser = etree.XMLParser(target=target)
    root = etree.fromstring(cleaned_html, parser)
    textilized_text = ''.join(target.final_output).lstrip().rstrip()
    return textilized_text
