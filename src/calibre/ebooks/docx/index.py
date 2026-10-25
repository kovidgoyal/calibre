#!/usr/bin/env python
# License: GPLv3 Copyright: 2014, Kovid Goyal <kovid at kovidgoyal.net>

from operator import itemgetter

from lxml import etree

from calibre.utils.icu import partition_by_first_letter, sort_key


def get_applicable_xe_fields(index, xe_fields, XPath, expand):
    iet = index.get('entry-type', None)
    xe_fields = [xe for xe in xe_fields if xe.get('entry-type', None) == iet]

    lr = index.get('letter-range', None)
    if lr is not None:
        sl, el = lr.partition('-')[0::2]
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
    t.text = xe.get('text') or ' '
    pt = xe.get('page-number-text', None)

    if pt:
        p = t.getparent().getparent()
        r = p.makeelement(expand('w:r'))
        p.append(r)
        t2 = r.makeelement(expand('w:t'))
        t2.set(expand('xml:space'), 'preserve')
        t2.text = f' [{pt}]'
        r.append(t2)
    return xe['anchor'], run


def process_index(field, index, xe_fields, log, XPath, expand):
    """
    We remove all the word generated index markup and replace it with our own
    that is more suitable for an ebook.
    """
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
        for key, fields in groups.items():
            items.append(key), items.extend(fields)
        if styles:
            heading_style = styles[0]
    else:
        items = sorted(xe_fields, key=lambda x: sort_key(x['text']))

    hyperlinks = []
    blocks = []
    for item in reversed(items):
        is_heading = not isinstance(item, dict)
        style = heading_style if is_heading else None
        assert start_pos is not None
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


def split_up_block(container, a, parts, ldict, tdict):
    style = 'display:block; margin-left: %.3gem'
    prefix = parts[:-1]
    # Move all existing content, such as the page number text, into the span
    # for the entry itself, so that the level spans are the only children of
    # container, which merge_blocks() relies on
    entry = container.makeelement('span', style=style % (len(prefix) * 1.5))
    entry.text, container.text = container.text, None
    for child in tuple(container):
        entry.append(child)
    for i, x in enumerate(prefix):
        span = container.makeelement('span', style=style % (1.5 * i))
        span.text = x
        ldict[span], tdict[span] = i, x
        container.append(span)
    container.append(entry)
    ldict[entry], tdict[entry] = len(prefix), parts[-1]


'''
The merge algorithm is a little tricky.
We start with a list of elementary blocks. Each is an HtmlElement, a p node
whose children are one span per level of the index entry. The last span
contains the link, and the earlier ones are just text.
The list is in reverse order from what we want in the index.
There is a dictionary ldict which records the level of each span and a
dictionary tdict which records the entry text of each span.

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
'''


def find_match(prev_block, pind, nextent, ldict, tdict):
    curlevel = ldict.get(prev_block[pind], -1)
    if curlevel < 0:
        return -1
    for p in range(pind + 1, len(prev_block)):
        trylev = ldict.get(prev_block[p], -1)
        if trylev <= curlevel:
            return -1
        if trylev > (curlevel + 1):
            continue
        # Compare entry text not text_content() as entries that have had
        # links merged into them contain multiple copies of the text
        if tdict.get(prev_block[p]) == tdict.get(nextent):
            return p
    return -1


def add_link(pent, nent):
    # Move the link and any associated content such as the page number text
    # from nent to pent. If there is no link, leave it as text.
    if not nent.xpath('descendant::a'):
        return
    children = tuple(nent)
    if pent.xpath('descendant::a'):
        # Put on same line with a comma. Blocks are merged in reverse order,
        # so put the links from nent first to keep references in document order.
        last = children[-1]
        last.tail = (last.tail or '').rstrip() + ', '
        for i, child in enumerate(children):
            pent.insert(i, child)
    else:
        # substitute link for plain text in pent
        pent.text = None
        for child in children:
            pent.append(child)


def merge_blocks(prev_block, next_block, pind, nind, next_path, ldict, tdict):
    # First elements match. Any more in next?
    if len(next_path) == (nind + 1):
        add_link(prev_block[pind], next_block[nind])
        return

    nind = nind + 1
    nextent = next_block[nind]
    prevent = find_match(prev_block, pind, nextent, ldict, tdict)
    if prevent > 0:
        merge_blocks(prev_block, next_block, prevent, nind, next_path, ldict, tdict)
        return

    # Want to insert elements into previous block
    while nind < len(next_block):
        # insert takes it out of old
        pind = pind + 1
        prev_block.insert(pind, next_block[nind])


def polish_index_markup(index, blocks):
    # Blocks are in reverse order at this point
    path_map = {}
    containers = {}
    ldict = {}
    tdict = {}
    for block in blocks:
        cls = block.get('class', '') or ''
        block.set('class', (cls + ' index-entry').lstrip())
        a = block.xpath('descendant::a[1]')
        if not a:
            # No link, leave the block as is
            continue
        a = a[0]
        text = etree.tostring(a, method='text', with_tail=False, encoding='unicode').strip()
        parts = [x.strip() for x in text.split(':')]
        parts = [x for x in parts if x] or [text]
        if ':' in text:
            a.text = parts[-1]
        path_map[block] = parts
        containers[block] = a.getparent()
        split_up_block(containers[block], a, parts, ldict, tdict)

    # We want a single block for each main entry
    blocks = [b for b in blocks if b in path_map]
    if not blocks:
        return
    prev_block = blocks[0]
    for block in blocks[1:]:
        pp, pn = path_map[prev_block], path_map[block]
        if pp[0] == pn[0]:
            merge_blocks(containers[prev_block], containers[block], 0, 0, pn, ldict, tdict)
            if not block.xpath('descendant::a'):
                # Everything in block has been merged into prev_block
                block.getparent().remove(block)
        else:
            prev_block = block

    # Put separate entries on separate lines. The spans are display:block but
    # adjacent spans with the same style are merged later in the conversion.
    for block in blocks:
        if block.getparent() is not None:
            for span in containers[block]:
                span.append(span.makeelement('br'))
