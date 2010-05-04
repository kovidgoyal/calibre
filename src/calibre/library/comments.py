#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re

from calibre.constants import preferred_encoding
from calibre.ebooks.BeautifulSoup import BeautifulSoup, Tag, NavigableString
from calibre import prepare_string_for_xml

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
    if not isinstance(comments, unicode):
        comments = comments.decode(preferred_encoding, 'replace')

    # Hackish - ignoring sentences ending or beginning in numbers to avoid
    # confusion with decimal points.

    # Explode lost CRs to \n\n
    for lost_cr in re.finditer('([a-z])([\.\?!])([A-Z])', comments):
        comments = comments.replace(lost_cr.group(),
                                    '%s%s\n\n%s' % (lost_cr.group(1),
                                                    lost_cr.group(2),
                                                    lost_cr.group(3)))

    # Convert \n\n to <p>s
    if re.search('\n\n', comments):
        soup = BeautifulSoup()
        split_ps = comments.split(u'\n\n')
        tsc = 0
        for p in split_ps:
            pTag = Tag(soup,'p')
            pTag.insert(0,p)
            soup.insert(tsc,pTag)
            tsc += 1
        comments = soup.renderContents(None)

    # Convert solo returns to <br />
    comments = re.sub('[\r\n]','<br />', comments)

    # Convert two hyphens to emdash
    comments = re.sub('--', '&mdash;', comments)
    soup = BeautifulSoup(comments)
    result = BeautifulSoup()
    rtc = 0
    open_pTag = False

    all_tokens = list(soup.contents)
    for token in all_tokens:
        if type(token) is NavigableString:
            if not open_pTag:
                pTag = Tag(result,'p')
                open_pTag = True
                ptc = 0
            pTag.insert(ptc,prepare_string_for_xml(token))
            ptc += 1

        elif token.name in ['br','b','i','em']:
            if not open_pTag:
                pTag = Tag(result,'p')
                open_pTag = True
                ptc = 0
            pTag.insert(ptc, token)
            ptc += 1

        else:
            if open_pTag:
                result.insert(rtc, pTag)
                rtc += 1
                open_pTag = False
                ptc = 0
            # Clean up NavigableStrings for xml
            sub_tokens = list(token.contents)
            for sub_token in sub_tokens:
                if type(sub_token) is NavigableString:
                    sub_token.replaceWith(prepare_string_for_xml(sub_token))
            result.insert(rtc, token)
            rtc += 1

    if open_pTag:
        result.insert(rtc, pTag)

    paras = result.findAll('p')
    for p in paras:
        p['class'] = 'description'

    return result.renderContents(encoding=None)

