#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2013, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from urlparse import urlparse
from collections import Counter, OrderedDict
from functools import partial
from operator import itemgetter

from lxml import etree
from lxml.builder import ElementMaker

from calibre import __version__
from calibre.ebooks.oeb.base import XPath, uuid_id, xml2text, NCX, NCX_NS, XML, XHTML, XHTML_NS, serialize
from calibre.ebooks.oeb.polish.errors import MalformedMarkup
from calibre.ebooks.oeb.polish.utils import guess_type
from calibre.ebooks.oeb.polish.opf import set_guide_item, get_book_language
from calibre.ebooks.oeb.polish.pretty import pretty_html_tree
from calibre.translations.dynamic import translate
from calibre.utils.localization import get_lang, canonicalize_lang, lang_as_iso639_1

ns = etree.FunctionNamespace('calibre_xpath_extensions')
ns.prefix = 'calibre'
ns['lower-case'] = lambda c, x: x.lower() if hasattr(x, 'lower') else x


class TOC(object):

    def __init__(self, title=None, dest=None, frag=None):
        self.title, self.dest, self.frag = title, dest, frag
        self.dest_exists = self.dest_error = None
        if self.title:
            self.title = self.title.strip()
        self.parent = None
        self.children = []

    def add(self, title, dest, frag=None):
        c = TOC(title, dest, frag)
        self.children.append(c)
        c.parent = self
        return c

    def remove(self, child):
        self.children.remove(child)
        child.parent = None

    def remove_from_parent(self):
        if self.parent is None:
            return
        idx = self.parent.children.index(self)
        for child in reversed(self.children):
            child.parent = self.parent
            self.parent.children.insert(idx, child)
        self.parent.children.remove(self)
        self.parent = None

    def __iter__(self):
        for c in self.children:
            yield c

    def __len__(self):
        return len(self.children)

    def iterdescendants(self):
        for child in self:
            yield child
            for gc in child.iterdescendants():
                yield gc

    @property
    def depth(self):
        """The maximum depth of the navigation tree rooted at this node."""
        try:
            return max(node.depth for node in self) + 1
        except ValueError:
            return 1

    def get_lines(self, lvl=0):
        frag = ('#'+self.frag) if self.frag else ''
        ans = [(u'\t'*lvl) + u'TOC: %s --> %s%s'%(self.title, self.dest, frag)]
        for child in self:
            ans.extend(child.get_lines(lvl+1))
        return ans

    def __str__(self):
        return b'\n'.join([x.encode('utf-8') for x in self.get_lines()])

def child_xpath(tag, name):
    return tag.xpath('./*[calibre:lower-case(local-name()) = "%s"]'%name)


def add_from_navpoint(container, navpoint, parent, ncx_name):
    dest = frag = text = None
    nl = child_xpath(navpoint, 'navlabel')
    if nl:
        nl = nl[0]
        text = ''
        for txt in child_xpath(nl, 'text'):
            text += etree.tostring(txt, method='text',
                    encoding=unicode, with_tail=False)
    content = child_xpath(navpoint, 'content')
    if content:
        content = content[0]
        href = content.get('src', None)
        if href:
            dest = container.href_to_name(href, base=ncx_name)
            frag = urlparse(href).fragment or None
    return parent.add(text or None, dest or None, frag or None)


def process_ncx_node(container, node, toc_parent, ncx_name):
    for navpoint in node.xpath('./*[calibre:lower-case(local-name()) = "navpoint"]'):
        child = add_from_navpoint(container, navpoint, toc_parent, ncx_name)
        if child is not None:
            process_ncx_node(container, navpoint, child, ncx_name)


def parse_ncx(container, ncx_name):
    root = container.parsed(ncx_name)
    toc_root = TOC()
    navmaps = root.xpath('//*[calibre:lower-case(local-name()) = "navmap"]')
    if navmaps:
        process_ncx_node(container, navmaps[0], toc_root, ncx_name)
    toc_root.lang = toc_root.uid = None
    for attr, val in root.attrib.iteritems():
        if attr.endswith('lang'):
            toc_root.lang = unicode(val)
            break
    for uid in root.xpath('//*[calibre:lower-case(local-name()) = "meta" and @name="dtb:uid"]/@content'):
        if uid:
            toc_root.uid = unicode(uid)
            break
    return toc_root


def verify_toc_destinations(container, toc):
    anchor_map = {}
    anchor_xpath = XPath('//*/@id|//h:a/@name')
    for item in toc.iterdescendants():
        name = item.dest
        if not name:
            item.dest_exists = False
            item.dest_error = _('No file named %s exists')%name
            continue
        try:
            root = container.parsed(name)
        except KeyError:
            item.dest_exists = False
            item.dest_error = _('No file named %s exists')%name
            continue
        if not hasattr(root, 'xpath'):
            item.dest_exists = False
            item.dest_error = _('No HTML file named %s exists')%name
            continue
        if not item.frag:
            item.dest_exists = True
            continue
        if name not in anchor_map:
            anchor_map[name] = frozenset(anchor_xpath(root))
        item.dest_exists = item.frag in anchor_map[name]
        if not item.dest_exists:
            item.dest_error = _(
                'The anchor %(a)s does not exist in file %(f)s')%dict(
                a=item.frag, f=name)


def find_existing_toc(container):
    toc = container.opf_xpath('//opf:spine/@toc')
    if toc:
        toc = container.manifest_id_map.get(toc[0], None)
    if not toc:
        ncx = guess_type('a.ncx')
        toc = container.manifest_type_map.get(ncx, [None])[0]
    if not toc:
        return None
    return toc


def get_toc(container, verify_destinations=True):
    toc = find_existing_toc(container)
    if toc is None or not container.has_name(toc):
        ans = TOC()
        ans.lang = ans.uid = ans.toc_file_name = None
        return ans
    ans = parse_ncx(container, toc)
    ans.toc_file_name = toc
    if verify_destinations:
        verify_toc_destinations(container, ans)
    return ans

def ensure_id(elem):
    if elem.tag == XHTML('a'):
        anchor = elem.get('name', None)
        if anchor:
            return False, anchor
    elem_id = elem.get('id', None)
    if elem_id:
        return False, elem_id
    elem.set('id', 'u' + uuid_id())
    return True, elem.get('id')

def elem_to_toc_text(elem):
    text = xml2text(elem).strip()
    if not text:
        text = elem.get('title', '')
    if not text:
        text = elem.get('alt', '')
    text = re.sub(r'\s+', ' ', text.strip())
    text = text[:1000].strip()
    if not text:
        text = _('(Untitled)')
    return text

def item_at_top(elem):
    try:
        body = XPath('//h:body')(elem.getroottree().getroot())[0]
    except (TypeError, IndexError, KeyError, AttributeError):
        return False
    tree = body.getroottree()
    path = tree.getpath(elem)
    for el in body.iterdescendants(etree.Element):
        epath = tree.getpath(el)
        if epath == path:
            break
        try:
            if el.tag.endswith('}img') or (el.text and el.text.strip()):
                return False
        except:
            return False
        if not path.startswith(epath):
            # Only check tail of non-parent elements
            if el.tail and el.tail.strip():
                return False
    return True

def from_xpaths(container, xpaths):
    '''
    Generate a Table of Contents from a list of XPath expressions. Each
    expression in the list corresponds to a level of the generate ToC. For
    example: :code:`['//h:h1', '//h:h2', '//h:h3']` will generate a three level
    table of contents from the ``<h1>``, ``<h2>`` and ``<h3>`` tags.
    '''
    tocroot = TOC()
    xpaths = [XPath(xp) for xp in xpaths]
    level_prev = {i+1:None for i in xrange(len(xpaths))}
    level_prev[0] = tocroot

    # Find those levels that have no elements in all spine items
    maps = OrderedDict()
    empty_levels = {i+1 for i, xp in enumerate(xpaths)}
    for spinepath in container.spine_items:
        name = container.abspath_to_name(spinepath)
        root = container.parsed(name)
        level_item_map = maps[name] = {i+1:frozenset(xp(root)) for i, xp in enumerate(xpaths)}
        for lvl, elems in level_item_map.iteritems():
            if elems:
                empty_levels.discard(lvl)
    # Remove empty levels from all level_maps
    if empty_levels:
        for name, lmap in tuple(maps.iteritems()):
            lmap = {lvl:items for lvl, items in lmap.iteritems() if lvl not in empty_levels}
            lmap = sorted(lmap.iteritems(), key=itemgetter(0))
            lmap = {i+1:items for i, (l, items) in enumerate(lmap)}
            maps[name] = lmap

    for name, level_item_map in maps.iteritems():
        root = container.parsed(name)
        item_level_map = {e:i for i, elems in level_item_map.iteritems() for e in elems}
        item_dirtied = False

        for item in root.iterdescendants(etree.Element):
            lvl = plvl = item_level_map.get(item, None)
            if lvl is None:
                continue
            parent = None
            while parent is None:
                plvl -= 1
                parent = level_prev[plvl]
            lvl = plvl + 1
            if item_at_top(item):
                dirtied, elem_id = False, None
            else:
                dirtied, elem_id = ensure_id(item)
            text = elem_to_toc_text(item)
            item_dirtied = dirtied or item_dirtied
            toc = parent.add(text, name, elem_id)
            toc.dest_exists = True
            level_prev[lvl] = toc
            for i in xrange(lvl+1, len(xpaths)+1):
                level_prev[i] = None

        if item_dirtied:
            container.commit_item(name, keep_parsed=True)

    return tocroot

def from_links(container):
    '''
    Generate a Table of Contents from links in the book.
    '''
    toc = TOC()
    link_path = XPath('//h:a[@href]')
    seen_titles, seen_dests = set(), set()
    for spinepath in container.spine_items:
        name = container.abspath_to_name(spinepath)
        root = container.parsed(name)
        for a in link_path(root):
            href = a.get('href')
            if not href or not href.strip():
                continue
            dest = container.href_to_name(href, base=name)
            frag = href.rpartition('#')[-1] or None
            if (dest, frag) in seen_dests:
                continue
            seen_dests.add((dest, frag))
            text = elem_to_toc_text(a)
            if text in seen_titles:
                continue
            seen_titles.add(text)
            toc.add(text, dest, frag=frag)
    verify_toc_destinations(container, toc)
    for child in toc:
        if not child.dest_exists:
            toc.remove(child)
    return toc

def find_text(node):
    LIMIT = 200
    pat = re.compile(r'\s+')
    for child in node:
        if isinstance(child, etree._Element):
            text = xml2text(child).strip()
            text = pat.sub(' ', text)
            if len(text) < 1:
                continue
            if len(text) > LIMIT:
                # Look for less text in a child of this node, recursively
                ntext = find_text(child)
                return ntext or (text[:LIMIT] + '...')
            else:
                return text

def from_files(container):
    '''
    Generate a Table of Contents from files in the book.
    '''
    toc = TOC()
    for i, spinepath in enumerate(container.spine_items):
        name = container.abspath_to_name(spinepath)
        root = container.parsed(name)
        body = XPath('//h:body')(root)
        if not body:
            continue
        text = find_text(body[0])
        if not text:
            text = name.rpartition('/')[-1]
            if i == 0 and text.rpartition('.')[0].lower() in {'titlepage', 'cover'}:
                text = _('Cover')
        toc.add(text, name)
    return toc

def node_from_loc(root, locs, totals=None):
    node = root.xpath('//*[local-name()="body"]')[0]
    for i, loc in enumerate(locs):
        children = tuple(node.iterchildren(etree.Element))
        if totals is not None and totals[i] != len(children):
            raise MalformedMarkup()
        node = children[loc]
    return node

def add_id(container, name, loc, totals=None):
    root = container.parsed(name)
    try:
        node = node_from_loc(root, loc, totals=totals)
    except MalformedMarkup:
        # The webkit HTML parser and the container parser have yielded
        # different node counts, this can happen if the file is valid XML
        # but contains constructs like nested <p> tags. So force parse it
        # with the HTML 5 parser and try again.
        raw = container.raw_data(name)
        root = container.parse_xhtml(raw, fname=name, force_html5_parse=True)
        try:
            node = node_from_loc(root, loc, totals=totals)
        except MalformedMarkup:
            raise MalformedMarkup(_('The file %s has malformed markup. Try running the Fix HTML tool'
                                    ' before editing.') % name)
        container.replace(name, root)

    node.set('id', node.get('id', 'u' + uuid_id()))
    container.commit_item(name, keep_parsed=True)
    return node.get('id')

def create_ncx(toc, to_href, btitle, lang, uid):
    lang = lang.replace('_', '-')
    ncx = etree.Element(NCX('ncx'),
        attrib={'version': '2005-1', XML('lang'): lang},
        nsmap={None: NCX_NS})
    head = etree.SubElement(ncx, NCX('head'))
    etree.SubElement(head, NCX('meta'),
        name='dtb:uid', content=unicode(uid))
    etree.SubElement(head, NCX('meta'),
        name='dtb:depth', content=str(toc.depth))
    generator = ''.join(['calibre (', __version__, ')'])
    etree.SubElement(head, NCX('meta'),
        name='dtb:generator', content=generator)
    etree.SubElement(head, NCX('meta'), name='dtb:totalPageCount', content='0')
    etree.SubElement(head, NCX('meta'), name='dtb:maxPageNumber', content='0')
    title = etree.SubElement(ncx, NCX('docTitle'))
    text = etree.SubElement(title, NCX('text'))
    text.text = btitle
    navmap = etree.SubElement(ncx, NCX('navMap'))
    spat = re.compile(r'\s+')

    play_order = Counter()

    def process_node(xml_parent, toc_parent):
        for child in toc_parent:
            play_order['c'] += 1
            point = etree.SubElement(xml_parent, NCX('navPoint'), id='num_%d' % play_order['c'],
                            playOrder=str(play_order['c']))
            label = etree.SubElement(point, NCX('navLabel'))
            title = child.title
            if title:
                title = spat.sub(' ', title)
            etree.SubElement(label, NCX('text')).text = title
            if child.dest:
                href = to_href(child.dest)
                if child.frag:
                    href += '#'+child.frag
                etree.SubElement(point, NCX('content'), src=href)
            process_node(point, child)

    process_node(navmap, toc)
    return ncx


def commit_toc(container, toc, lang=None, uid=None):
    tocname = find_existing_toc(container)
    if tocname is None:
        item = container.generate_item('toc.ncx', id_prefix='toc')
        tocname = container.href_to_name(item.get('href'),
                                         base=container.opf_name)
    if not lang:
        lang = get_lang()
        for l in container.opf_xpath('//dc:language'):
            l = canonicalize_lang(xml2text(l).strip())
            if l:
                lang = l
                lang = lang_as_iso639_1(l) or l
                break
    lang = lang_as_iso639_1(lang) or lang
    if not uid:
        uid = uuid_id()
        eid = container.opf.get('unique-identifier', None)
        if eid:
            m = container.opf_xpath('//*[@id="%s"]'%eid)
            if m:
                uid = 'u' + xml2text(m[0])

    title = _('Table of Contents')
    m = container.opf_xpath('//dc:title')
    if m:
        x = xml2text(m[0]).strip()
        title = x or title

    to_href = partial(container.name_to_href, base=tocname)
    root = create_ncx(toc, to_href, title, lang, uid)
    container.replace(tocname, root)
    container.pretty_print.add(tocname)

def remove_names_from_toc(container, names):
    toc = get_toc(container)
    if len(toc) == 0:
        return False
    remove = []
    names = frozenset(names)
    for node in toc.iterdescendants():
        if node.dest in names:
            remove.append(node)
    if remove:
        for node in reversed(remove):
            node.remove_from_parent()
        commit_toc(container, toc)
        return True
    return False

def find_inline_toc(container):
    for name, linear in container.spine_names:
        if container.parsed(name).xpath('//*[local-name()="body" and @id="calibre_generated_inline_toc"]'):
            return name

def toc_to_html(toc, container, toc_name, title, lang=None):

    def process_node(html_parent, toc, level=1, indent='  ', style_level=2):
        li = html_parent.makeelement(XHTML('li'))
        li.tail = '\n'+ (indent*level)
        html_parent.append(li)
        name, frag = toc.dest, toc.frag
        href = '#'
        if name:
            href = container.name_to_href(name, toc_name)
            if frag:
                href += '#' + frag
        a = li.makeelement(XHTML('a'), href=href)
        a.text = toc.title
        li.append(a)
        if len(toc) > 0:
            parent = li.makeelement(XHTML('ul'))
            parent.set('class', 'level%d' % (style_level))
            li.append(parent)
            a.tail = '\n\n' + (indent*(level+2))
            parent.text = '\n'+(indent*(level+3))
            parent.tail = '\n\n' + (indent*(level+1))
            for child in toc:
                process_node(parent, child, level+3, style_level=style_level + 1)
            parent[-1].tail = '\n' + (indent*(level+2))

    E = ElementMaker(namespace=XHTML_NS, nsmap={None:XHTML_NS})
    html = E.html(
        E.head(
            E.title(title),
            E.style(P('templates/inline_toc_styles.css', data=True), type='text/css'),
        ),
        E.body(
            E.h2(title),
            E.ul(),
            id="calibre_generated_inline_toc",
        )
    )

    ul = html[1][1]
    ul.set('class', 'level1')
    for child in toc:
        process_node(ul, child)
    if lang:
        html.set('lang', lang)
    pretty_html_tree(container, html)
    return html

def create_inline_toc(container, title=None):
    '''
    Create an inline (HTML) Table of Contents from an existing NCX table of contents.

    :param title: The title for this table of contents.
    '''
    lang = get_book_language(container)
    default_title = 'Table of Contents'
    if lang:
        lang = lang_as_iso639_1(lang) or lang
        default_title = translate(lang, default_title)
    title = title or default_title
    toc = get_toc(container)
    if len(toc) == 0:
        return None
    toc_name = find_inline_toc(container)

    name = toc_name
    html = toc_to_html(toc, container, name, title, lang)
    raw = serialize(html, 'text/html')
    if name is None:
        name, c = 'toc.xhtml', 0
        while container.has_name(name):
            c += 1
            name = 'toc%d.xhtml' % c
        container.add_file(name, raw, spine_index=0)
    else:
        with container.open(name, 'wb') as f:
            f.write(raw)
    set_guide_item(container, 'toc', title, name, frag='calibre_generated_inline_toc')
    return name

