"""
Attribute List Extension for Python-Markdown
============================================

Adds attribute list syntax. Inspired by 
[maruku](http://maruku.rubyforge.org/proposal.html#attribute_lists)'s
feature of the same name.

Copyright 2011 [Waylan Limberg](http://achinghead.com/).

Contact: markdown@freewisdom.org

License: BSD (see ../LICENSE.md for details) 

Dependencies:
* [Python 2.4+](http://python.org)
* [Markdown 2.1+](http://packages.python.org/Markdown/)

"""

from __future__ import absolute_import
from __future__ import unicode_literals
from . import Extension
from ..treeprocessors import Treeprocessor
from ..util import isBlockLevel
import re

try:
    Scanner = re.Scanner
except AttributeError:
    # must be on Python 2.4
    from sre import Scanner

def _handle_double_quote(s, t):
    k, v = t.split('=')
    return k, v.strip('"')

def _handle_single_quote(s, t):
    k, v = t.split('=')
    return k, v.strip("'")

def _handle_key_value(s, t): 
    return t.split('=')

def _handle_word(s, t):
    if t.startswith('.'):
        return '.', t[1:]
    if t.startswith('#'):
        return 'id', t[1:]
    return t, t

_scanner = Scanner([
    (r'[^ ]+=".*?"', _handle_double_quote),
    (r"[^ ]+='.*?'", _handle_single_quote),
    (r'[^ ]+=[^ ]*', _handle_key_value),
    (r'[^ ]+', _handle_word),
    (r' ', None)
])

def get_attrs(str):
    """ Parse attribute list and return a list of attribute tuples. """
    return _scanner.scan(str)[0]

def isheader(elem):
    return elem.tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']

class AttrListTreeprocessor(Treeprocessor):
    
    BASE_RE = r'\{\:?([^\}]*)\}'
    HEADER_RE = re.compile(r'[ ]*%s[ ]*$' % BASE_RE)
    BLOCK_RE = re.compile(r'\n[ ]*%s[ ]*$' % BASE_RE)
    INLINE_RE = re.compile(r'^%s' % BASE_RE)
    NAME_RE = re.compile(r'[^A-Z_a-z\u00c0-\u00d6\u00d8-\u00f6\u00f8-\u02ff\u0370-\u037d'
                         r'\u037f-\u1fff\u200c-\u200d\u2070-\u218f\u2c00-\u2fef'
                         r'\u3001-\ud7ff\uf900-\ufdcf\ufdf0-\ufffd'
                         r'\:\-\.0-9\u00b7\u0300-\u036f\u203f-\u2040]+')

    def run(self, doc):
        for elem in doc.getiterator():
            if isBlockLevel(elem.tag):
                # Block level: check for attrs on last line of text
                RE = self.BLOCK_RE
                if isheader(elem):
                    # header: check for attrs at end of line
                    RE = self.HEADER_RE
                if len(elem) and elem[-1].tail:
                    # has children. Get from tail of last child
                    m = RE.search(elem[-1].tail)
                    if m:
                        self.assign_attrs(elem, m.group(1))
                        elem[-1].tail = elem[-1].tail[:m.start()]
                        if isheader(elem):
                            # clean up trailing #s
                            elem[-1].tail = elem[-1].tail.rstrip('#').rstrip()
                elif elem.text:
                    # no children. Get from text.
                    m = RE.search(elem.text)
                    if m:
                        self.assign_attrs(elem, m.group(1))
                        elem.text = elem.text[:m.start()]
                        if isheader(elem):
                            # clean up trailing #s
                            elem.text = elem.text.rstrip('#').rstrip()
            else:
                # inline: check for attrs at start of tail
                if elem.tail:
                    m = self.INLINE_RE.match(elem.tail)
                    if m:
                        self.assign_attrs(elem, m.group(1))
                        elem.tail = elem.tail[m.end():]

    def assign_attrs(self, elem, attrs):
        """ Assign attrs to element. """
        for k, v in get_attrs(attrs):
            if k == '.':
                # add to class
                cls = elem.get('class')
                if cls:
                    elem.set('class', '%s %s' % (cls, v))
                else:
                    elem.set('class', v)
            else:
                # assign attr k with v
                elem.set(self.sanitize_name(k), v)

    def sanitize_name(self, name):
        """
        Sanitize name as 'an XML Name, minus the ":"'.
        See http://www.w3.org/TR/REC-xml-names/#NT-NCName
        """
        return self.NAME_RE.sub('_', name)


class AttrListExtension(Extension):
    def extendMarkdown(self, md, md_globals):
        md.treeprocessors.add('attr_list', AttrListTreeprocessor(md), '>prettify')


def makeExtension(configs={}):
    return AttrListExtension(configs=configs)
