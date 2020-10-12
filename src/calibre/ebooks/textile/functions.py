#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
PyTextile

A Humane Web Text Generator
"""

# Last upstream version basis
# __version__ = '2.1.4'
# __date__ = '2009/12/04'

__copyright__ = """
Copyright (c) 2011, Leigh Parry <leighparry@blueyonder.co.uk>
Copyright (c) 2011, John Schember <john@nachtimwald.com>
Copyright (c) 2009, Jason Samsa, http://jsamsa.com/
Copyright (c) 2004, Roberto A. F. De Almeida, http://dealmeida.net/
Copyright (c) 2003, Mark Pilgrim, http://diveintomark.org/

Original PHP Version:
Copyright (c) 2003-2004, Dean Allen <dean@textism.com>
All rights reserved.

Thanks to Carlo Zottmann <carlo@g-blog.net> for refactoring
Textile's procedural code into a class framework

Additions and fixes Copyright (c) 2006 Alex Shiels http://thresholdstate.com/

"""

__license__ = """
L I C E N S E
=============
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice,
  this list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name Textile nor the names of its contributors may be used to
  endorse or promote products derived from this software without specific
  prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

"""

import re
import uuid

from calibre.utils.smartypants import smartyPants
from polyglot.builtins import unicode_type
from polyglot.urllib import urlopen, urlparse


def _normalize_newlines(string):
    out = re.sub(r'\r\n', '\n', string)
    out = re.sub(r'\n{3,}', '\n\n', out)
    out = re.sub(r'\n\s*\n', '\n\n', out)
    out = re.sub(r'"$', '" ', out)
    return out


def getimagesize(url):
    """
    Attempts to determine an image's width and height, and returns a string
    suitable for use in an <img> tag, or None in case of failure.
    Requires that PIL is installed.

    >>> getimagesize("http://www.google.com/intl/en_ALL/images/logo.gif")
    ... #doctest: +ELLIPSIS, +SKIP
    'width="..." height="..."'

    """

    from PIL import ImageFile

    try:
        p = ImageFile.Parser()
        f = urlopen(url)
        while True:
            s = f.read(1024)
            if not s:
                break
            p.feed(s)
            if p.image:
                return 'width="%i" height="%i"' % p.image.size
    except (IOError, ValueError):
        return None


class Textile(object):
    hlgn = r'(?:\<(?!>)|(?<!<)\>|\<\>|\=|[()]+(?! ))'
    vlgn = r'[\-^~]'
    clas = r'(?:\([^)]+\))'
    lnge = r'(?:\[[^\]]+\])'
    styl = r'(?:\{[^}]+\})'
    cspn = r'(?:\\\d+)'
    rspn = r'(?:\/\d+)'
    a = r'(?:%s|%s)*' % (hlgn, vlgn)
    s = r'(?:%s|%s)*' % (cspn, rspn)
    c = r'(?:%s)*' % '|'.join([clas, styl, lnge, hlgn])

    pnct = r'[-!"#$%&()*+,/:;<=>?@\'\[\\\]\.^_`{|}~]'
    # urlch = r'[\w"$\-_.+!*\'(),";/?:@=&%#{}|\\^~\[\]`]'
    urlch = r'[\w"$\-_.+*\'(),";\/?:@=&%#{}|\\^~\[\]`]'

    url_schemes = ('http', 'https', 'ftp', 'mailto')

    btag = ('bq', 'bc', 'notextile', 'pre', 'h[1-6]', r'fn\d+', 'p')
    btag_lite = ('bq', 'bc', 'p')

    macro_defaults = [
        (re.compile(r'{(c\||\|c)}'),     r'&#162;'),  # cent
        (re.compile(r'{(L-|-L)}'),       r'&#163;'),  # pound
        (re.compile(r'{(Y=|=Y)}'),       r'&#165;'),  # yen
        (re.compile(r'{\(c\)}'),         r'&#169;'),  # copyright
        (re.compile(r'{\(r\)}'),         r'&#174;'),  # registered
        (re.compile(r'{(\+_|_\+)}'),     r'&#177;'),  # plus-minus
        (re.compile(r'{1/4}'),           r'&#188;'),  # quarter
        (re.compile(r'{1/2}'),           r'&#189;'),  # half
        (re.compile(r'{3/4}'),           r'&#190;'),  # three-quarter
        (re.compile(r'{(A`|`A)}'),       r'&#192;'),  # A-acute
        (re.compile(r'{(A\'|\'A)}'),     r'&#193;'),  # A-grave
        (re.compile(r'{(A\^|\^A)}'),     r'&#194;'),  # A-circumflex
        (re.compile(r'{(A~|~A)}'),       r'&#195;'),  # A-tilde
        (re.compile(r'{(A\"|\"A)}'),     r'&#196;'),  # A-diaeresis
        (re.compile(r'{(Ao|oA)}'),       r'&#197;'),  # A-ring
        (re.compile(r'{(AE)}'),          r'&#198;'),  # AE
        (re.compile(r'{(C,|,C)}'),       r'&#199;'),  # C-cedilla
        (re.compile(r'{(E`|`E)}'),       r'&#200;'),  # E-acute
        (re.compile(r'{(E\'|\'E)}'),     r'&#201;'),  # E-grave
        (re.compile(r'{(E\^|\^E)}'),     r'&#202;'),  # E-circumflex
        (re.compile(r'{(E\"|\"E)}'),     r'&#203;'),  # E-diaeresis
        (re.compile(r'{(I`|`I)}'),       r'&#204;'),  # I-acute
        (re.compile(r'{(I\'|\'I)}'),     r'&#205;'),  # I-grave
        (re.compile(r'{(I\^|\^I)}'),     r'&#206;'),  # I-circumflex
        (re.compile(r'{(I\"|\"I)}'),     r'&#207;'),  # I-diaeresis
        (re.compile(r'{(D-|-D)}'),       r'&#208;'),  # ETH
        (re.compile(r'{(N~|~N)}'),       r'&#209;'),  # N-tilde
        (re.compile(r'{(O`|`O)}'),       r'&#210;'),  # O-acute
        (re.compile(r'{(O\'|\'O)}'),     r'&#211;'),  # O-grave
        (re.compile(r'{(O\^|\^O)}'),     r'&#212;'),  # O-circumflex
        (re.compile(r'{(O~|~O)}'),       r'&#213;'),  # O-tilde
        (re.compile(r'{(O\"|\"O)}'),     r'&#214;'),  # O-diaeresis
        (re.compile(r'{x}'),             r'&#215;'),  # dimension
        (re.compile(r'{(O\/|\/O)}'),     r'&#216;'),  # O-slash
        (re.compile(r'{(U`|`U)}'),       r'&#217;'),  # U-acute
        (re.compile(r'{(U\'|\'U)}'),     r'&#218;'),  # U-grave
        (re.compile(r'{(U\^|\^U)}'),     r'&#219;'),  # U-circumflex
        (re.compile(r'{(U\"|\"U)}'),     r'&#220;'),  # U-diaeresis
        (re.compile(r'{(Y\'|\'Y)}'),     r'&#221;'),  # Y-grave
        (re.compile(r'{sz}'),            r'&szlig;'),  # sharp-s
        (re.compile(r'{(a`|`a)}'),       r'&#224;'),  # a-grave
        (re.compile(r'{(a\'|\'a)}'),     r'&#225;'),  # a-acute
        (re.compile(r'{(a\^|\^a)}'),     r'&#226;'),  # a-circumflex
        (re.compile(r'{(a~|~a)}'),       r'&#227;'),  # a-tilde
        (re.compile(r'{(a\"|\"a)}'),     r'&#228;'),  # a-diaeresis
        (re.compile(r'{(ao|oa)}'),       r'&#229;'),  # a-ring
        (re.compile(r'{ae}'),            r'&#230;'),  # ae
        (re.compile(r'{(c,|,c)}'),       r'&#231;'),  # c-cedilla
        (re.compile(r'{(e`|`e)}'),       r'&#232;'),  # e-grave
        (re.compile(r'{(e\'|\'e)}'),     r'&#233;'),  # e-acute
        (re.compile(r'{(e\^|\^e)}'),     r'&#234;'),  # e-circumflex
        (re.compile(r'{(e\"|\"e)}'),     r'&#235;'),  # e-diaeresis
        (re.compile(r'{(i`|`i)}'),       r'&#236;'),  # i-grave
        (re.compile(r'{(i\'|\'i)}'),     r'&#237;'),  # i-acute
        (re.compile(r'{(i\^|\^i)}'),     r'&#238;'),  # i-circumflex
        (re.compile(r'{(i\"|\"i)}'),     r'&#239;'),  # i-diaeresis
        (re.compile(r'{(d-|-d)}'),       r'&#240;'),  # eth
        (re.compile(r'{(n~|~n)}'),       r'&#241;'),  # n-tilde
        (re.compile(r'{(o`|`o)}'),       r'&#242;'),  # o-grave
        (re.compile(r'{(o\'|\'o)}'),     r'&#243;'),  # o-acute
        (re.compile(r'{(o\^|\^o)}'),     r'&#244;'),  # o-circumflex
        (re.compile(r'{(o~|~o)}'),       r'&#245;'),  # o-tilde
        (re.compile(r'{(o\"|\"o)}'),     r'&#246;'),  # o-diaeresis
        (re.compile(r'{(o\/|\/o)}'),     r'&#248;'),  # o-stroke
        (re.compile(r'{(u`|`u)}'),       r'&#249;'),  # u-grave
        (re.compile(r'{(u\'|\'u)}'),     r'&#250;'),  # u-acute
        (re.compile(r'{(u\^|\^u)}'),     r'&#251;'),  # u-circumflex
        (re.compile(r'{(u\"|\"u)}'),     r'&#252;'),  # u-diaeresis
        (re.compile(r'{(y\'|\'y)}'),     r'&#253;'),  # y-acute
        (re.compile(r'{(y\"|\"y)}'),     r'&#255;'),  # y-diaeresis

        (re.compile(r'{(C\ˇ|\ˇC)}'),     r'&#268;'),  # C-caron
        (re.compile(r'{(c\ˇ|\ˇc)}'),     r'&#269;'),  # c-caron
        (re.compile(r'{(D\ˇ|\ˇD)}'),     r'&#270;'),  # D-caron
        (re.compile(r'{(d\ˇ|\ˇd)}'),     r'&#271;'),  # d-caron
        (re.compile(r'{(E\ˇ|\ˇE)}'),     r'&#282;'),  # E-caron
        (re.compile(r'{(e\ˇ|\ˇe)}'),     r'&#283;'),  # e-caron
        (re.compile(r'{(L\'|\'L)}'),     r'&#313;'),  # L-acute
        (re.compile(r'{(l\'|\'l)}'),     r'&#314;'),  # l-acute
        (re.compile(r'{(L\ˇ|\ˇL)}'),     r'&#317;'),  # L-caron
        (re.compile(r'{(l\ˇ|\ˇl)}'),     r'&#318;'),  # l-caron
        (re.compile(r'{(N\ˇ|\ˇN)}'),     r'&#327;'),  # N-caron
        (re.compile(r'{(n\ˇ|\ˇn)}'),     r'&#328;'),  # n-caron

        (re.compile(r'{OE}'),            r'&#338;'),  # OE
        (re.compile(r'{oe}'),            r'&#339;'),  # oe

        (re.compile(r'{(R\'|\'R)}'),     r'&#340;'),  # R-acute
        (re.compile(r'{(r\'|\'r)}'),     r'&#341;'),  # r-acute
        (re.compile(r'{(R\ˇ|\ˇR)}'),     r'&#344;'),  # R-caron
        (re.compile(r'{(r\ˇ|\ˇr)}'),     r'&#345;'),  # r-caron

        (re.compile(r'{(S\^|\^S)}'),     r'&#348;'),  # S-circumflex
        (re.compile(r'{(s\^|\^s)}'),     r'&#349;'),  # s-circumflex

        (re.compile(r'{(S\ˇ|\ˇS)}'),     r'&#352;'),  # S-caron
        (re.compile(r'{(s\ˇ|\ˇs)}'),     r'&#353;'),  # s-caron
        (re.compile(r'{(T\ˇ|\ˇT)}'),     r'&#356;'),  # T-caron
        (re.compile(r'{(t\ˇ|\ˇt)}'),     r'&#357;'),  # t-caron
        (re.compile(r'{(U\°|\°U)}'),     r'&#366;'),  # U-ring
        (re.compile(r'{(u\°|\°u)}'),     r'&#367;'),  # u-ring
        (re.compile(r'{(Z\ˇ|\ˇZ)}'),     r'&#381;'),  # Z-caron
        (re.compile(r'{(z\ˇ|\ˇz)}'),     r'&#382;'),  # z-caron

        (re.compile(r'{\*}'),            r'&#8226;'),  # bullet
        (re.compile(r'{Fr}'),            r'&#8355;'),  # Franc
        (re.compile(r'{(L=|=L)}'),       r'&#8356;'),  # Lira
        (re.compile(r'{Rs}'),            r'&#8360;'),  # Rupee
        (re.compile(r'{(C=|=C)}'),       r'&#8364;'),  # euro
        (re.compile(r'{tm}'),            r'&#8482;'),  # trademark
        (re.compile(r'{spades?}'),       r'&#9824;'),  # spade
        (re.compile(r'{clubs?}'),        r'&#9827;'),  # club
        (re.compile(r'{hearts?}'),       r'&#9829;'),  # heart
        (re.compile(r'{diam(onds?|s)}'), r'&#9830;'),  # diamond
        (re.compile(r'{"}'),             r'&#34;'),  # double-quote
        (re.compile(r"{'}"),             r'&#39;'),  # single-quote
        (re.compile(r"{(’|'/|/')}"),     r'&#8217;'),  # closing-single-quote - apostrophe
        (re.compile(r"{(‘|\\'|'\\)}"),   r'&#8216;'),  # opening-single-quote
        (re.compile(r'{(”|"/|/")}'),     r'&#8221;'),  # closing-double-quote
        (re.compile(r'{(“|\\"|"\\)}'),   r'&#8220;'),  # opening-double-quote
    ]
    glyph_defaults = [
        (re.compile(r'(\d+\'?\"?)( ?)x( ?)(?=\d+)'),                   r'\1\2&#215;\3'),  # dimension sign
        (re.compile(r'(\d+)\'(\s)', re.I),                             r'\1&#8242;\2'),  # prime
        (re.compile(r'(\d+)\"(\s)', re.I),                             r'\1&#8243;\2'),  # prime-double
        (re.compile(r'\b([A-Z][A-Z0-9]{2,})\b(?:[(]([^)]*)[)])'),      r'<acronym title="\2">\1</acronym>'),  # 3+ uppercase acronym
        (re.compile(r'\b([A-Z][A-Z\'\-]+[A-Z])(?=[\s.,\)>])'),         r'<span class="caps">\1</span>'),  # 3+ uppercase
        (re.compile(r'\b(\s{0,1})?\.{3}'),                             r'\1&#8230;'),  # ellipsis
        (re.compile(r'^[\*_-]{3,}$', re.M),                            r'<hr />'),  # <hr> scene-break
        (re.compile(r'(^|[^-])--([^-]|$)'),                            r'\1&#8212;\2'),  # em dash
        (re.compile(r'\s-(?:\s|$)'),                                   r' &#8211; '),  # en dash
        (re.compile(r'\b( ?)[([]TM[])]', re.I),                        r'\1&#8482;'),  # trademark
        (re.compile(r'\b( ?)[([]R[])]', re.I),                         r'\1&#174;'),  # registered
        (re.compile(r'\b( ?)[([]C[])]', re.I),                         r'\1&#169;'),  # copyright
    ]

    def __init__(self, restricted=False, lite=False, noimage=False):
        """docstring for __init__"""
        self.restricted = restricted
        self.lite = lite
        self.noimage = noimage
        self.get_sizes = False
        self.fn = {}
        self.urlrefs = {}
        self.shelf = {}
        self.rel = ''
        self.html_type = 'xhtml'

    def textile(self, text, rel=None, head_offset=0, html_type='xhtml'):
        """
        >>> import textile
        >>> textile.textile('some textile')
        u'\\t<p>some textile</p>'
        """
        self.html_type = html_type

        # text = type(u'')(text)
        text = _normalize_newlines(text)

        if self.restricted:
            text = self.encode_html(text, quotes=False)

        if rel:
            self.rel = ' rel="%s"' % rel

        text = self.getRefs(text)
        text = self.block(text, int(head_offset))
        text = self.retrieve(text)
        text = smartyPants(text, 'q')

        return text

    def pba(self, input, element=None):
        """
        Parse block attributes.

        >>> t = Textile()
        >>> t.pba(r'\3')
        ''
        >>> t.pba(r'\\3', element='td')
        ' colspan="3"'
        >>> t.pba(r'/4', element='td')
        ' rowspan="4"'
        >>> t.pba(r'\\3/4', element='td')
        ' colspan="3" rowspan="4"'

        >>> t.vAlign('^')
        'top'

        >>> t.pba('^', element='td')
        ' style="vertical-align:top;"'

        >>> t.pba('{line-height:18px}')
        ' style="line-height:18px;"'

        >>> t.pba('(foo-bar)')
        ' class="foo-bar"'

        >>> t.pba('(#myid)')
        ' id="myid"'

        >>> t.pba('(foo-bar#myid)')
        ' class="foo-bar" id="myid"'

        >>> t.pba('((((')
        ' style="padding-left:4em;"'

        >>> t.pba(')))')
        ' style="padding-right:3em;"'

        >>> t.pba('[fr]')
        ' lang="fr"'

        """
        style = []
        aclass = ''
        lang = ''
        colspan = ''
        rowspan = ''
        id = ''

        if not input:
            return ''

        matched = input
        if element == 'td':
            m = re.search(r'\\(\d+)', matched)
            if m:
                colspan = m.group(1)

            m = re.search(r'/(\d+)', matched)
            if m:
                rowspan = m.group(1)

        if element == 'td' or element == 'tr':
            m = re.search(r'(%s)' % self.vlgn, matched)
            if m:
                style.append("vertical-align:%s;" % self.vAlign(m.group(1)))

        m = re.search(r'\{([^}]*)\}', matched)
        if m:
            style.append(m.group(1).rstrip(';') + ';')
            matched = matched.replace(m.group(0), '')

        m = re.search(r'\[([^\]]+)\]', matched, re.U)
        if m:
            lang = m.group(1)
            matched = matched.replace(m.group(0), '')

        m = re.search(r'\(([^()]+)\)', matched, re.U)
        if m:
            aclass = m.group(1)
            matched = matched.replace(m.group(0), '')

        m = re.search(r'([(]+)', matched)
        if m:
            style.append("padding-left:%sem;" % len(m.group(1)))
            matched = matched.replace(m.group(0), '')

        m = re.search(r'([)]+)', matched)
        if m:
            style.append("padding-right:%sem;" % len(m.group(1)))
            matched = matched.replace(m.group(0), '')

        m = re.search(r'(%s)' % self.hlgn, matched)
        if m:
            style.append("text-align:%s;" % self.hAlign(m.group(1)))

        m = re.search(r'^(.*)#(.*)$', aclass)
        if m:
            id = m.group(2)
            aclass = m.group(1)

        if self.restricted:
            if lang:
                return ' lang="%s"'
            else:
                return ''

        result = []
        if style:
            result.append(' style="%s"' % "".join(style))
        if aclass:
            result.append(' class="%s"' % aclass)
        if lang:
            result.append(' lang="%s"' % lang)
        if id:
            result.append(' id="%s"' % id)
        if colspan:
            result.append(' colspan="%s"' % colspan)
        if rowspan:
            result.append(' rowspan="%s"' % rowspan)
        return ''.join(result)

    def hasRawText(self, text):
        """
        checks whether the text has text not already enclosed by a block tag

        >>> t = Textile()
        >>> t.hasRawText('<p>foo bar biz baz</p>')
        False

        >>> t.hasRawText(' why yes, yes it does')
        True

        """
        r = re.compile(r'<(p|blockquote|div|form|table|ul|ol|pre|h\d)[^>]*?>.*</\1>', re.S).sub('', text.strip()).strip()
        r = re.compile(r'<(hr|br)[^>]*?/>').sub('', r)
        return '' != r

    def table(self, text):
        r"""
        >>> t = Textile()
        >>> t.table('|one|two|three|\n|a|b|c|')
        '\t<table>\n\t\t<tr>\n\t\t\t<td>one</td>\n\t\t\t<td>two</td>\n\t\t\t<td>three</td>\n\t\t</tr>\n\t\t<tr>\n\t\t\t<td>a</td>\n\t\t\t<td>b</td>\n\t\t\t<td>c</td>\n\t\t</tr>\n\t</table>\n\n'
        """
        text = text + "\n\n"
        pattern = re.compile(r'^(?:table(_?%(s)s%(a)s%(c)s)\. ?\n)?^(%(a)s%(c)s\.? ?\|.*\|)\n\n' % {'s':self.s, 'a':self.a, 'c':self.c}, re.S|re.M|re.U)
        return pattern.sub(self.fTable, text)

    def fTable(self, match):
        tatts = self.pba(match.group(1), 'table')
        rows = []
        for row in [x for x in match.group(2).split('\n') if x]:
            rmtch = re.search(r'^(%s%s\. )(.*)' % (self.a, self.c), row.lstrip())
            if rmtch:
                ratts = self.pba(rmtch.group(1), 'tr')
                row = rmtch.group(2)
            else:
                ratts = ''

            cells = []
            for cell in row.split('|')[1:-1]:
                ctyp = 'd'
                if re.search(r'^_', cell):
                    ctyp = "h"
                cmtch = re.search(r'^(_?%s%s%s\. )(.*)' % (self.s, self.a, self.c), cell)
                if cmtch:
                    catts = self.pba(cmtch.group(1), 'td')
                    cell = cmtch.group(2)
                else:
                    catts = ''

                cell = self.graf(self.span(cell))
                cells.append('\t\t\t<t%s%s>%s</t%s>' % (ctyp, catts, cell, ctyp))
            rows.append("\t\t<tr%s>\n%s\n\t\t</tr>" % (ratts, '\n'.join(cells)))
            cells = []
            catts = None
        return "\t<table%s>\n%s\n\t</table>\n\n" % (tatts, '\n'.join(rows))

    def lists(self, text):
        """
        >>> t = Textile()
        >>> t.lists("* one\\n* two\\n* three")
        '\\t<ul>\\n\\t\\t<li>one</li>\\n\\t\\t<li>two</li>\\n\\t\\t<li>three</li>\\n\\t</ul>'
        """
        pattern = re.compile(r'^([#*]+%s .*)$(?![^#*])' % self.c, re.U|re.M|re.S)
        return pattern.sub(self.fList, text)

    def fList(self, match):
        text = match.group(0).split("\n")
        result = []
        lists = []
        for i, line in enumerate(text):
            try:
                nextline = text[i+1]
            except IndexError:
                nextline = ''

            m = re.search(r"^([#*]+)(%s%s) (.*)$" % (self.a, self.c), line, re.S)
            if m:
                tl, atts, content = m.groups()
                nl = ''
                nm = re.search(r'^([#*]+)\s.*', nextline)
                if nm:
                    nl = nm.group(1)
                if tl not in lists:
                    lists.append(tl)
                    atts = self.pba(atts)
                    line = "\t<%sl%s>\n\t\t<li>%s" % (self.lT(tl), atts, self.graf(content))
                else:
                    line = "\t\t<li>" + self.graf(content)

                if len(nl) <= len(tl):
                    line = line + "</li>"
                for k in reversed(lists):
                    if len(k) > len(nl):
                        line = line + "\n\t</%sl>" % self.lT(k)
                        if len(k) > 1:
                            line = line + "</li>"
                        lists.remove(k)

            result.append(line)
        return "\n".join(result)

    def lT(self, input):
        if re.search(r'^#+', input):
            return 'o'
        else:
            return 'u'

    def doPBr(self, in_):
        return re.compile(r'<(p)([^>]*?)>(.*)(</\1>)', re.S).sub(self.doBr, in_)

    def doBr(self, match):
        if self.html_type == 'html':
            content = re.sub(r'(.+)(?:(?<!<br>)|(?<!<br />))\n(?![#*\s|])', '\\1<br>', match.group(3))
        else:
            content = re.sub(r'(.+)(?:(?<!<br>)|(?<!<br />))\n(?![#*\s|])', '\\1<br />', match.group(3))
        return '<%s%s>%s%s' % (match.group(1), match.group(2), content, match.group(4))

    def block(self, text, head_offset=0):
        """
        >>> t = Textile()
        >>> t.block('h1. foobar baby')
        '\\t<h1>foobar baby</h1>'
        """
        if not self.lite:
            tre = '|'.join(self.btag)
        else:
            tre = '|'.join(self.btag_lite)
        text = text.split('\n\n')

        tag = 'p'
        atts = cite = graf = ext = c1 = ''

        out = []

        anon = False
        for line in text:
            pattern = r'^(%s)(%s%s)\.(\.?)(?::(\S+))? (.*)$' % (tre, self.a, self.c)
            match = re.search(pattern, line, re.S)
            if match:
                if ext:
                    out.append(out.pop() + c1)

                tag, atts, ext, cite, graf = match.groups()
                h_match = re.search(r'h([1-6])', tag)
                if h_match:
                    head_level, = h_match.groups()
                    tag = 'h%i' % max(1,
                                      min(int(head_level) + head_offset,
                                          6))
                o1, o2, content, c2, c1 = self.fBlock(tag, atts, ext,
                                                      cite, graf)
                # leave off c1 if this block is extended,
                # we'll close it at the start of the next block

                if ext:
                    line = "%s%s%s%s" % (o1, o2, content, c2)
                else:
                    line = "%s%s%s%s%s" % (o1, o2, content, c2, c1)

            else:
                anon = True
                if ext or not re.search(r'^\s', line):
                    o1, o2, content, c2, c1 = self.fBlock(tag, atts, ext,
                                                          cite, line)
                    # skip $o1/$c1 because this is part of a continuing
                    # extended block
                    if tag == 'p' and not self.hasRawText(content):
                        line = content
                    else:
                        line = "%s%s%s" % (o2, content, c2)
                else:
                    line = self.graf(line)

            line = self.doPBr(line)
            if self.html_type == 'xhtml':
                line = re.sub(r'<br>', '<br />', line)

            if ext and anon:
                out.append(out.pop() + "\n" + line)
            else:
                out.append(line)

            if not ext:
                tag = 'p'
                atts = ''
                cite = ''
                graf = ''

        if ext:
            out.append(out.pop() + c1)
        return '\n\n'.join(out)

    def fBlock(self, tag, atts, ext, cite, content):
        """
        >>> t = Textile()
        >>> t.fBlock("bq", "", None, "", "Hello BlockQuote")
        ('\\t<blockquote>\\n', '\\t\\t<p>', 'Hello BlockQuote', '</p>', '\\n\\t</blockquote>')

        >>> t.fBlock("bq", "", None, "http://google.com", "Hello BlockQuote")
        ('\\t<blockquote cite="http://google.com">\\n', '\\t\\t<p>', 'Hello BlockQuote', '</p>', '\\n\\t</blockquote>')

        >>> t.fBlock("bc", "", None, "", 'printf "Hello, World";') # doctest: +ELLIPSIS
        ('<pre>', '<code>', ..., '</code>', '</pre>')

        >>> t.fBlock("h1", "", None, "", "foobar")
        ('', '\\t<h1>', 'foobar', '</h1>', '')
        """
        atts = self.pba(atts)
        o1 = o2 = c2 = c1 = ''

        m = re.search(r'fn(\d+)', tag)
        if m:
            tag = 'p'
            if m.group(1) in self.fn:
                fnid = self.fn[m.group(1)]
            else:
                fnid = m.group(1)
            atts = atts + ' id="fn%s"' % fnid
            if atts.find('class=') < 0:
                atts = atts + ' class="footnote"'
            content = ('<sup>%s</sup>' % m.group(1)) + content

        if tag == 'bq':
            cite = self.checkRefs(cite)
            if cite:
                cite = ' cite="%s"' % cite
            else:
                cite = ''
            o1 = "\t<blockquote%s%s>\n" % (cite, atts)
            o2 = "\t\t<p%s>" % atts
            c2 = "</p>"
            c1 = "\n\t</blockquote>"

        elif tag == 'bc':
            o1 = "<pre%s>" % atts
            o2 = "<code%s>" % atts
            c2 = "</code>"
            c1 = "</pre>"
            content = self.shelve(self.encode_html(content.rstrip("\n") + "\n"))

        elif tag == 'notextile':
            content = self.shelve(content)
            o1 = o2 = ''
            c1 = c2 = ''

        elif tag == 'pre':
            content = self.shelve(self.encode_html(content.rstrip("\n") + "\n"))
            o1 = "<pre%s>" % atts
            o2 = c2 = ''
            c1 = '</pre>'

        else:
            o2 = "\t<%s%s>" % (tag, atts)
            c2 = "</%s>" % tag

        content = self.graf(content)
        return o1, o2, content, c2, c1

    def footnoteRef(self, text):
        """
        >>> t = Textile()
        >>> t.footnoteRef('foo[1] ') # doctest: +ELLIPSIS
        'foo<sup class="footnote"><a href="#fn...">1</a></sup> '
        """
        return re.sub(r'\b\[([0-9]+)\](\s)?', self.footnoteID, text)

    def footnoteID(self, match):
        id, t = match.groups()
        if id not in self.fn:
            self.fn[id] = unicode_type(uuid.uuid4())
        fnid = self.fn[id]
        if not t:
            t = ''
        return '<sup class="footnote"><a href="#fn%s">%s</a></sup>%s' % (fnid, id, t)

    def glyphs(self, text):
        """
        >>> t = Textile()

        >>> t.glyphs("apostrophe's")
        'apostrophe&#8217;s'

        >>> t.glyphs("back in '88")
        'back in &#8217;88'

        >>> t.glyphs('foo ...')
        'foo &#8230;'

        >>> t.glyphs('--')
        '&#8212;'

        >>> t.glyphs('FooBar[tm]')
        'FooBar&#8482;'

        >>> t.glyphs("<p><cite>Cat's Cradle</cite> by Vonnegut</p>")
        '<p><cite>Cat&#8217;s Cradle</cite> by Vonnegut</p>'

        """
        # fix: hackish
        text = re.sub(r'"\Z', '\" ', text)

        result = []
        for line in re.compile(r'(<.*?>)', re.U).split(text):
            if not re.search(r'<.*>', line):
                rules = []
                if re.search(r'{.+?}', line):
                    rules = self.macro_defaults + self.glyph_defaults
                else:
                    rules = self.glyph_defaults
                for s, r in rules:
                    line = s.sub(r, line)
            result.append(line)
        return ''.join(result)

    def macros_only(self, text):
        # fix: hackish
        text = re.sub(r'"\Z', '\" ', text)

        result = []
        for line in re.compile(r'(<.*?>)', re.U).split(text):
            if not re.search(r'<.*>', line):
                rules = []
                if re.search(r'{.+?}', line):
                    rules = self.macro_defaults
                for s, r in rules:
                    line = s.sub(r, line)
            result.append(line)
        return ''.join(result)

    def vAlign(self, input):
        d = {'^':'top', '-':'middle', '~':'bottom'}
        return d.get(input, '')

    def hAlign(self, input):
        d = {'<':'left', '=':'center', '>':'right', '<>': 'justify'}
        return d.get(input, '')

    def getRefs(self, text):
        """
        what is this for?
        """
        pattern = re.compile(r'(?:(?<=^)|(?<=\s))\[(.+)\]((?:http(?:s?):\/\/|\/)\S+)(?=\s|$)', re.U)
        text = pattern.sub(self.refs, text)
        return text

    def refs(self, match):
        flag, url = match.groups()
        self.urlrefs[flag] = url
        return ''

    def checkRefs(self, url):
        return self.urlrefs.get(url, url)

    def isRelURL(self, url):
        """
        Identify relative urls.

        >>> t = Textile()
        >>> t.isRelURL("http://www.google.com/")
        False
        >>> t.isRelURL("/foo")
        True

        """
        (scheme, netloc) = urlparse(url)[0:2]
        return not scheme and not netloc

    def relURL(self, url):
        scheme = urlparse(url)[0]
        if self.restricted and scheme and scheme not in self.url_schemes:
            return '#'
        return url

    def shelve(self, text):
        id = unicode_type(uuid.uuid4()) + 'c'
        self.shelf[id] = text
        return id

    def retrieve(self, text):
        """
        >>> t = Textile()
        >>> id = t.shelve("foobar")
        >>> t.retrieve(id)
        'foobar'
        """
        while True:
            old = text
            for k, v in self.shelf.items():
                text = text.replace(k, v)
            if text == old:
                break
        return text

    def encode_html(self, text, quotes=True):
        a = (
            ('&', '&#38;'),
            ('<', '&#60;'),
            ('>', '&#62;')
        )

        if quotes:
            a = a + (
                ("'", '&#39;'),
                ('"', '&#34;')
            )

        for k, v in a:
            text = text.replace(k, v)
        return text

    def graf(self, text):
        if not self.lite:
            text = self.noTextile(text)
            text = self.code(text)

        text = self.links(text)

        if not self.noimage:
            text = self.image(text)

        if not self.lite:
            text = self.lists(text)
            text = self.table(text)

        text = self.span(text)
        text = self.footnoteRef(text)
        text = self.glyphs(text)

        return text.rstrip('\n')

    def links(self, text):
        """
        >>> t = Textile()
        >>> t.links('fooobar "Google":http://google.com/foobar/ and hello world "flickr":http://flickr.com/photos/jsamsa/ ') # doctest: +ELLIPSIS
        'fooobar ... and hello world ...'
        """

        text = self.macros_only(text)
        punct = '!"#$%&\'*+,-./:;=?@\\^_`|~'

        pattern = r'''
            (?P<pre>    [\s\[{(]|[%s]   )?
            "                          # start
            (?P<atts>   %s       )
            (?P<text>   [^"]+?   )
            \s?
            (?:   \(([^)]+?)\)(?=")   )?     # $title
            ":
            (?P<url>    (?:ftp|https?)? (?: :// )? [-A-Za-z0-9+&@#/?=~_()|!:,.;]*[-A-Za-z0-9+&@#/=~_()|]   )
            (?P<post>   [^\w\/;]*?   )
            (?=<|\s|$)
        ''' % (re.escape(punct), self.c)

        text = re.compile(pattern, re.X).sub(self.fLink, text)

        return text

    def fLink(self, match):
        pre, atts, text, title, url, post = match.groups()

        if pre is None:
            pre = ''

        # assume ) at the end of the url is not actually part of the url
        # unless the url also contains a (
        if url.endswith(')') and not url.find('(') > -1:
            post = url[-1] + post
            url = url[:-1]

        url = self.checkRefs(url)

        atts = self.pba(atts)
        if title:
            atts = atts +  ' title="%s"' % self.encode_html(title)

        if not self.noimage:
            text = self.image(text)

        text = self.span(text)
        text = self.glyphs(text)

        url = self.relURL(url)
        out = '<a href="%s"%s%s>%s</a>' % (self.encode_html(url), atts, self.rel, text)
        out = self.shelve(out)
        return ''.join([pre, out, post])

    def span(self, text):
        """
        >>> t = Textile()
        >>> t.span(r"hello %(bob)span *strong* and **bold**% goodbye")
        'hello <span class="bob">span <strong>strong</strong> and <b>bold</b></span> goodbye'
        """
        qtags = (r'\*\*', r'\*', r'\?\?', r'\-', r'__', r'_', r'%', r'\+', r'~', r'\^')
        pnct = ".,\"'?!;:"

        for qtag in qtags:
            pattern = re.compile(r"""
                (?:^|(?<=[\s>%(pnct)s\(])|\[|([\]}]))
                (%(qtag)s)(?!%(qtag)s)
                (%(c)s)
                (?::(\S+))?
                ([^\s%(qtag)s]+|\S[^%(qtag)s\n]*[^\s%(qtag)s\n])
                ([%(pnct)s]*)
                %(qtag)s
                (?:$|([\]}])|(?=%(selfpnct)s{1,2}|\s))
            """ % {'qtag':qtag, 'c':self.c, 'pnct':pnct,
                   'selfpnct':self.pnct}, re.X)
            text = pattern.sub(self.fSpan, text)
        return text

    def fSpan(self, match):
        _, tag, atts, cite, content, end, _ = match.groups()

        qtags = {
            '*': 'strong',
            '**': 'b',
            '??': 'cite',
            '_' : 'em',
            '__': 'i',
            '-' : 'del',
            '%' : 'span',
            '+' : 'ins',
            '~' : 'sub',
            '^' : 'sup'
        }
        tag = qtags[tag]
        atts = self.pba(atts)
        if cite:
            atts = atts + 'cite="%s"' % cite

        content = self.span(content)

        out = "<%s%s>%s%s</%s>" % (tag, atts, content, end, tag)
        return out

    def image(self, text):
        """
        >>> t = Textile()
        >>> t.image('!/imgs/myphoto.jpg!:http://jsamsa.com')
        '<a href="http://jsamsa.com"><img src="/imgs/myphoto.jpg" alt="" /></a>'
        """
        pattern = re.compile(r"""
            (?:[\[{])?          # pre
            \!                 # opening !
            (%s)               # optional style,class atts
            (?:\. )?           # optional dot-space
            ([^\s(!]+)         # presume this is the src
            \s?                # optional space
            (?:\(([^\)]+)\))?  # optional title
            \!                 # closing
            (?::(\S+))?        # optional href
            (?:[\]}]|(?=\s|$)) # lookahead: space or end of string
        """ % self.c, re.U|re.X)
        return pattern.sub(self.fImage, text)

    def fImage(self, match):
        # (None, '', '/imgs/myphoto.jpg', None, None)
        atts, url, title, href = match.groups()
        atts  = self.pba(atts)

        if title:
            atts = atts + ' title="%s" alt="%s"' % (title, title)
        else:
            atts = atts + ' alt=""'

        if not self.isRelURL(url) and self.get_sizes:
            size = getimagesize(url)
            if (size):
                atts += " %s" % size

        if href:
            href = self.checkRefs(href)

        url = self.checkRefs(url)
        url = self.relURL(url)

        out = []
        if href:
            out.append('<a href="%s" class="img">' % href)
        if self.html_type == 'html':
            out.append('<img src="%s"%s>' % (url, atts))
        else:
            out.append('<img src="%s"%s />' % (url, atts))
        if href:
            out.append('</a>')

        return ''.join(out)

    def code(self, text):
        text = self.doSpecial(text, '<code>', '</code>', self.fCode)
        text = self.doSpecial(text, '@', '@', self.fCode)
        text = self.doSpecial(text, '<pre>', '</pre>', self.fPre)
        return text

    def fCode(self, match):
        before, text, after = match.groups()
        if after is None:
            after = ''
        # text needs to be escaped
        if not self.restricted:
            text = self.encode_html(text)
        return ''.join([before, self.shelve('<code>%s</code>' % text), after])

    def fPre(self, match):
        before, text, after = match.groups()
        if after is None:
            after = ''
        # text needs to be escapedd
        if not self.restricted:
            text = self.encode_html(text)
        return ''.join([before, '<pre>', self.shelve(text), '</pre>', after])

    def doSpecial(self, text, start, end, method=None):
        if method is None:
            method = self.fSpecial
        pattern = re.compile(r'(^|\s|[\[({>])%s(.*?)%s(\s|$|[\])}])?' % (re.escape(start), re.escape(end)), re.M|re.S)
        return pattern.sub(method, text)

    def fSpecial(self, match):
        """
        special blocks like notextile or code
        """
        before, text, after = match.groups()
        if after is None:
            after = ''
        return ''.join([before, self.shelve(self.encode_html(text)), after])

    def noTextile(self, text):
        text = self.doSpecial(text, '<notextile>', '</notextile>', self.fTextile)
        return self.doSpecial(text, '==', '==', self.fTextile)

    def fTextile(self, match):
        before, notextile, after = match.groups()
        if after is None:
            after = ''
        return ''.join([before, self.shelve(notextile), after])


def textile(text, head_offset=0, html_type='xhtml', encoding=None, output=None):
    """
    this function takes additional parameters:
    head_offset - offset to apply to heading levels (default: 0)
    html_type - 'xhtml' or 'html' style tags (default: 'xhtml')
    """
    return Textile().textile(text, head_offset=head_offset,
                             html_type=html_type)


def textile_restricted(text, lite=True, noimage=True, html_type='xhtml'):
    """
    Restricted version of Textile designed for weblog comments and other
    untrusted input.

    Raw HTML is escaped.
    Style attributes are disabled.
    rel='nofollow' is added to external links.

    When lite=True is set (the default):
    Block tags are restricted to p, bq, and bc.
    Lists and tables are disabled.

    When noimage=True is set (the default):
    Image tags are disabled.

    """
    return Textile(restricted=True, lite=lite,
                   noimage=noimage).textile(text, rel='nofollow',
                                            html_type=html_type)
