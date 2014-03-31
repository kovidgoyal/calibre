#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from operator import itemgetter

from lxml import etree

from calibre.ebooks.docx.names import XPath, expand
from calibre.utils.icu import partition_by_first_letter, sort_key

def get_applicable_xe_fields(index, xe_fields):
    iet = index.get('entry-type', None)
    xe_fields = [xe for xe in xe_fields if xe.get('entry-type', None) == iet]

    lr = index.get('letter-range', None)
    if lr is not None:
        sl, el = lr.parition('-')[0::2]
        sl, el = sl.strip(), el.strip()
        if sl and el:
            def inrange(text):
                return sl <= text[0] <= el
            xe_fields = [xe for xe in xe_fields if inrange(xe.get('text', ''))]

    bmark = index.get('bookmark', None)
    if bmark is None:
        return xe_fields
    attr = expand('w:name')
    bookmarks = {b for b in XPath('//w:bookmarkStart')(xe_fields[0]['start_elem']) if b.get(attr, None) == bmark}
    ancestors = XPath('ancestor::w:bookmarkStart')

    def contained(xe):
        # Check if the xe field is contained inside a bookmark with the
        # specified name
        return bool(set(ancestors(xe['start_elem'])) & bookmarks)

    return [xe for xe in xe_fields if contained(xe)]

def make_block(style, parent, pos):
    p = parent.makeelement(expand('w:p'))
    parent.insert(pos, p)
    if style is not None:
        ppr = p.makeelement(expand('w:pPr'))
        p.append(ppr)
        ps = ppr.makeelement(expand('w:pStyle'))
        ppr.append(ps)
        ps.set(expand('w:val'), style)
    r = p.makeelement(expand('w:r'))
    p.append(r)
    t = r.makeelement(expand('w:t'))
    t.set(expand('xml:space'), 'preserve')
    r.append(t)
    return p, t

def add_xe(xe, t):
    text = xe.get('text', '')
    pt = xe.get('page-number-text', None)
    t.text = text or ' '
    if pt:
        p = t.getparent().getparent()
        r = p.makeelement(expand('w:r'))
        p.append(r)
        t2 = r.makeelement(expand('w:t'))
        t2.set(expand('xml:space'), 'preserve')
        t2.text = ' [%s]' % pt
        r.append(t2)
    return xe['anchor'], t.getparent()

def process_index(field, index, xe_fields, log):
    '''
    We remove all the word generated index markup and replace it with our own
    that is more suitable for an ebook.
    '''
    styles = []
    heading_text = index.get('heading', None)
    heading_style = 'IndexHeading'
    start_pos = None
    for elem in field.contents:
        if elem.tag.endswith('}p'):
            s = XPath('descendant::pStyle/@w:val')(elem)
            if s:
                styles.append(s[0])
            p = elem.getparent()
            if start_pos is None:
                start_pos = (p, p.index(elem))
            p.remove(elem)

    xe_fields = get_applicable_xe_fields(index, xe_fields)
    if not xe_fields:
        return
    if heading_text is not None:
        groups = partition_by_first_letter(xe_fields, key=itemgetter('text'))
        items = []
        for key, fields in groups.iteritems():
            items.append(key), items.extend(fields)
        if styles:
            heading_style = styles[0]
    else:
        items = sorted(xe_fields, key=lambda x:sort_key(x['text']))

    hyperlinks = []
    blocks = []
    for item in reversed(items):
        is_heading = not isinstance(item, dict)
        style = heading_style if is_heading else None
        p, t = make_block(style, *start_pos)
        if is_heading:
            text = heading_text
            if text.lower().startswith('a'):
                text = item + text[1:]
            t.text = text
        else:
            hyperlinks.append(add_xe(item, t))
            blocks.append(p)

    return hyperlinks, blocks

def split_up_block(block, a, text, parts):
    prefix = parts[:-1]
    a.text = parts[-1]
    parent = a.getparent()
    style = 'display:block; margin-left: %.3gem'
    for i, prefix in enumerate(prefix):
        m = 1.5 * i
        span = parent.makeelement('span', style=style % m)
        parent.append(span)
        span.text = prefix
    span = parent.makeelement('span', style=style % ((i + 1) * 1.5))
    parent.append(span)
    span.append(a)

def merge_blocks(prev_block, next_block, prev_path, next_path):
    pa, na = prev_block.xpath('descendant::a'), next_block.xpath('descendant::a[1]')
    if not pa or not na:
        return
    pa, na = pa[-1], na[0]
    if prev_path == next_path:
        # Put on same line with a comma
        pa.tail = ', '
        p = pa.getparent()
        p.insert(p.index(pa) + 1, na)
    else:
        # Add a line to the previous block
        ps, ns = pa.getparent(), na.getparent()
        p = ps.getparent()
        p.insert(p.index(ps) + 1, ns)
    next_block.getparent().remove(next_block)

def polish_index_markup(index, blocks):
    path_map = {}
    for block in blocks:
        cls = block.get('class', '') or ''
        block.set('class', (cls + ' index-entry').lstrip())
        a = block.xpath('descendant::a[1]')
        text = ''
        if a:
            text = etree.tostring(a[0], method='text', with_tail=False, encoding=unicode).strip()
        if ':' in text:
            path_map[block] = parts = filter(None, (x.strip() for x in text.split(':')))
            if len(parts) > 1:
                split_up_block(block, a[0], text, parts)
        else:
            path_map[block] = [text]

    prev_block = blocks[0]
    for block in blocks[1:]:
        pp, pn = path_map[prev_block], path_map[block]
        if pp == pn:
            merge_blocks(prev_block, block, pp, pn)
        elif len(pp) > 1 and len(pn) >= len(pp):
            if pn[:-1] in (pp[:-1], pp):
                merge_blocks(prev_block, block, pp, pn)
            # It's possible to have pn starting with pp but having more
            # than one extra entry, but until I see that in the wild, I'm not
            # going to bother
        prev_block = block

