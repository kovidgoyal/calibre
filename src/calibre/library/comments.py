#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
# License: GPLv3 Copyright: 2010, Kovid Goyal <kovid at kovidgoyal.net>


import re

from calibre import prepare_string_for_xml
from calibre.constants import preferred_encoding
from calibre.ebooks.BeautifulSoup import (
    BeautifulSoup, CData, Comment, Declaration, NavigableString,
    ProcessingInstruction
)
from calibre.utils.html2text import html2text
from polyglot.builtins import unicode_type

# Hackish - ignoring sentences ending or beginning in numbers to avoid
# confusion with decimal points.
lost_cr_pat = re.compile('([a-z])([\\.\\?!])([A-Z])')
lost_cr_exception_pat = re.compile(r'(Ph\.D)|(D\.Phil)|((Dr|Mr|Mrs|Ms)\.[A-Z])')
sanitize_pat = re.compile(r'<script|<table|<tr|<td|<th|<style|<iframe',
        re.IGNORECASE)


def comments_to_html(comments):
    '''
    Convert random comment text to normalized, xml-legal block of <p>s
    'plain text' returns as
    <p>plain text</p>

    'plain text with <i>minimal</i> <b>markup</b>' returns as
    <p>plain text with <i>minimal</i> <b>markup</b></p>

    '<p>pre-formatted text</p> returns untouched

    'A line of text\n\nFollowed by a line of text' returns as
    <p>A line of text</p>
    <p>Followed by a line of text</p>

    'A line of text.\nA second line of text.\rA third line of text' returns as
    <p>A line of text.<br />A second line of text.<br />A third line of text.</p>

    '...end of a paragraph.Somehow the break was lost...' returns as
    <p>...end of a paragraph.</p>
    <p>Somehow the break was lost...</p>

    Deprecated HTML returns as HTML via BeautifulSoup()

    '''
    if not comments:
        return u'<p></p>'
    if not isinstance(comments, unicode_type):
        comments = comments.decode(preferred_encoding, 'replace')

    if comments.lstrip().startswith('<'):
        # Comment is already HTML do not mess with it
        return comments

    if '<' not in comments:
        comments = prepare_string_for_xml(comments)
        parts = [u'<p class="description">%s</p>'%x.replace(u'\n', u'<br />')
                for x in comments.split('\n\n')]
        return '\n'.join(parts)

    if sanitize_pat.search(comments) is not None:
        try:
            return sanitize_comments_html(comments)
        except:
            import traceback
            traceback.print_exc()
            return u'<p></p>'

    # Explode lost CRs to \n\n
    comments = lost_cr_exception_pat.sub(lambda m: m.group().replace('.',
        '.\r'), comments)
    for lost_cr in lost_cr_pat.finditer(comments):
        comments = comments.replace(lost_cr.group(),
                                    '%s%s\n\n%s' % (lost_cr.group(1),
                                                    lost_cr.group(2),
                                                    lost_cr.group(3)))

    comments = comments.replace(u'\r', u'')
    # Convert \n\n to <p>s
    comments = comments.replace(u'\n\n', u'<p>')
    # Convert solo returns to <br />
    comments = comments.replace(u'\n', '<br />')
    # Convert two hyphens to emdash
    comments = comments.replace('--', '&mdash;')

    soup = BeautifulSoup('<div>' + comments + '</div>').find('div')
    result = BeautifulSoup('<div>')
    container = result.find('div')
    rtc = 0
    open_pTag = False

    all_tokens = list(soup.contents)
    inline_tags = ('br', 'b', 'i', 'em', 'strong', 'span', 'font', 'a', 'hr')
    for token in all_tokens:
        if isinstance(token,  (CData, Comment, Declaration, ProcessingInstruction)):
            continue
        if isinstance(token, NavigableString):
            if not open_pTag:
                pTag = result.new_tag('p')
                open_pTag = True
                ptc = 0
            pTag.insert(ptc, token)
            ptc += 1
        elif token.name in inline_tags:
            if not open_pTag:
                pTag = result.new_tag('p')
                open_pTag = True
                ptc = 0
            pTag.insert(ptc, token)
            ptc += 1
        else:
            if open_pTag:
                container.insert(rtc, pTag)
                rtc += 1
                open_pTag = False
                ptc = 0
            container.insert(rtc, token)
            rtc += 1

    if open_pTag:
        container.insert(rtc, pTag)

    for p in container.findAll('p'):
        p['class'] = 'description'

    return container.decode_contents()


def markdown(val):
    try:
        md = markdown.Markdown
    except AttributeError:
        from calibre.ebooks.markdown import Markdown
        md = markdown.Markdown = Markdown()
    return md.convert(val)


def merge_comments(one, two):
    return comments_to_html(one) + '\n\n' + comments_to_html(two)


def sanitize_comments_html(html):
    from calibre.ebooks.markdown import Markdown
    text = html2text(html)
    md = Markdown()
    html = md.convert(text)
    return html


def find_tests():
    import unittest

    class Test(unittest.TestCase):

        def test_comments_to_html(self):
            for pat, val in [
                    (b'lineone\n\nlinetwo',
                        '<p class="description">lineone</p>\n<p class="description">linetwo</p>'),

                    ('a <b>b&c</b>\nf',
                        '<p class="description">a <b>b&amp;c</b><br/>f</p>'),

                    ('a <?xml asd> b\n\ncd',
                        '<p class="description">a  b</p><p class="description">cd</p>'),
            ]:
                cval = comments_to_html(pat)
                self.assertEqual(cval, val)

    return unittest.defaultTestLoader.loadTestsFromTestCase(Test)
