#!/usr/bin/env python
# vim:fileencoding=utf-8


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

from operator import itemgetter

from lxml import etree

from calibre.utils.icu import partition_by_first_letter, sort_key
from polyglot.builtins import iteritems, filter


def get_applicable_xe_fields(index, xe_fields, XPath, expand):
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


def make_block(expand, style, parent, pos):
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


def add_xe(xe, t, expand):
    run = t.getparent()
    idx = run.index(t)
    t.text = xe.get('text') or ' '
    pt = xe.get('page-number-text', None)

    if pt:
        p = t.getparent().getparent()
        r = p.makeelement(expand('w:r'))
        p.append(r)
        t2 = r.makeelement(expand('w:t'))
        t2.set(expand('xml:space'), 'preserve')
        t2.text = ' [%s]' % pt
        r.append(t2)
    # put separate entries on separate lines
    run.insert(idx + 1, run.makeelement(expand('w:br')))
    return xe['anchor'], run


def process_index(field, index, xe_fields, log, XPath, expand):
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

    xe_fields = get_applicable_xe_fields(index, xe_fields, XPath, expand)
    if not xe_fields:
        return [], []
    if heading_text is not None:
        groups = partition_by_first_letter(xe_fields, key=itemgetter('text'))
        items = []
        for key, fields in iteritems(groups):
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
        p, t = make_block(expand, style, *start_pos)
        if is_heading:
            text = heading_text
            if text.lower().startswith('a'):
                text = item + text[1:]
            t.text = text
        else:
            hyperlinks.append(add_xe(item, t, expand))
            blocks.append(p)

    return hyperlinks, blocks


def split_up_block(block, a, text, parts, ldict):
    prefix = parts[:-1]
    a.text = parts[-1]
    parent = a.getparent()
    style = 'display:block; margin-left: %.3gem'
    for i, prefix in enumerate(prefix):
        m = 1.5 * i
        span = parent.makeelement('span', style=style % m)
        ldict[span]    = i
        parent.append(span)
        span.text = prefix
    span = parent.makeelement('span', style=style % ((i + 1) * 1.5))
    parent.append(span)
    span.append(a)
    ldict[span]    = len(prefix)


"""
The merge algorithm is a little tricky.
We start with a list of elementary blocks. Each is an HtmlElement, a p node
with a list of child nodes. The last child may be a link, and the earlier ones are
just text.
The list is in reverse order from what we want in the index.
There is a dictionary ldict which records the level of each child node.

Now we want to do a reduce-like operation, combining all blocks with the same
top level index entry into a single block representing the structure of all
references, subentries, etc. under that top entry.
Here's the algorithm.

Given a block p and the next block n, and the top level entries p1 and n1 in each
block, which we assume have the same text:

Start with (p, p1) and (n, n1).

Given (p, p1, ..., pk) and (n, n1, ..., nk) which we want to merge:

If there are no more levels in n, and we have a link in nk,
then add the link from nk to the links for pk.
This might be the first link for pk, or we might get a list of references.

Otherwise nk+1 is the next level in n. Look for a matching entry in p. It must have
the same text, it must follow pk, it must come before we find any other p entries at
the same level as pk, and it must have the same level as nk+1.

If we find such a matching entry, go back to the start with (p ... pk+1) and (n ... nk+1).

If there is no matching entry, then because of the original reversed order we want
to insert nk+1 and all following entries from n into p immediately following pk.
"""


def find_match(prev_block, pind, nextent, ldict):
    curlevel = ldict.get(prev_block[pind], -1)
    if curlevel < 0:
        return -1
    for p in range(pind+1, len(prev_block)):
        trylev = ldict.get(prev_block[p], -1)
        if trylev <= curlevel:
            return -1
        if trylev > (curlevel+1):
            continue
        if prev_block[p].text_content() == nextent.text_content():
            return p
    return -1


def add_link(pent, nent, ldict):
    na = nent.xpath('descendant::a[1]')
    # If there is no link, leave it as text
    if not na or len(na) == 0:
        return
    na = na[0]
    pa = pent.xpath('descendant::a')
    if pa and len(pa) > 0:
        # Put on same line with a comma
        pa = pa[-1]
        pa.tail = ', '
        p = pa.getparent()
        p.insert(p.index(pa) + 1, na)
    else:
        # substitute link na for plain text in pent
        pent.text = ""
        pent.append(na)


def merge_blocks(prev_block, next_block, pind, nind, next_path, ldict):
    # First elements match. Any more in next?
    if len(next_path) == (nind + 1):
        nextent = next_block[nind]
        add_link(prev_block[pind], nextent, ldict)
        return

    nind = nind + 1
    nextent = next_block[nind]
    prevent = find_match(prev_block, pind, nextent, ldict)
    if prevent > 0:
        merge_blocks(prev_block, next_block, prevent, nind, next_path, ldict)
        return

    # Want to insert elements into previous block
    while nind < len(next_block):
        # insert takes it out of old
        pind = pind + 1
        prev_block.insert(pind, next_block[nind])

    next_block.getparent().remove(next_block)


def polish_index_markup(index, blocks):
    # Blocks are in reverse order at this point
    path_map = {}
    ldict = {}
    for block in blocks:
        cls = block.get('class', '') or ''
        block.set('class', (cls + ' index-entry').lstrip())
        a = block.xpath('descendant::a[1]')
        text = ''
        if a:
            text = etree.tostring(a[0], method='text', with_tail=False, encoding='unicode').strip()
        if ':' in text:
            path_map[block] = parts = list(filter(None, (x.strip() for x in text.split(':'))))
            if len(parts) > 1:
                split_up_block(block, a[0], text, parts, ldict)
        else:
            # try using a span all the time
            path_map[block] = [text]
            parent = a[0].getparent()
            span = parent.makeelement('span', style='display:block; margin-left: 0em')
            parent.append(span)
            span.append(a[0])
            ldict[span] = 0

        for br in block.xpath('descendant::br'):
            br.tail = None

    # We want a single block for each main entry
    prev_block = blocks[0]
    for block in blocks[1:]:
        pp, pn = path_map[prev_block], path_map[block]
        if pp[0] == pn[0]:
            merge_blocks(prev_block, block, 0, 0, pn, ldict)
        else:
            prev_block = block
