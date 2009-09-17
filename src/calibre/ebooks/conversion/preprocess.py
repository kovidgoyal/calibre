#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import functools
import re

from calibre import entity_to_unicode

XMLDECL_RE    = re.compile(r'^\s*<[?]xml.*?[?]>')
SVG_NS       = 'http://www.w3.org/2000/svg'
XLINK_NS     = 'http://www.w3.org/1999/xlink'

convert_entities = functools.partial(entity_to_unicode, exceptions=['quot',
    'apos', 'lt', 'gt', 'amp', '#60', '#62'])
_span_pat = re.compile('<span.*?</span>', re.DOTALL|re.IGNORECASE)


def sanitize_head(match):
    x = match.group(1)
    x = _span_pat.sub('', x)
    return '<head>\n%s\n</head>' % x

def chap_head(match):
    chap = match.group('chap')
    title = match.group('title')
    if not title:
               return '<h1>'+chap+'</h1><br/>\n'
    else:
               return '<h1>'+chap+'<br/>\n'+title+'</h1><br/>\n'

def wrap_lines(match):
    ital = match.group('ital')
    if not ital:
               return ' '
    else:
               return ital+' '

def line_length(raw, percent):
    '''
    raw is the raw text to find the line length to use for wrapping.
    percentage is a decimal number, 0 - 1 which is used to determine
    how far in the list of line lengths to use. The list of line lengths is
    ordered smallest to larged and does not include duplicates. 0.5 is the
    median value.
    '''
    raw = raw.replace('&nbsp;', ' ')
    linere = re.compile('(?<=<br>).*?(?=<br>)', re.DOTALL)
    lines = linere.findall(raw)

    lengths = []
    for line in lines:
        if len(line) > 0:
            lengths.append(len(line))

    if not lengths:
        return 0

    lengths = list(set(lengths))
    total = sum(lengths)
    avg = total / len(lengths)
    max_line = avg * 2

    lengths = sorted(lengths)
    for i in range(len(lengths) - 1, -1, -1):
        if lengths[i] > max_line:
            del lengths[i]

    if percent > 1:
        percent = 1
    if percent < 0:
        percent = 0

    index = int(len(lengths) * percent) - 1

    return lengths[index]


class CSSPreProcessor(object):

    PAGE_PAT   = re.compile(r'@page[^{]*?{[^}]*?}')

    def __call__(self, data):
        data = self.PAGE_PAT.sub('', data)
        return data

class HTMLPreProcessor(object):

    PREPROCESS = [
                  # Some idiotic HTML generators (Frontpage I'm looking at you)
                  # Put all sorts of crap into <head>. This messes up lxml
                  (re.compile(r'<head[^>]*>\n*(.*?)\n*</head>', re.IGNORECASE|re.DOTALL),
                   sanitize_head),
                  # Convert all entities, since lxml doesn't handle them well
                  (re.compile(r'&(\S+?);'), convert_entities),
                  # Remove the <![if/endif tags inserted by everybody's darling, MS Word
                  (re.compile(r'</{0,1}!\[(end){0,1}if\]{0,1}>', re.IGNORECASE),
                   lambda match: ''),
                  ]

    # Fix pdftohtml markup
    PDFTOHTML  = [
                  # Fix umlauts
                  (re.compile(u'¨\s*(<br.*?>)*\s*o', re.UNICODE), lambda match: u'ö'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*O', re.UNICODE), lambda match: u'Ö'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*u', re.UNICODE), lambda match: u'ü'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*U', re.UNICODE), lambda match: u'Ü'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*e', re.UNICODE), lambda match: u'ë'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*E', re.UNICODE), lambda match: u'Ë'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*i', re.UNICODE), lambda match: u'ï'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*I', re.UNICODE), lambda match: u'Ï'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*a', re.UNICODE), lambda match: u'ä'),
                  (re.compile(u'¨\s*(<br.*?>)*\s*A', re.UNICODE), lambda match: u'Ä'),

                  # Fix accents
                  (re.compile(u'`\s*(<br.*?>)*\s*o', re.UNICODE), lambda match: u'ò'),
                  (re.compile(u'`\s*(<br.*?>)*\s*O', re.UNICODE), lambda match: u'Ò'),
                  (re.compile(u'`\s*(<br.*?>)*\s*u', re.UNICODE), lambda match: u'ù'),
                  (re.compile(u'`\s*(<br.*?>)*\s*U', re.UNICODE), lambda match: u'Ù'),
                  (re.compile(u'`\s*(<br.*?>)*\s*e', re.UNICODE), lambda match: u'è'),
                  (re.compile(u'`\s*(<br.*?>)*\s*E', re.UNICODE), lambda match: u'È'),
                  (re.compile(u'`\s*(<br.*?>)*\s*i', re.UNICODE), lambda match: u'ì'),
                  (re.compile(u'`\s*(<br.*?>)*\s*I', re.UNICODE), lambda match: u'Ì'),
                  (re.compile(u'`\s*(<br.*?>)*\s*a', re.UNICODE), lambda match: u'à'),
                  (re.compile(u'`\s*(<br.*?>)*\s*A', re.UNICODE), lambda match: u'À'),

                  (re.compile(u'´\s*(<br.*?>)*\s*o', re.UNICODE), lambda match: u'ó'),
                  (re.compile(u'´\s*(<br.*?>)*\s*O', re.UNICODE), lambda match: u'Ó'),
                  (re.compile(u'´\s*(<br.*?>)*\s*u', re.UNICODE), lambda match: u'ú'),
                  (re.compile(u'´\s*(<br.*?>)*\s*U', re.UNICODE), lambda match: u'Ú'),
                  (re.compile(u'´\s*(<br.*?>)*\s*e', re.UNICODE), lambda match: u'é'),
                  (re.compile(u'´\s*(<br.*?>)*\s*E', re.UNICODE), lambda match: u'É'),
                  (re.compile(u'´\s*(<br.*?>)*\s*i', re.UNICODE), lambda match: u'í'),
                  (re.compile(u'´\s*(<br.*?>)*\s*I', re.UNICODE), lambda match: u'Í'),
                  (re.compile(u'´\s*(<br.*?>)*\s*a', re.UNICODE), lambda match: u'á'),
                  (re.compile(u'´\s*(<br.*?>)*\s*A', re.UNICODE), lambda match: u'Á'),

                  (re.compile(u'ˆ\s*(<br.*?>)*\s*o', re.UNICODE), lambda match: u'ô'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*O', re.UNICODE), lambda match: u'Ô'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*u', re.UNICODE), lambda match: u'û'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*U', re.UNICODE), lambda match: u'Û'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*e', re.UNICODE), lambda match: u'ê'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*E', re.UNICODE), lambda match: u'Ê'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*i', re.UNICODE), lambda match: u'î'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*I', re.UNICODE), lambda match: u'Î'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*a', re.UNICODE), lambda match: u'â'),
                  (re.compile(u'ˆ\s*(<br.*?>)*\s*A', re.UNICODE), lambda match: u'Â'),

                  # Fix more special characters
                  (re.compile(u'¸\s*(<br.*?>)*\s*c', re.UNICODE), lambda match: u'ç'),
                  (re.compile(u'¸\s*(<br.*?>)*\s*C', re.UNICODE), lambda match: u'Ç'),

                  # Remove page links
                  (re.compile(r'<a name=\d+></a>', re.IGNORECASE), lambda match: ''),
                  # Remove <hr> tags
                  (re.compile(r'<hr.*?>', re.IGNORECASE), lambda match: '<br />'),
                  # Replace <br><br> with <p>
                  (re.compile(r'<br.*?>\s*<br.*?>', re.IGNORECASE), lambda match: '<p>'),

                  # Remove hyphenation
                  (re.compile(r'-<br.*?>\n\r?'), lambda match: ''),

                  # Remove gray background
                  (re.compile(r'<BODY[^<>]+>'), lambda match : '<BODY>'),

                  # Remove non breaking spaces
                  (re.compile(ur'\u00a0'), lambda match : ' '),

                  # Detect Chapters to match default XPATH in GUI
                  (re.compile(r'(?=<(/?br|p))(<(/?br|p)[^>]*)?>\s*(?P<chap>(<i><b>|<i>|<b>)?(Chapter|Epilogue|Prologue|Book|Part)\s*([\d\w-]+)?(</i></b>|</i>|</b>)?)(</?p[^>]*>|<br[^>]*>)\n?((?=(<i>)?\s*\w+(\s+\w+)?(</i>)?(<br[^>]*>|</?p[^>]*>))((?P<title>(<i>)?\s*\w+(\s+\w+)?(</i>)?)(<br[^>]*>|</?p[^>]*>)))?', re.IGNORECASE), chap_head),
                  (re.compile(r'(?=<(/?br|p))(<(/?br|p)[^>]*)?>\s*(?P<chap>([A-Z \'"!]{5,})\s*(\d+|\w+)?)(</?p[^>]*>|<br[^>]*>)\n?((?=(<i>)?\s*\w+(\s+\w+)?(</i>)?(<br[^>]*>|</?p[^>]*>))((?P<title>.*)(<br[^>]*>|</?p[^>]*>)))?'), chap_head),

                  # Have paragraphs show better
                  (re.compile(r'<br.*?>'), lambda match : '<p>'),
                  # Clean up spaces
                  (re.compile(u'(?<=[\.,;\?!”"\'])[\s^ ]*(?=<)'), lambda match: ' '),
                  # Connect paragraphs split by -
                  (re.compile(u'(?<=[^\s][-–])[\s]*(</p>)*[\s]*(<p>)*\s*(?=[^\s])'), lambda match: ''),
                  # Add space before and after italics
                  (re.compile(u'(?<!“)<i>'), lambda match: ' <i>'),
                  (re.compile(r'</i>(?=\w)'), lambda match: '</i> '),
                 ]

    # Fix Book Designer markup
    BOOK_DESIGNER = [
                     # HR
                     (re.compile('<hr>', re.IGNORECASE),
                      lambda match : '<span style="page-break-after:always"> </span>'),
                     # Create header tags
                     (re.compile('<h2[^><]*?id=BookTitle[^><]*?(align=)*(?(1)(\w+))*[^><]*?>[^><]*?</h2>', re.IGNORECASE),
                      lambda match : '<h1 id="BookTitle" align="%s">%s</h1>'%(match.group(2) if match.group(2) else 'center', match.group(3))),
                     (re.compile('<h2[^><]*?id=BookAuthor[^><]*?(align=)*(?(1)(\w+))*[^><]*?>[^><]*?</h2>', re.IGNORECASE),
                      lambda match : '<h2 id="BookAuthor" align="%s">%s</h2>'%(match.group(2) if match.group(2) else 'center', match.group(3))),
                     (re.compile('<span[^><]*?id=title[^><]*?>(.*?)</span>', re.IGNORECASE|re.DOTALL),
                      lambda match : '<h2 class="title">%s</h2>'%(match.group(1),)),
                     (re.compile('<span[^><]*?id=subtitle[^><]*?>(.*?)</span>', re.IGNORECASE|re.DOTALL),
                      lambda match : '<h3 class="subtitle">%s</h3>'%(match.group(1),)),
                     ]
    def __init__(self, input_plugin_preprocess, plugin_preprocess,
            extra_opts=None):
        self.input_plugin_preprocess = input_plugin_preprocess
        self.plugin_preprocess = plugin_preprocess
        self.extra_opts = extra_opts

    def is_baen(self, src):
        return re.compile(r'<meta\s+name="Publisher"\s+content=".*?Baen.*?"',
                          re.IGNORECASE).search(src) is not None

    def is_book_designer(self, raw):
        return re.search('<H2[^><]*id=BookTitle', raw) is not None

    def is_pdftohtml(self, src):
        return '<!-- created by calibre\'s pdftohtml -->' in src[:1000]

    def __call__(self, html, remove_special_chars=None):
        if remove_special_chars is not None:
            html = remove_special_chars.sub('', html)
        html = html.replace('\0', '')
        if self.is_baen(html):
            rules = []
        elif self.is_book_designer(html):
            rules = self.BOOK_DESIGNER
        elif self.is_pdftohtml(html):
            rules = self.PDFTOHTML
        else:
            rules = []

        pre_rules = []
        if getattr(self.extra_opts, 'remove_header', None):
            pre_rules.append(
                (re.compile(getattr(self.extra_opts, 'header_regex')), lambda match : '')
            )
        if getattr(self.extra_opts, 'remove_footer', None):
            pre_rules.append(
                (re.compile(getattr(self.extra_opts, 'footer_regex')), lambda match : '')
            )

        end_rules = []
        if getattr(self.extra_opts, 'unwrap_factor', 0.0) > 0.01:
            length = line_length(html, getattr(self.extra_opts, 'unwrap_factor'))
            if length:
                end_rules.append(
                    # Un wrap using punctuation
                    (re.compile(r'(?<=.{%i}[a-z\.,;:)-IA])\s*(?P<ital></(i|b|u)>)?\s*(<p.*?>)\s*(?=(<(i|b|u)>)?\s*[\w\d(])' % length, re.UNICODE), wrap_lines),
                )

        for rule in self.PREPROCESS + pre_rules + rules + end_rules:
            html = rule[0].sub(rule[1], html)

        # Handle broken XHTML w/ SVG (ugh)
        if 'svg:' in html and SVG_NS not in html:
            html = html.replace(
                '<html', '<html xmlns:svg="%s"' % SVG_NS, 1)
        if 'xlink:' in html and XLINK_NS not in html:
            html = html.replace(
                '<html', '<html xmlns:xlink="%s"' % XLINK_NS, 1)

        html = XMLDECL_RE.sub('', html)

        if getattr(self.extra_opts, 'asciiize', False):
            from calibre.ebooks.unidecode.unidecoder import Unidecoder
            unidecoder = Unidecoder()
            html = unidecoder.decode(html)

        if self.plugin_preprocess:
            html = self.input_plugin_preprocess(html)

        return html

