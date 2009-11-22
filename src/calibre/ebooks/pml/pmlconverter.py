# -*- coding: utf-8 -*-

'''
Convert pml markup to and from html
'''

__license__   = 'GPL v3'
__copyright__ = '2009, John Schember <john@nachtimwald.com>'
__docformat__ = 'restructuredtext en'

import re

from calibre import my_unichr, prepare_string_for_xml
from calibre.ebooks.pdb.ereader import image_name

PML_HTML_RULES = [
    # NOP-process all \x escapes, turning \\ into &#92;  This keeps the regex
    # parsing simple while making sure that we don't try to honor \\x as \x
    # (and also makes sure we DO honor \\\x as &#92; followed by \x).
    (re.compile(r'\\(.)'), lambda match: '&#92;' if match.group(1) == '\\' else '\\' + match.group(1)),

    (re.compile(r'\\p'), lambda match: '<br /><br style="page-break-after: always;" />'),
    (re.compile(r'\\x(?P<text>.*?)\\x', re.DOTALL), lambda match: '<h1 style="page-break-before: always;">%s</h1>' % match.group('text') if match.group('text') else ''),
    (re.compile(r'\\X(?P<val>[0-4])(?P<text>.*?)\\X[0-4]', re.DOTALL), lambda match: '<h%s>%s</h%s>' % (int(match.group('val')) + 1, match.group('text'), int(match.group('val')) + 1) if match.group('text') else ''),
    (re.compile(r'\\C\d=".+?"'), lambda match: ''), # This should be made to create a TOC entry
    (re.compile(r'\\c(?P<text>.*?)\\c', re.DOTALL), lambda match: '<div style="text-align: center; margin: auto;">%s</div>' % match.group('text') if match.group('text') else ''),
    (re.compile(r'\\r(?P<text>.*?)\\r', re.DOTALL), lambda match: '<div style="text-align: right;">%s</div>' % match.group('text') if match.group('text') else ''),
    (re.compile(r'\\i(?P<text>.*?)\\i', re.DOTALL), lambda match: '<i>%s</i>' % match.group('text') if match.group('text') else ''),
    (re.compile(r'\\u(?P<text>.*?)\\u', re.DOTALL), lambda match: '<u>%s</u>' % match.group('text') if match.group('text') else ''),
    (re.compile(r'\\o(?P<text>.*?)\\o', re.DOTALL), lambda match: '<del>%s</del>' % match.group('text') if match.group('text') else ''),
    (re.compile(r'\\v(?P<text>.*?)\\v', re.DOTALL), lambda match: '<!-- %s -->' % match.group('text') if match.group('text') else ''),
    (re.compile(r'\\t(?P<text>.*?)\\t', re.DOTALL), lambda match: '<div style="margin-left: 5%%;">%s</div>' % match.group('text') if match.group('text') else ''),
    (re.compile(r'\\T="(?P<val>\d+)%*"(?P<text>.*?)$', re.MULTILINE), lambda match: r'<div style="margin-left: %s%%">%s</div>' % (match.group('val'), match.group('text')) if match.group('text') else ''),
    (re.compile(r'\\w="(?P<val>\d+)%"'), lambda match: '<hr width="%s%%" />' % match.group('val')),
    (re.compile(r'\\n'), lambda match: ''),
    (re.compile(r'\\s(?P<text>.*?)\\s', re.DOTALL), lambda match: '<span style="font-size: 1em;">%s</span>' % match.group('text') if match.group('text') else ''),
    (re.compile(r'\\b(?P<text>.*?)\\b', re.DOTALL), lambda match: '<b>%s</b>' % match.group('text') if match.group('text') else ''), # \b is deprecated; \B should be used instead.
    (re.compile(r'\\l(?P<text>.*?)\\l', re.DOTALL), lambda match: '<span style="font-size: 1.5em;">%s</span>' % match.group('text') if match.group('text') else ''),
    (re.compile(r'\\B(?P<text>.*?)\\B', re.DOTALL), lambda match: '<b>%s</b>' % match.group('text') if match.group('text') else ''),
    (re.compile(r'\\Sp(?P<text>.*?)\\Sp', re.DOTALL), lambda match: '<sup>%s</sup>' % match.group('text') if match.group('text') else ''),
    (re.compile(r'\\Sb(?P<text>.*?)\\Sb', re.DOTALL), lambda match: '<sub>%s</sub>' % match.group('text') if match.group('text') else ''),
    (re.compile(r'\\k(?P<text>.*?)\\k', re.DOTALL), lambda match: '<span style="font-size: 0.75em;">%s</span>' % match.group('text').upper() if match.group('text') else ''),
    (re.compile(r'\\a(?P<num>\d{3})'), lambda match: '&#%s;' % match.group('num')),
    (re.compile(r'\\U(?P<num>[0-9a-f]{4})'), lambda match: '%s' % my_unichr(int(match.group('num'), 16))),
    (re.compile(r'\\m="(?P<name>.+?)"'), lambda match: '<img src="images/%s" />' % image_name(match.group('name')).strip('\x00')),
    (re.compile(r'\\q="(?P<target>#.+?)"(?P<text>.*?)\\q', re.DOTALL), lambda match: '<a href="%s">%s</a>' % (match.group('target'), match.group('text')) if match.group('text') else ''),
    (re.compile(r'\\Q="(?P<target>.+?)"'), lambda match: '<span id="%s"></span>' % match.group('target')),
    (re.compile(r'\\-'), lambda match: ''),
    (re.compile(r'\\Fn="(?P<target>.+?)"(?P<text>.*?)\\Fn'), lambda match: '<a href="#fns-%s">%s</a>' % (match.group('target'), match.group('text')) if match.group('text') else ''),
    (re.compile(r'\\Sd="(?P<target>.+?)"(?P<text>.*?)\\Sd'), lambda match: '<a href="#fns-%s">%s</a>' % (match.group('target'), match.group('text')) if match.group('text') else ''),
    # Just italicize index items as that is how the eReader software renders them.
    (re.compile(r'\\I(?P<text>.*?)\\I', re.DOTALL), lambda match: '<i>%s</i>' % match.group('text') if match.group('text') else ''),

    # Sidebar and Footnotes
    (re.compile(r'&lt;sidebar\s+id="(?P<target>.+?)"&gt;\s*(?P<text>.*?)\s*&lt;/sidebar&gt;', re.DOTALL), lambda match: '<div id="fns-%s">%s</div>' % (match.group('target'), match.group('text')) if match.group('text') else ''),
    (re.compile(r'&lt;footnote\s+id="(?P<target>.+?)"&gt;\s*(?P<text>.*?)\s*&lt;/footnote&gt;', re.DOTALL), lambda match: '<div id="fns-%s">%s</div>' % (match.group('target'), match.group('text')) if match.group('text') else ''),

    # eReader files are one paragraph per line.
    # This forces the lines to wrap properly.
    (re.compile('^(?P<text>.+)$', re.MULTILINE), lambda match: '<p>%s</p>' % match.group('text')),
    # Remove empty <p>'s.
    (re.compile('<p>[ ]*</p>'), lambda match: ''),
    # Ensure empty lines carry over.
    (re.compile('(\r\n|\n|\r){3}'), lambda match: '<br />'),

    # Try to fix some of the misordering of character-attribute tags.
    (re.compile(r'(?P<ch>(<(i|u|b|del|sup|sub)( [^>]+)?>)+)(?P<close>(</(div|span)>)+)'), lambda match: match.group('close') + match.group('ch')),
    (re.compile(r'(?P<ch>(<(i|u|b|del|sup|sub|span)( [^>]+)?>)+)(?P<blk>(<(div|h\d)( [^>]+)?>)+)'), lambda match: match.group('blk') + match.group('ch')),

    # Remove unmatched plm codes.
    (re.compile(r'\\X[0-4]'), lambda match: ''),
    (re.compile(r'\\T="\d+%*"'), lambda match: ''),
    (re.compile(r'\\Sp'), lambda match: ''),
    (re.compile(r'\\Sb'), lambda match: ''),
    # Remove invalid single item pml codes.
    (re.compile(r'\\.'), lambda match: ''),
]

def pml_to_html(pml):
    html = prepare_string_for_xml(pml)
    for rule in PML_HTML_RULES:
        html = rule[0].sub(rule[1], html)

    return html

def footnote_sidebar_to_html(id, pml):
    if id.startswith('\x01'):
        id = id[2:]
    html = '<div id="fns-%s"><dt>%s</dt></div><dd>%s</dd>' % (id, id, pml_to_html(pml))
    return html
