# -*- coding: utf-8 -*-

'''
Convert pml markup to and from html
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re

from calibre.ebooks.pdb.ereader import image_name
from calibre.ebooks.htmlsymbols import HTML_SYMBOLS

from BeautifulSoup import BeautifulSoup

PML_HTML_RULES = [
    (re.compile(r'\\p'), lambda match: '<br /><br style="page-break-after: always;" />'),
    (re.compile(r'\\x(?P<text>.+?)\\x', re.DOTALL), lambda match: '<h1 style="page-break-before: always;">%s</h1>' % match.group('text')),
    (re.compile(r'\\X(?P<val>[0-4])(?P<text>.+?)\\X[0-4]', re.DOTALL), lambda match: '<h%s style="page-break-before: always;">%s</h%s>' % (int(match.group('val')) + 1, match.group('text'), int(match.group('val')) + 1)),
    (re.compile(r'\\C\d=".+"'), lambda match: ''), # This should be made to create a TOC entry
    (re.compile(r'\\c(?P<text>.+?)\\c', re.DOTALL), lambda match: '<div style="text-align: center; display: block; margin: auto;">%s</div>' % match.group('text')),
    (re.compile(r'\\r(?P<text>.+?)\\r', re.DOTALL), lambda match: '<div style="text-align: right; display: block;">%s</div>' % match.group('text')),
    (re.compile(r'\\i(?P<text>.+?)\\i', re.DOTALL), lambda match: '<i>%s</i>' % match.group('text')),
    (re.compile(r'\\u(?P<text>.+?)\\u', re.DOTALL), lambda match: '<div style="text-decoration: underline;">%s</div>' % match.group('text')),
    (re.compile(r'\\o(?P<text>.+?)\\o', re.DOTALL), lambda match: '<del>%s</del>' % match.group('text')),
    (re.compile(r'\\v(?P<text>.+?)\\v', re.DOTALL), lambda match: '<!-- %s -->' % match.group('text')),
    (re.compile(r'\\t(?P<text>.+?)\\t', re.DOTALL), lambda match: '<div style="margin-left: 5%%;">%s</div>' % match.group('text')),
    (re.compile(r'\\T="(?P<val>\d+)%*"(?P<text>.+?)$', re.MULTILINE), lambda match: r'<div style="margin-left: %s%%;">%s</div>' % (match.group('val'), match.group('text'))),
    (re.compile(r'\\w="(?P<val>\d+)%"'), lambda match: '<hr width="%s%%" />' % match.group('val')),
    (re.compile(r'\\n'), lambda match: ''),
    (re.compile(r'\\s'), lambda match: ''),
    (re.compile(r'\\b(?P<text>.+?)\\b', re.DOTALL), lambda match: '<b>%s</b>' % match.group('text')), # \b is deprecated; \B should be used instead.
    (re.compile(r'\\l(?P<text>.+?)\\l', re.DOTALL), lambda match: '<big>%s</big>' % match.group('text')),
    (re.compile(r'\\B(?P<text>.+?)\\B', re.DOTALL), lambda match: '<b>%s</b>' % match.group('text')),
    (re.compile(r'\\Sp(?P<text>.+?)\\Sp', re.DOTALL), lambda match: '<sup>%s</sup>' % match.group('text')),
    (re.compile(r'\\Sb(?P<text>.+?)\\Sb', re.DOTALL), lambda match: '<sub>%s</sub>' % match.group('text')),
    (re.compile(r'\\k(?P<text>.+?)\\k', re.DOTALL), lambda match: '<small>%s</small>' % match.group('text')),
    (re.compile(r'\\a(?P<num>\d\d\d)'), lambda match: '&#%s;' % match.group('num')),
    (re.compile(r'\\U(?P<num>\d+)'), lambda match: '%s' % unichr(int(match.group('num'), 16))),
    (re.compile(r'\\m="(?P<name>.+?)"'), lambda match: '<img src="images/%s" />' % image_name(match.group('name')).strip('\x00')),
    (re.compile(r'\\q="(?P<target>#.+?)"(?P<text>.+?)\\q', re.DOTALL), lambda match: '<a href="%s">%s</a>' % (match.group('target'), match.group('text'))),
    (re.compile(r'\\Q="(?P<target>.+?)"'), lambda match: '<div id="%s"></div>' % match.group('target')),
    (re.compile(r'\\-'), lambda match: ''),
    (re.compile(r'\\Fn="(?P<target>.+?)"(?P<text>.+?)\\Fn'), lambda match: '<a href="#footnote-%s">%s</a>' % (match.group('target'), match.group('text'))),
    (re.compile(r'\\Sd="(?P<target>.+?)"(?P<text>.+?)\\Sd'), lambda match: '<a href="#sidebar-%s">%s</a>' % (match.group('target'), match.group('text'))),
    (re.compile(r'\\I'), lambda match: ''),
    
    # Sidebar and Footnotes
    (re.compile(r'<sidebar\s+id="(?P<target>.+?)">\s*(?P<text>.+?)\s*</sidebar>', re.DOTALL), lambda match: '<div id="sidebar-%s">%s</div>' % (match.group('target'), match.group('text'))),
    (re.compile(r'<footnote\s+id="(?P<target>.+?)">\s*(?P<text>.+?)\s*</footnote>', re.DOTALL), lambda match: '<div id="footnote-%s">%s</div>' % (match.group('target'), match.group('text'))),
    
    # eReader files are one paragraph per line.
    # This forces the lines to wrap properly.
    (re.compile('^(?P<text>.+)$', re.MULTILINE), lambda match: '<p>%s</p>' % match.group('text')),
    (re.compile('<p>[ ]*</p>'), lambda match: ''),
    
    # Remove unmatched plm codes.
    (re.compile(r'(?<=[^\\])\\[pxcriouvtblBk]'), lambda match: ''),
    (re.compile(r'(?<=[^\\])\\X[0-4]'), lambda match: ''),
    (re.compile(r'(?<=[^\\])\\Sp'), lambda match: ''),
    (re.compile(r'(?<=[^\\])\\Sb'), lambda match: ''),
    
    # Replace \\ with \.
    (re.compile(r'\\\\'), lambda match: '\\'),
]

HTML_PML_RULES = [

    (re.compile(r'\\'), lambda match: '\\\\'),
    (re.compile('(?<=[^\n])[ ]*<p.*?>'), lambda match: '\n<p>'),
    (re.compile('</p>(?=^\n|^\r\n)'), lambda match: '\n'),
    
    
    # Clean up HTML
    (re.compile('@page.*?}'), lambda match: ''),
    (re.compile('<script.*?>.*?</script>', re.DOTALL), lambda match: ''),
    (re.compile('<style.*?>.*?</style>', re.DOTALL), lambda match: ''),
    
    # Reflow paragraphs
    (re.compile('<p.*?>(?P<text>.*?)</p>', re.DOTALL), lambda match: match.group('text').replace('\r\n', ' ').replace('\n', ' ')),
    
    # HTML to PML
    (re.compile('<a.*?href="#sidebar-(?P<target>.+?).*?">(?P<text>.+?)</a>'), lambda match: '\\Sd="%s"%s\\Sd' % (match.group('target'), match.group('text'))),
    (re.compile('<a.*?href="#footnote-(?P<target>.+?).*?">(?P<text>.+?)</a>'), lambda match: '\\Fn="%s"%s\\Fn' % (match.group('target'), match.group('text'))),
    (re.compile('<div.*?id="(?P<target>.+?).*?"></div>'), lambda match: '\\\\Q="%s"' % match.group('target')),
    (re.compile('<a.*?href="(?P<target>#.+?).*?">(?P<text>)</a>', re.DOTALL), lambda match: '\\q="%s"%s\\q' % (match.group('target'), match.group('text'))),
    #(re.compile('<img.*?src="images/(?P<name>.+?)".*?>'), lambda match: '\\m="%s"' % match.group('name')),
    (re.compile('<img.*?src="(?P<name>.+?)".*?>(.*?</img>)*'), lambda match: '\\m="%s"' % image_name(match.group('name').strip('\x00'))),
    #(re.compile('&#(?P<num>\d\d\d\d);'), lambda match: '\\U%s' % int(match.group('num'))),
    (re.compile('&#(?P<num>\d\d\d);'), lambda match: '\\a%s' % match.group('num')),
    (re.compile('<small .*?>(?P<text>.+?)</small>', re.DOTALL), lambda match: '\\k%s\\k' % match.group('text')),
    (re.compile('<small>(?P<text>.+?)</small>', re.DOTALL), lambda match: '\\k%s\\k' % match.group('text')),
    (re.compile('<sub .*?>(?P<text>.+?)</sub>', re.DOTALL), lambda match: '\\Sb%s\\Sb' % match.group('text')),
    (re.compile('<sub>(?P<text>.+?)</sub>', re.DOTALL), lambda match: '\\Sb%s\\Sb' % match.group('text')),
    (re.compile('<sup .*?>(?P<text>.+?)</sup>', re.DOTALL), lambda match: '\\Sp%s\\Sp' % match.group('text')),
    (re.compile('<sup>(?P<text>.+?)</sup>', re.DOTALL), lambda match: '\\Sp%s\\Sp' % match.group('text')),
    (re.compile('<b .*?>(?P<text>.+?)</b>', re.DOTALL), lambda match: '\\B%s\\B' % match.group('text')),
    (re.compile('<b>(?P<text>.+?)</b>', re.DOTALL), lambda match: '\\B%s\\B' % match.group('text')),
    (re.compile('<strong .*?>(?P<text>.+?)</strong>', re.DOTALL), lambda match: '\\B%s\\B' % match.group('text')),
    (re.compile('<strong>(?P<text>.+?)</strong>', re.DOTALL), lambda match: '\\B%s\\B' % match.group('text')),
    (re.compile('<big .*?>(?P<text>.+?)</big>', re.DOTALL), lambda match: '\\l%s\\l' % match.group('text')),
    (re.compile('<big>(?P<text>.+?)</big>', re.DOTALL), lambda match: '\\l%s\\l' % match.group('text')),
    (re.compile('<hr.*?width="(?P<val>\d+)%".*?>'), lambda match: '\\w="%s%%"' % match.group('val')),
    (re.compile('<div.*?style.*?margin-left: (?P<val>\d+)%*;.*?>(?P<text>.+?)</div>', re.MULTILINE), lambda match: '\\T="%s%%"%s$' % (match.group('val'), match.group('text'))),
    (re.compile('<div.*?style.*?margin-left: \d{1,3}%;.*?>(?P<text>.+?)</div>', re.DOTALL), lambda match: '\\t%s\\t' % match.group('text')),
    (re.compile('<!--(?P<text>.+?)-->', re.DOTALL), lambda match: '\\v%s\\v' % match.group('text')),
    (re.compile('<del .*?>(?P<text>.+?)</del>', re.DOTALL), lambda match: '\\o%s\\o' % match.group('text')),
    (re.compile('<del>(?P<text>.+?)</del>', re.DOTALL), lambda match: '\\o%s\\o' % match.group('text')),
    (re.compile('<div.*?style.*?text-decoration: underline;.*?>(?P<text>.+?)</div>', re.DOTALL), lambda match: '\\u%s\\u' % match.group('text')),
    (re.compile('<i .*?>(?P<text>.+?)</i>', re.DOTALL), lambda match: '\\\\i%s\\i' % match.group('text')),
    (re.compile('<i>(?P<text>.+?)</i>', re.DOTALL), lambda match: '\\\\i%s\\i' % match.group('text')),
    (re.compile('<div.*?style.*?text-align: right;.*?>(?P<text>.+?)</div>', re.DOTALL), lambda match: '\\r%s\\r' % match.group('text')),
    (re.compile('<div.*?style.*?text-align: center;.*?".*?>(?P<text>.+?)</div>', re.DOTALL), lambda match: '\\c%s\\c' % match.group('text')),
    (re.compile('<h(?P<val>[0-4]).*?>(?P<text>.+?)</h[0-4]>', re.DOTALL), lambda match: '\\X%s%s\\X%s' % (int(match.group('val')) + 1, match.group('text'), int(match.group('val')) + 1)),
    (re.compile('<h1.*?>(?P<text>.+?)</h1>', re.DOTALL), lambda match: '\\x%s\\x' % match.group('text')),
    (re.compile('<br .*?>'), lambda match: '\n'),
    (re.compile('<br/*>'), lambda match: '\n'),
    
    # Remove remaining HTML tags
    (re.compile('<.*?>'), lambda match: ''),
    
    # Remove redundant page break markers
    (re.compile(r'(\\p){2,}'), lambda match: r'\p'),
    
    # Remove whitespace on empty lines
    (re.compile('^[\t\r ]$', re.MULTILINE), lambda match: ''),
    # Remove excess whitespace in lines
    (re.compile('(?<=.)[ ]{2,}(?=.)'), lambda match: ' '),
    
    # Remove excess newlines at the beginning and end
    (re.compile('^(\r\n){1,}'), lambda match: ''),
    (re.compile('^\n{1,}'), lambda match: ''),
    (re.compile('(\r\n){3,}$'), lambda match: ''),
    (re.compile('\n{3,}$'), lambda match: ''),
]

def pml_to_html(pml):
    html = pml
    for rule in PML_HTML_RULES:
        html = rule[0].sub(rule[1], html)

    for symbol in HTML_SYMBOLS.keys():
        if ord(symbol) > 128:
            html = html.replace(symbol, HTML_SYMBOLS[symbol][len(HTML_SYMBOLS[symbol]) - 1])
        
    return html

def footnote_sidebar_to_html(id, pml):
    html = '<div id="sidebar-%s"><dt>%s</dt></div><dd>%s</dd>' % (id, id, pml_to_html(pml))
    return html 

def html_to_pml(html):
    pml = ''
    
    for dom_tree in BeautifulSoup(html).findAll('body'):
        body = unicode(dom_tree.prettify())

        for rule in HTML_PML_RULES:
            body = rule[0].sub(rule[1], body)
            
        pml += body
    
    # Replace symbols outside of cp1512 wtih \Uxxxx

    return pml
