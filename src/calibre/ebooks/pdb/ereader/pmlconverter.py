# -*- coding: utf-8 -*-
from __future__ import with_statement
'''
Convert pml markup to and from html
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re

from calibre.ebooks.htmlsymbols import HTML_SYMBOLS

PML_HTML_RULES = [
    (re.compile('\\\\p'), lambda match: '<br /><br style="page-break-after: always;" />'),
    (re.compile('\\\\x(?P<text>.+?)\\\\x', re.DOTALL), lambda match: '<h1 style="page-break-before: always;">%s</h1>' % match.group('text')),
    (re.compile('\\\\X(?P<val>[0-4])(?P<text>.+?)\\\\X[0-4]', re.DOTALL), lambda match: '<h%i style="page-break-before: always;">%i</h%i>' % (int(match.group('val')) + 1, match.group('text'), int(match.group('val')) + 1)),
    (re.compile('\\\\C\d=".+"'), lambda match: ''), # This should be made to create a TOC entry
    (re.compile('\\\\c(?P<text>.+?)\\\\c', re.DOTALL), lambda match: '<div style="text-align: center; display: block; margin: auto;">%s</div>' % match.group('text')),
    (re.compile('\\\\r(?P<text>.+?)\\\\r', re.DOTALL), lambda match: '<div style="text-align: right; display: block;">%s</div>' % match.group('text')),
    (re.compile('\\\\i(?P<text>.+?)\\\\i', re.DOTALL), lambda match: '<i>%s</i>' % match.group('text')),
    (re.compile('\\\\u(?P<text>.+?)\\\\u', re.DOTALL), lambda match: '<div style="text-decoration: underline;">%s</div>' % match.group('text')),
    (re.compile('\\\\o(?P<text>.+?)\\\\o', re.DOTALL), lambda match: '<del>%s</del>' % match.group('text')),
    (re.compile('\\\\v(?P<text>.+?)\\\\v', re.DOTALL), lambda match: '<!-- %s -->' % match.group('text')),
    (re.compile('\\\\t(?P<text>.+?)\\\\t', re.DOTALL), lambda match: '<div style="margin-left: 5%%">%s</div>' % match.group('text')),
    (re.compile('\\\\T="(?P<val>\d+%*)"(?P<text>.+?)$', re.MULTILINE), lambda match: '<div style="margin-left: %i%">%s</div>' % (match.group('val'), match.group('text'))),
    (re.compile('\\\\w="(?P<val>\d+)%"'), lambda match: '<hr width="%s%%" />' % match.group('val')),
    (re.compile('\\\\n'), lambda match: ''),
    (re.compile('\\\\s'), lambda match: ''),
    (re.compile('\\\\b(?P<text>.+?)\\\\b', re.DOTALL), lambda match: '<b>%s</b>' % match.group('text')), # \b is deprecated; \B should be used instead.
    (re.compile('\\\\l(?P<text>.+?)\\\\l', re.DOTALL), lambda match: '<big>%s</big>' % match.group('text')),
    (re.compile('\\\\B(?P<text>.+?)\\\\B', re.DOTALL), lambda match: '<b>%s</b>' % match.group('text')),
    (re.compile('\\\\Sp(?P<text>.+?)\\\\Sp', re.DOTALL), lambda match: '<sup>%s</sup>' % match.group('text')),
    (re.compile('\\\\Sb(?P<text>.+?)\\\\Sb', re.DOTALL), lambda match: '<sub>%s</sub>' % match.group('text')),
    (re.compile('\\\\k(?P<text>.+?)\\\\k', re.DOTALL), lambda match: '<small>%s</small>' % match.group('text')),
    (re.compile('\\\\a(?P<num>\d\d\d)'), lambda match: '&#%s;' % match.group('num')),
    (re.compile('\\\\U(?P<num>\d\d\d\d)'), lambda match: '&#%i;' % int(match.group('num'))),
    (re.compile('\\\\m="(?P<name>.+?)"'), lambda match: '<img src="images/%s" />' % match.group('name')),
    (re.compile('\\\\q="(?P<target>#.+?)"(?P<text>)\\\\q', re.DOTALL), lambda match: '<a href="%s">%s</a>' % (match.group('target'), match.group('text'))),
    (re.compile('\\\\Q="(?P<target>.+?)"'), lambda match: '<div id="%s"></div>' % match.group('target')),
    (re.compile('\\\\-'), lambda match: ''),
    (re.compile('\\\\Fn="(?P<target>.+?)"(?P<text>.+?)\\\\Fn'), lambda match: '<a href="#footnote-%s">%s</a>' % (match.group('target'), match.group('text'))),
    (re.compile('\\\\Sd="(?P<target>.+?)"(?P<text>.+?)\\\\Sd'), lambda match: '<a href="#sidebar-%s">%s</a>' % (match.group('target'), match.group('text'))),
    (re.compile('\\\\I'), lambda match: ''),
    
    # eReader files are one paragraph per line.
    # This forces the lines to wrap properly.
    (re.compile('^(?P<text>.+)$', re.MULTILINE), lambda match: '<p>%s</p>' % match.group('text')),
    
    # Remove unmatched plm codes.
    (re.compile('(?<=[^\\\\])\\\\[pxcriouvtblBk]'), lambda match: ''),
    (re.compile('(?<=[^\\\\])\\\\X[0-4]'), lambda match: ''),
    (re.compile('(?<=[^\\\\])\\\\Sp'), lambda match: ''),
    (re.compile('(?<=[^\\\\])\\\\Sb'), lambda match: ''),
    
    # Replace \\ with \.
    (re.compile('\\\\\\\\'), lambda match: '\\'),
]

FOOTNOTE_HTML_RULES = [
    (re.compile('<footnote id="(?P<id>.+?)">(?P<text>.+?)</footnote>', re.DOTALL), lambda match: '<div id="footnote-%s">%s</div>')
]

SIDEBAR_HTML_RULES = [
    (re.compile('<sidebar id="(?P<id>.+?)">(?P<text>.+?)</sidebar>', re.DOTALL), lambda match: '<div id="sidebar-%s">%s</div>')
]


def pml_to_html(pml):
    html = pml
    for rule in PML_HTML_RULES:
        html = rule[0].sub(rule[1], html)

    for symbol in HTML_SYMBOLS.keys():
        if ord(symbol) > 128:
            html = html.replace(symbol, HTML_SYMBOLS[symbol][len(HTML_SYMBOLS[symbol]) - 1])
        
    return html

def footnote_to_html(footnotes):
    html = footnotes
    for rule in FOOTNOTE_HTML_RULES:
        html = rule[0].sub(rule[1], html)
        
    html = pml_to_html(html)
        
    return html
    
def sidebar_to_html(sidebars):
    html = sidebars
    for rule in FOOTNOTE_HTML_RULES:
        html = rule[0].sub(rule[1], html)
        
    html = pml_to_html(html)
        
    return html
