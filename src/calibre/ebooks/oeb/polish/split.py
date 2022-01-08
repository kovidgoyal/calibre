#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'

import copy, os, re
from polyglot.builtins import string_or_bytes

from calibre.ebooks.oeb.base import barename, XPNSMAP, XPath, OPF, XHTML, OEB_DOCS
from calibre.ebooks.oeb.polish.errors import MalformedMarkup
from calibre.ebooks.oeb.polish.toc import node_from_loc
from calibre.ebooks.oeb.polish.replace import LinkRebaser
from polyglot.builtins import iteritems
from polyglot.urllib import urlparse


class AbortError(ValueError):
    pass


def in_table(node):
    while node is not None:
        if node.tag.endswith('}table'):
            return True
        node = node.getparent()
    return False


def adjust_split_point(split_point, log):
    '''
    Move the split point up its ancestor chain if it has no content
    before it. This handles the common case:
    <div id="chapter1"><h2>Chapter 1</h2>...</div> with a page break on the
    h2.
    '''
    sp = split_point
    while True:
        parent = sp.getparent()
        if (
            parent is None or
            barename(parent.tag) in {'body', 'html'} or
            (parent.text and parent.text.strip()) or
            parent.index(sp) > 0
        ):
            break
        sp = parent

    if sp is not split_point:
        log.debug('Adjusted split point to ancestor')

    return sp


def get_body(root):
    return root.find('h:body', namespaces=XPNSMAP)


def do_split(split_point, log, before=True):
    '''
    Split tree into a *before* and an *after* tree at ``split_point``.

    :param split_point: The Element at which to split
    :param before: If True tree is split before split_point, otherwise after split_point
    :return: before_tree, after_tree
    '''
    if before:
        # We cannot adjust for after since moving an after split point to a
        # parent will cause breakage if the parent contains any content
        # after the original split point
        split_point = adjust_split_point(split_point, log)
    tree         = split_point.getroottree()
    path         = tree.getpath(split_point)

    tree, tree2  = copy.deepcopy(tree), copy.deepcopy(tree)
    root, root2  = tree.getroot(), tree2.getroot()
    body, body2  = map(get_body, (root, root2))
    split_point  = root.xpath(path)[0]
    split_point2 = root2.xpath(path)[0]

    def nix_element(elem, top=True):
        # Remove elem unless top is False in which case replace elem by its
        # children
        parent = elem.getparent()
        if top:
            parent.remove(elem)
        else:
            index = parent.index(elem)
            parent[index:index+1] = list(elem.iterchildren())

    # Tree 1
    hit_split_point = False
    keep_descendants = False
    split_point_descendants = frozenset(split_point.iterdescendants())
    for elem in tuple(body.iterdescendants()):
        if elem is split_point:
            hit_split_point = True
            if before:
                nix_element(elem)
            else:
                # We want to keep the descendants of the split point in
                # Tree 1
                keep_descendants = True
                # We want the split point element, but not its tail
                elem.tail = '\n'

            continue
        if hit_split_point:
            if keep_descendants:
                if elem in split_point_descendants:
                    # elem is a descendant keep it
                    continue
                else:
                    # We are out of split_point, so prevent further set
                    # lookups of split_point_descendants
                    keep_descendants = False
            nix_element(elem)

    # Tree 2
    ancestors = frozenset(XPath('ancestor::*')(split_point2))
    for elem in tuple(body2.iterdescendants()):
        if elem is split_point2:
            if not before:
                # Keep the split point element's tail, if it contains non-whitespace
                # text
                tail = elem.tail
                if tail and not tail.isspace():
                    parent = elem.getparent()
                    idx = parent.index(elem)
                    if idx == 0:
                        parent.text = (parent.text or '') + tail
                    else:
                        sib = parent[idx-1]
                        sib.tail = (sib.tail or '') + tail
                # Remove the element itself
                nix_element(elem)
            break
        if elem in ancestors:
            # We have to preserve the ancestors as they could have CSS
            # styles that are inherited/applicable, like font or
            # width. So we only remove the text, if any.
            elem.text = '\n'
        else:
            nix_element(elem, top=False)

    body2.text = '\n'

    return tree, tree2


class SplitLinkReplacer:

    def __init__(self, base, bottom_anchors, top_name, bottom_name, container):
        self.bottom_anchors, self.bottom_name = bottom_anchors, bottom_name
        self.container, self.top_name = container, top_name
        self.base = base
        self.replaced = False

    def __call__(self, url):
        if url and url.startswith('#'):
            return url
        name = self.container.href_to_name(url, self.base)
        if name != self.top_name:
            return url
        purl = urlparse(url)
        if purl.fragment and purl.fragment in self.bottom_anchors:
            url = self.container.name_to_href(self.bottom_name, self.base) + '#' + purl.fragment
            self.replaced = True
        return url


def split(container, name, loc_or_xpath, before=True, totals=None):
    '''
    Split the file specified by name at the position specified by loc_or_xpath.
    Splitting automatically migrates all links and references to the affected
    files.

    :param loc_or_xpath: Should be an XPath expression such as
        //h:div[@id="split_here"]. Can also be a *loc* which is used internally to
        implement splitting in the preview panel.
    :param before: If True the split occurs before the identified element otherwise after it.
    :param totals: Used internally
    '''

    root = container.parsed(name)
    if isinstance(loc_or_xpath, str):
        split_point = root.xpath(loc_or_xpath)[0]
    else:
        try:
            split_point = node_from_loc(root, loc_or_xpath, totals=totals)
        except MalformedMarkup:
            # The webkit HTML parser and the container parser have yielded
            # different node counts, this can happen if the file is valid XML
            # but contains constructs like nested <p> tags. So force parse it
            # with the HTML 5 parser and try again.
            raw = container.raw_data(name)
            root = container.parse_xhtml(raw, fname=name, force_html5_parse=True)
            try:
                split_point = node_from_loc(root, loc_or_xpath, totals=totals)
            except MalformedMarkup:
                raise MalformedMarkup(_('The file %s has malformed markup. Try running the Fix HTML tool'
                                        ' before splitting') % name)
            container.replace(name, root)
    if in_table(split_point):
        raise AbortError('Cannot split inside tables')
    if split_point.tag.endswith('}body'):
        raise AbortError('Cannot split on the <body> tag')
    tree1, tree2 = do_split(split_point, container.log, before=before)
    root1, root2 = tree1.getroot(), tree2.getroot()
    anchors_in_top = frozenset(root1.xpath('//*/@id')) | frozenset(root1.xpath('//*/@name')) | {''}
    anchors_in_bottom = frozenset(root2.xpath('//*/@id')) | frozenset(root2.xpath('//*/@name'))
    base, ext = name.rpartition('.')[0::2]
    base = re.sub(r'_split\d+$', '', base)
    nname, s = None, 0
    while not nname or container.exists(nname):
        s += 1
        nname = '%s_split%d.%s' % (base, s, ext)
    manifest_item = container.generate_item(nname, media_type=container.mime_map[name])
    bottom_name = container.href_to_name(manifest_item.get('href'), container.opf_name)

    # Fix links in the split trees
    for r in (root1, root2):
        for a in r.xpath('//*[@href]'):
            url = a.get('href')
            if url.startswith('#'):
                fname = name
            else:
                fname = container.href_to_name(url, name)
            if fname == name:
                purl = urlparse(url)
                if purl.fragment in anchors_in_top:
                    if r is root2:
                        a.set('href', f'{container.name_to_href(name, bottom_name)}#{purl.fragment}')
                    else:
                        a.set('href', '#' + purl.fragment)
                elif purl.fragment in anchors_in_bottom:
                    if r is root1:
                        a.set('href', f'{container.name_to_href(bottom_name, name)}#{purl.fragment}')
                    else:
                        a.set('href', '#' + purl.fragment)

    # Fix all links in the container that point to anchors in the bottom tree
    for fname, media_type in iteritems(container.mime_map):
        if fname not in {name, bottom_name}:
            repl = SplitLinkReplacer(fname, anchors_in_bottom, name, bottom_name, container)
            container.replace_links(fname, repl)

    container.replace(name, root1)
    container.replace(bottom_name, root2)

    spine = container.opf_xpath('//opf:spine')[0]
    for spine_item, spine_name, linear in container.spine_iter:
        if spine_name == name:
            break
    index = spine.index(spine_item) + 1

    si = spine.makeelement(OPF('itemref'), idref=manifest_item.get('id'))
    if not linear:
        si.set('linear', 'no')
    container.insert_into_xml(spine, si, index=index)
    container.dirty(container.opf_name)
    return bottom_name


def multisplit(container, name, xpath, before=True):
    '''
    Split the specified file at multiple locations (all tags that match the specified XPath expression). See also: :func:`split`.
    Splitting automatically migrates all links and references to the affected
    files.

    :param before: If True the splits occur before the identified element otherwise after it.
    '''
    root = container.parsed(name)
    nodes = root.xpath(xpath, namespaces=XPNSMAP)
    if not nodes:
        raise AbortError(_('The expression %s did not match any nodes') % xpath)
    for split_point in nodes:
        if in_table(split_point):
            raise AbortError('Cannot split inside tables')
        if split_point.tag.endswith('}body'):
            raise AbortError('Cannot split on the <body> tag')

    for i, tag in enumerate(nodes):
        tag.set('calibre-split-point', str(i))

    current = name
    all_names = [name]
    for i in range(len(nodes)):
        current = split(container, current, '//*[@calibre-split-point="%d"]' % i, before=before)
        all_names.append(current)

    for x in all_names:
        for tag in container.parsed(x).xpath('//*[@calibre-split-point]'):
            tag.attrib.pop('calibre-split-point')
        container.dirty(x)

    return all_names[1:]


class MergeLinkReplacer:

    def __init__(self, base, anchor_map, master, container):
        self.container, self.anchor_map = container, anchor_map
        self.master = master
        self.base = base
        self.replaced = False

    def __call__(self, url):
        if url and url.startswith('#'):
            return url
        name = self.container.href_to_name(url, self.base)
        amap = self.anchor_map.get(name, None)
        if amap is None:
            return url
        purl = urlparse(url)
        frag = purl.fragment or ''
        frag = amap.get(frag, frag)
        url = self.container.name_to_href(self.master, self.base) + '#' + frag
        self.replaced = True
        return url


def add_text(body, text):
    if len(body) > 0:
        body[-1].tail = (body[-1].tail or '') + text
    else:
        body.text = (body.text or '') + text


def all_anchors(root):
    return set(root.xpath('//*/@id')) | set(root.xpath('//*/@name'))


def all_stylesheets(container, name):
    for link in XPath('//h:head/h:link[@href]')(container.parsed(name)):
        name = container.href_to_name(link.get('href'), name)
        typ = link.get('type', 'text/css')
        if typ == 'text/css':
            yield name


def unique_anchor(seen_anchors, current):
    c = 0
    ans = current
    while ans in seen_anchors:
        c += 1
        ans = '%s_%d' % (current, c)
    return ans


def remove_name_attributes(root):
    # Remove all name attributes, replacing them with id attributes
    for elem in root.xpath('//*[@id and @name]'):
        del elem.attrib['name']
    for elem in root.xpath('//*[@name]'):
        elem.set('id', elem.attrib.pop('name'))


def merge_html(container, names, master, insert_page_breaks=False):
    p = container.parsed
    root = p(master)

    # Ensure master has a <head>
    head = root.find('h:head', namespaces=XPNSMAP)
    if head is None:
        head = root.makeelement(XHTML('head'))
        container.insert_into_xml(root, head, 0)

    seen_anchors = all_anchors(root)
    seen_stylesheets = set(all_stylesheets(container, master))
    master_body = p(master).findall('h:body', namespaces=XPNSMAP)[-1]
    master_base = os.path.dirname(master)
    anchor_map = {n:{} for n in names if n != master}
    first_anchor_map = {}

    for name in names:
        if name == master:
            continue
        # Insert new stylesheets into master
        for sheet in all_stylesheets(container, name):
            if sheet not in seen_stylesheets:
                seen_stylesheets.add(sheet)
                link = head.makeelement(XHTML('link'), rel='stylesheet', type='text/css', href=container.name_to_href(sheet, master))
                container.insert_into_xml(head, link)

        # Rebase links if master is in a different directory
        if os.path.dirname(name) != master_base:
            container.replace_links(name, LinkRebaser(container, name, master))

        root = p(name)
        children = []
        for body in p(name).findall('h:body', namespaces=XPNSMAP):
            children.append(body.text if body.text and body.text.strip() else '\n\n')
            children.extend(body)

        first_child = ''
        for first_child in children:
            if not isinstance(first_child, string_or_bytes):
                break
        if isinstance(first_child, string_or_bytes):
            # body contained only text, no tags
            first_child = body.makeelement(XHTML('p'))
            first_child.text, children[0] = children[0], first_child

        amap = anchor_map[name]
        remove_name_attributes(root)

        for elem in root.xpath('//*[@id]'):
            val = elem.get('id')
            if not val:
                continue
            if val in seen_anchors:
                nval = unique_anchor(seen_anchors, val)
                elem.set('id', nval)
                amap[val] = nval
            else:
                seen_anchors.add(val)

        if 'id' not in first_child.attrib:
            first_child.set('id', unique_anchor(seen_anchors, 'top'))
            seen_anchors.add(first_child.get('id'))
        first_anchor_map[name] = first_child.get('id')

        if insert_page_breaks:
            first_child.set('style', first_child.get('style', '') + '; page-break-before: always')

        amap[''] = first_child.get('id')

        # Fix links that point to local changed anchors
        for a in XPath('//h:a[starts-with(@href, "#")]')(root):
            q = a.get('href')[1:]
            if q in amap:
                a.set('href', '#' + amap[q])

        for child in children:
            if isinstance(child, string_or_bytes):
                add_text(master_body, child)
            else:
                master_body.append(copy.deepcopy(child))

        container.remove_item(name, remove_from_guide=False)

    # Fix all links in the container that point to merged files
    for fname, media_type in iteritems(container.mime_map):
        repl = MergeLinkReplacer(fname, anchor_map, master, container)
        container.replace_links(fname, repl)

    return first_anchor_map


def merge_css(container, names, master):
    p = container.parsed
    msheet = p(master)
    master_base = os.path.dirname(master)
    merged = set()

    for name in names:
        if name == master:
            continue
        # Rebase links if master is in a different directory
        if os.path.dirname(name) != master_base:
            container.replace_links(name, LinkRebaser(container, name, master))

        sheet = p(name)

        # Remove charset rules
        cr = [r for r in sheet.cssRules if r.type == r.CHARSET_RULE]
        [sheet.deleteRule(sheet.cssRules.index(r)) for r in cr]
        for rule in sheet.cssRules:
            msheet.add(rule)

        container.remove_item(name)
        merged.add(name)

    # Remove links to merged stylesheets in the html files, replacing with a
    # link to the master sheet
    for name, mt in iteritems(container.mime_map):
        if mt in OEB_DOCS:
            removed = False
            root = p(name)
            for link in XPath('//h:link[@href]')(root):
                q = container.href_to_name(link.get('href'), name)
                if q in merged:
                    container.remove_from_xml(link)
                    removed = True
            if removed:
                container.dirty(name)
            if removed and master not in set(all_stylesheets(container, name)):
                head = root.find('h:head', namespaces=XPNSMAP)
                if head is not None:
                    link = head.makeelement(XHTML('link'), type='text/css', rel='stylesheet', href=container.name_to_href(master, name))
                    container.insert_into_xml(head, link)


def merge(container, category, names, master):
    '''
    Merge the specified files into a single file, automatically migrating all
    links and references to the affected files. The file must all either be HTML or CSS files.

    :param category: Must be either ``'text'`` for HTML files or ``'styles'`` for CSS files
    :param names: The list of files to be merged
    :param master: Which of the merged files is the *master* file, that is, the file that will remain after merging.
    '''
    if category not in {'text', 'styles'}:
        raise AbortError('Cannot merge files of type: %s' % category)
    if len(names) < 2:
        raise AbortError('Must specify at least two files to be merged')
    if master not in names:
        raise AbortError('The master file (%s) must be one of the files being merged' % master)

    if category == 'text':
        merge_html(container, names, master)
    elif category == 'styles':
        merge_css(container, names, master)

    container.dirty(master)
