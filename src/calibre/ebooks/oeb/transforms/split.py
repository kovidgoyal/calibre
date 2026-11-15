# License: GPLv3 Copyright: 2008, Kovid Goyal kovid@kovidgoyal.net

'''
Splitting of the XHTML flows. Splitting can happen on page boundaries or can be
forced at "likely" locations to conform to size limitations. This transform
assumes a prior call to the flatcss transform.
'''

import collections
import copy
import functools
import os
import re
from collections import OrderedDict
from contextlib import suppress
from typing import TYPE_CHECKING, cast

from css_parser.css import CSSStyleSheet
from css_selectors import Select, SelectorError
from lxml import etree
from lxml.etree import XPath as _XPath

from calibre import as_unicode, force_unicode
from calibre.ebooks.epub import rules
from calibre.ebooks.oeb.base import OEB_STYLES, XHTML, rewrite_links, urldefrag, urlnormalize
from calibre.ebooks.oeb.base import XPNSMAP as NAMESPACES
from calibre.ebooks.oeb.polish.split import do_split, partition_by_body_siblings
from calibre.utils.localization import _
from polyglot.urllib import unquote

if TYPE_CHECKING:
    from optparse import Values

    from lxml.etree import _Element, _ElementTree

    from calibre.ebooks.oeb.base import TOC, Manifest, OEBBook

    type PageBreak = tuple[_XPath, bool]

XPath = functools.partial(_XPath, namespaces=NAMESPACES)

SPLIT_POINT_ATTR = 'csp'


def resolve_page_break_elements(
    ordered_ids: OrderedDict[str, tuple[object, bool]],
    root: _Element,
) -> list[tuple[_Element, bool]]:
    """Map page-break ids to elements with one document walk (O(D+N)).

    Completes the sibling-partition fast path: callers used to resolve each
    break with ``//*[@id=…]`` (O(N×D)), which dominated TOC-options converts
    on large flat Markdown bodies while partition itself stayed cheap.
    """
    wanted = frozenset(ordered_ids)
    id_to_elem: dict[str, _Element] = {}
    for elem in root.iter('*'):
        eid = elem.get('id')
        if eid is not None and eid in wanted and eid not in id_to_elem:
            id_to_elem[eid] = elem
            if len(id_to_elem) == len(wanted):
                break
    specs: list[tuple[_Element, bool]] = []
    for pb_id, (_pattern, before) in ordered_ids.items():
        elem = id_to_elem.get(pb_id)
        if elem is not None:
            specs.append((elem, before))
    return specs


def tostring(root: _Element) -> bytes:
    return etree.tostring(root, encoding='utf-8')


class SplitError(ValueError):
    def __init__(self, path: str, root: _Element) -> None:
        size = len(tostring(root)) / 1024.0
        ValueError.__init__(
            self,
            _('Could not find reasonable point at which to split: %(path)s Sub-tree size: %(size)d KB') % dict(path=path, size=size),
        )


class Split:
    def __init__(
        self, split_on_page_breaks: bool = True, page_breaks_xpath: str | None = None, max_flow_size: int = 0, remove_css_pagebreaks: bool = True
    ) -> None:
        self.split_on_page_breaks = split_on_page_breaks
        self.page_breaks_xpath = page_breaks_xpath
        self.max_flow_size = max_flow_size
        self.page_break_selectors: list[PageBreak] | set[tuple[str, bool]] | None = None
        self.remove_css_pagebreaks = remove_css_pagebreaks
        if self.page_breaks_xpath is not None:
            self.page_break_selectors = [(XPath(self.page_breaks_xpath), False)]

    def __call__(self, oeb: OEBBook, opts: Values) -> None:
        self.oeb = oeb
        self.log = oeb.log
        self.log('Splitting markup on page breaks and flow limits, if any...')
        self.opts = opts
        self.map: dict[str, collections.defaultdict[str | None, str]] = {}
        self.nav_href = getattr(opts, 'epub3_nav_href', '')
        self.existing_nav = getattr(opts, 'epub3_nav_parsed', None)
        output_supports_nav = False
        with suppress(Exception):
            output_supports_nav = int(opts.epub_version) >= 3

        def is_nav(item: Manifest.Item) -> bool:
            ans = item.href == self.nav_href and output_supports_nav
            if ans:
                self.log(f'Not splitting {self.nav_href} as it is the EPUB3 nav document')
            return ans

        for item in list(self.oeb.manifest.items):
            if item.spine_position is not None and etree.iselement(item.data) and not is_nav(item):
                self.split_item(item)

        self.fix_links()

    def split_item(self, item: Manifest.Item) -> None:
        page_breaks: list[PageBreak] = []
        page_break_ids: list[str] = []
        if self.split_on_page_breaks:
            page_breaks, page_break_ids = self.find_page_breaks(item)

        splitter = FlowSplitter(item, page_breaks, page_break_ids, self.max_flow_size, self.oeb, self.opts)
        if splitter.was_split:
            am = splitter.anchor_map
            self.map[item.href] = collections.defaultdict(am.default_factory, am)

    def find_page_breaks(self, item: Manifest.Item) -> tuple[list[PageBreak], list[str]]:
        if self.page_break_selectors is None:
            ignored = {'avoid', 'auto', 'inherit', 'never'}
            self.page_break_selectors = set()
            stylesheets: list[CSSStyleSheet] = []
            for x in self.oeb.manifest:
                if x.media_type in OEB_STYLES:
                    sheet = x.data
                    assert isinstance(sheet, CSSStyleSheet)  # media_type is in OEB_STYLES
                    stylesheets.append(sheet)
            for rule in rules(stylesheets):
                before = force_unicode(getattr(rule.style.getPropertyCSSValue('page-break-before'), 'cssText', '').strip().lower())
                after = force_unicode(getattr(rule.style.getPropertyCSSValue('page-break-after'), 'cssText', '').strip().lower())
                try:
                    if before and before not in ignored:
                        self.page_break_selectors.add((rule.selectorText, True))
                        if self.remove_css_pagebreaks:
                            rule.style.removeProperty('page-break-before')
                except Exception:
                    pass
                try:
                    if after and after not in ignored:
                        self.page_break_selectors.add((rule.selectorText, False))
                        if self.remove_css_pagebreaks:
                            rule.style.removeProperty('page-break-after')
                except Exception:
                    pass
        if not self.page_break_selectors:
            return [], []
        page_breaks = set()
        root = item.data
        assert isinstance(root, etree._Element)  # only called for items whose data is an element
        select = Select(root)
        body = root.xpath('//h:body', namespaces=NAMESPACES)
        if not body:
            return [], []
        descendants = frozenset(body[0].iterdescendants('*'))

        pb_before_map: dict[_Element, bool] = {}
        # css_selectors.Select can be pathologically slow on large flat bodies
        # (e.g. .calibre1 ≈ 7min on a 265k-node Markdown novel). Use XPath for
        # the common post-flatcss ".classname" form.
        simple_class = re.compile(r'^\.([A-Za-z_][\w-]*)$')

        def match_selector(selector: str | _XPath) -> list[_Element]:
            if isinstance(selector, str):
                m = simple_class.match(selector)
                if m is not None:
                    cls = m.group(1)
                    return root.xpath(
                        f'//*[contains(concat(" ", normalize-space(@class), " "), " {cls} ")]'
                    )
                return list(select(selector))
            return list(selector(root))

        for selector, before in self.page_break_selectors:
            try:
                matches = match_selector(selector)
                for elem in matches:
                    if elem in descendants and elem.tag.rpartition('}')[2].lower() not in {
                        'html',
                        'body',
                        'head',
                        'style',
                        'script',
                        'meta',
                        'link',
                    }:
                        # Last matching selector wins for before/after, same as prior attrib overwrite.
                        pb_before_map[elem] = before
                        page_breaks.add(elem)
            except SelectorError as err:
                self.log.warn(f'Ignoring page breaks specified with invalid CSS selector: {selector!r} ({as_unicode(err)})')
            except Exception as err:
                self.log.warn(f'Ignoring page breaks specified with invalid CSS selector: {selector!r} ({as_unicode(err)})')

        # Document order without tagging every node (attrib set on 10^5–10^6 nodes
        # dominated Split time on large Markdown novels).
        pb_order: dict[_Element, int] = {}
        if page_breaks:
            for i, elem in enumerate(root.iter('*')):
                if elem in page_breaks:
                    pb_order[elem] = i

        page_breaks = list(page_breaks)
        page_breaks.sort(key=lambda x: pb_order[x])
        page_break_ids: list[str] = []
        page_breaks_: list[PageBreak] = []
        for i, x in enumerate(page_breaks):
            x.set('id', x.get('id', f'calibre_pb_{i}'))
            id = x.get('id')
            try:
                xp = XPath(f'//*[@id="{id}"]')
            except Exception:
                try:
                    xp = XPath(f"//*[@id='{id}']")
                except Exception:
                    # The id has both a quote and an apostrophe or some other
                    # Just replace it since I doubt its going to work anywhere else
                    # either
                    id = f'calibre_pb_{i}'
                    x.set('id', id)
                    xp = XPath(f'//*[@id={id!r}]')
            page_breaks_.append((xp, pb_before_map.get(x, False)))
            page_break_ids.append(id)

        return page_breaks_, page_break_ids

    def fix_links(self) -> None:
        """
        Fix references to the split files in other content files.
        """
        seen = set()
        for item in self.oeb.manifest:
            if etree.iselement(item.data):
                self.current_item = item
                rewrite_links(item.data, self.rewrite_links)
                seen.add(item.data)
        if self.existing_nav is not None and self.existing_nav not in seen:
            seen.add(self.existing_nav)
            from calibre.ebooks.oeb.base import rel_href

            class FakeManifestItem:
                href = self.nav_href

                def abshref(self) -> str:
                    return self.href

                def relhref(self, href: str) -> str:
                    return rel_href(self.href, href)

            rewrite_links(self.existing_nav, self.rewrite_links)

    def rewrite_links(self, url: str) -> str:
        href, frag = urldefrag(url)
        try:
            href = self.current_item.abshref(href)
        except ValueError:
            # Unparsable URL
            return url
        try:
            href = urlnormalize(href)
        except ValueError:
            # href has non utf-8 quoting
            return url
        if href in self.map:
            anchor_map = self.map[href]
            nhref = anchor_map[frag or None]
            nhref = self.current_item.relhref(nhref)
            if frag:
                nhref = '#'.join((unquote(nhref), frag))

            return nhref
        return url


class FlowSplitter:
    "The actual splitting logic"

    def __init__(self, item: Manifest.Item, page_breaks: list[PageBreak], page_break_ids: list[str], max_flow_size: int, oeb: OEBBook, opts: Values) -> None:
        self.item = item
        self.oeb = oeb
        self.opts = opts
        self.log = oeb.log
        self.page_breaks = page_breaks
        self.page_break_ids = page_break_ids
        self.max_flow_size = max_flow_size
        self.base = item.href
        self.csp_counter = 0

        base, ext = os.path.splitext(self.base)
        self.base = base.replace('%', '%%') + '_split_%.3d' + ext

        root = self.item.data
        assert isinstance(root, etree._Element)  # only items whose data is an element are split
        self.trees: list[_ElementTree] = [root.getroottree()]
        self.splitting_on_page_breaks = True
        if self.page_breaks:
            self.split_on_page_breaks(self.trees[0])
        self.splitting_on_page_breaks = False

        if self.max_flow_size > 0:
            lt_found = False
            self.log(f'\tLooking for large trees in {item.href}...')
            trees = list(self.trees)
            self.tree_map: dict[_ElementTree, list[_ElementTree]] = {}
            for i, tree in enumerate(trees):
                size = len(tostring(tree.getroot()))
                if size > self.max_flow_size:
                    self.log(f'\tFound large tree #{i}')
                    lt_found = True
                    self.split_trees = []
                    self.split_to_size(tree)
                    self.tree_map[tree] = self.split_trees
            if not lt_found:
                self.log('\tNo large trees found')
            self.trees = []
            for x in trees:
                self.trees.extend(self.tree_map.get(x, [x]))

        self.was_split = len(self.trees) > 1
        if self.was_split:
            self.log(f'\tSplit into {len(self.trees)} parts')
        self.commit()

    def split_on_page_breaks(self, orig_tree: _ElementTree) -> None:
        ordered_ids: OrderedDict[str, PageBreak] = OrderedDict()
        all_page_break_ids = frozenset(self.page_break_ids)
        pb_by_id = dict(zip(self.page_break_ids, self.page_breaks, strict=True))
        for elem_id in orig_tree.xpath('//*/@id'):
            if elem_id in all_page_break_ids:
                ordered_ids[elem_id] = pb_by_id[elem_id]

        self.trees = [orig_tree]
        # Fast path: many page breaks on a flat <body> (typical Markdown novels).
        # Partition body siblings once instead of N× full-tree do_split deepcopies.
        # Supports mixed page-break-before / page-break-after (chapter_mark=pagebreak).
        if len(ordered_ids) > 1:
            specs = resolve_page_break_elements(ordered_ids, orig_tree.getroot())
            for elem, before in specs:
                self.log.debug(
                    f'\t\tQueued page-break at id={elem.get("id")} before={before}'
                )
            if specs:
                partitioned = partition_by_body_siblings(orig_tree, specs, self.log)
                if partitioned is not None:
                    self.log(f'\tSibling-partitioned page breaks into {len(partitioned)} parts')
                    self.trees = partitioned
                    ordered_ids.clear()
                else:
                    self.log.debug('\tSibling partition unavailable; falling back to sequential do_split')

        while ordered_ids:
            pb_id, (pattern, before) = next(iter(ordered_ids.items()))
            del ordered_ids[pb_id]
            for i in range(len(self.trees) - 1, -1, -1):
                tree = self.trees[i]
                elem = pattern(tree)
                if elem:
                    self.log.debug('\t\tSplitting on page-break at id={}'.format(elem[0].get('id')))
                    before_tree, after_tree = self.do_split(tree, elem[0], before)
                    self.trees[i : i + 1] = [before_tree, after_tree]
                    break

        trees, ids = [], set()
        for tree in self.trees:
            root = tree.getroot()
            if self.is_page_empty(root):
                discarded_ids = root.xpath('//*[@id]')
                for x in discarded_ids:
                    x = x.get('id')
                    if not x.startswith('calibre_'):
                        ids.add(x)
            else:
                if ids:
                    body = self.get_body(root)
                    if body is not None:
                        existing_ids = frozenset(body.xpath('//*/@id'))
                        for x in ids - existing_ids:
                            body.insert(0, body.makeelement(XHTML('div'), id=x, style='height:0pt'))
                ids = set()
                trees.append(tree)
        self.trees = trees

    def get_body(self, root: _Element) -> _Element | None:
        body = root.xpath('//h:body', namespaces=NAMESPACES)
        if not body:
            return None
        return body[0]

    def do_split(self, tree: _ElementTree, split_point: _Element, before: bool) -> tuple[_ElementTree, _ElementTree]:
        """
        Split ``tree`` into a *before* and *after* tree at ``split_point``.

        :param before: If True tree is split before split_point, otherwise after split_point
        :return: before_tree, after_tree
        """
        return do_split(split_point, self.log, before=before)

    def is_page_empty(self, root: _Element) -> bool:
        body = self.get_body(root)
        if body is None:
            return False
        txt = re.sub(r'\s+|\xa0', '', etree.tostring(body, method='text', encoding='unicode'))
        if len(txt):
            return False
        for img in root.xpath('//h:img', namespaces=NAMESPACES):
            if img.get('style', '') != 'display:none':
                return False
        if root.xpath('//*[local-name() = "svg"]'):
            return False
        return True

    def split_text(self, text: str, root: _Element, size: int) -> list[str]:
        self.log.debug(f'\t\t\tSplitting text of length: {len(text)}')
        rest = text.replace('\r', '')
        parts = rest.split('\n\n')
        self.log.debug(f'\t\t\t\tFound {len(parts)} parts')
        if max(map(len, parts)) > size:
            raise SplitError('Cannot split as file contains a <pre> tag with a very large paragraph', root)
        ans: list[str] = []
        buf = ''
        for part in parts:
            if len(buf) + len(part) < size:
                buf += '\n\n' + part
            else:
                ans.append(buf)
                buf = part
        return ans

    def split_to_size(self, tree: _ElementTree) -> None:
        self.log.debug('\t\tSplitting...')
        root = tree.getroot()
        # Split large <pre> tags if they contain only text
        for pre in XPath('//h:pre')(root):
            if len(tuple(pre.iterchildren(etree.Element))) > 0:
                continue
            if pre.text and len(pre.text) > self.max_flow_size * 0.5:
                self.log.debug('\t\tSplitting large <pre> tag')
                frags = self.split_text(pre.text, root, int(0.2 * self.max_flow_size))
                new_pres = []
                for frag in frags:
                    pre2 = copy.copy(pre)
                    pre2.text = frag
                    pre2.tail = ''
                    new_pres.append(pre2)
                new_pres[-1].tail = pre.tail
                p = pre.getparent()
                i = p.index(pre)
                p[i : i + 1] = new_pres

        # Prefer one-shot sibling partition at all headings (flat Markdown bodies).
        headings = XPath('//*[re:match(name(), "h[1-6]", "i")]')(root)
        if len(headings) >= 2:
            # Cut before every heading after the first (keeps preamble with first heading).
            partitioned = partition_by_body_siblings(tree, headings[1:], self.log, before=True)
            if partitioned is not None and len(partitioned) > 1:
                self.log.debug(f'\t\t\tSibling-partitioned into {len(partitioned)} heading parts')
                for t in partitioned:
                    r = t.getroot()
                    if self.is_page_empty(r):
                        continue
                    size = len(tostring(r))
                    if size <= self.max_flow_size:
                        self.split_trees.append(t)
                        self.log.debug(f'\t\t\tCommitted sub-tree #{len(self.split_trees)} ({size / 1024.0} KB)')
                    else:
                        self.log.debug(f'\t\t\tSplit tree still too large: {size / 1024.0} KB')
                        more = XPath('//*[re:match(name(), "h[1-6]", "i")]')(r)
                        if len(more) >= 2:
                            self.split_to_size(t)
                        else:
                            self._split_to_size_binary(t)
                return

        self._split_to_size_binary(tree)

    def _split_to_size_binary(self, tree: _ElementTree) -> None:
        root = tree.getroot()
        split_point, before = self.find_split_point(root)
        if split_point is None:
            raise SplitError(self.item.href, root)
        self.log.debug('\t\t\tSplit point:', split_point.tag, tree.getpath(split_point))

        trees = self.do_split(tree, split_point, before)
        sizes = [len(tostring(t.getroot())) for t in trees]
        if min(sizes) < 5 * 1024:
            self.log.debug('\t\t\tSplit tree too small')
            self.split_to_size(tree)
            return

        for t, size in zip(trees, sizes):
            r = t.getroot()
            if self.is_page_empty(r):
                continue
            elif size <= self.max_flow_size:
                self.split_trees.append(t)
                self.log.debug(f'\t\t\tCommitted sub-tree #{len(self.split_trees)} ({size / 1024.0} KB)')
            else:
                self.log.debug(f'\t\t\tSplit tree still too large: {size / 1024.0} KB')
                self.split_to_size(t)

    def find_split_point(self, root: _Element) -> tuple[_Element | None, bool]:
        '''
        Find the tag at which to split the tree rooted at `root`.
        Search order is:
            * Heading tags
            * <div> tags
            * <pre> tags
            * <hr> tags
            * <p> tags
            * <br> tags
            * <li> tags

        We try to split in the "middle" of the file (as defined by tag counts.
        '''

        def pick_elem(elems: list[_Element]) -> _Element | None:
            if elems:
                elems = [i for i in elems if i.get(SPLIT_POINT_ATTR, '0') != '1']
                if elems:
                    i = int(len(elems) // 2)
                    elems[i].set(SPLIT_POINT_ATTR, '1')
                    return elems[i]

        for path in (
            '//*[re:match(name(), "h[1-6]", "i")]',
            '/h:html/h:body/h:div',
            '//h:pre',
            '//h:hr',
            '//h:p',
            '//h:div',
            '//h:br',
            '//h:li',
        ):
            elems = root.xpath(path, namespaces=NAMESPACES)
            elem = pick_elem(elems)
            if elem is not None:
                try:
                    XPath(elem.getroottree().getpath(elem))
                except Exception:
                    continue
                return elem, True

        return None, True

    def commit(self) -> None:
        """
        Commit all changes caused by the split. Calculates an *anchor_map* for
        all anchors in the original tree. Internal links are re-directed. The
        original file is deleted and the split files are saved.
        """
        if not self.was_split:
            return
        self.anchor_map: collections.defaultdict[str | None, str] = collections.defaultdict(lambda: self.base % 0)
        self.files: list[str] = []

        for i, tree in enumerate(self.trees):
            root = tree.getroot()
            self.files.append(self.base % i)
            for elem in root.xpath('//*[@id or @name]'):
                for anchor in elem.get('id', ''), elem.get('name', ''):
                    if anchor != '' and anchor not in self.anchor_map:
                        self.anchor_map[anchor] = self.files[-1]
            for elem in root.xpath(f'//*[@{SPLIT_POINT_ATTR}]'):
                elem.attrib.pop(SPLIT_POINT_ATTR, '0')

        spine_pos = cast('int', self.item.spine_position)  # only items in the spine are split

        for current, tree in zip(*map(reversed, (self.files, self.trees))):
            for a in tree.getroot().xpath('//h:a[@href]', namespaces=NAMESPACES):
                href = a.get('href').strip()
                if href.startswith('#'):
                    anchor = href[1:]
                    file = self.anchor_map[anchor]
                    file = self.item.relhref(file)
                    if file != current:
                        a.set('href', file + href)

            new_id = self.oeb.manifest.generate(id=self.item.id)[0]
            new_item = self.oeb.manifest.add(new_id, current, self.item.media_type, data=tree.getroot())
            self.oeb.spine.insert(spine_pos, new_item, self.item.linear)

        if self.oeb.guide:
            for ref in self.oeb.guide.values():
                href, frag = urldefrag(ref.href)
                if href == self.item.href:
                    nhref = self.anchor_map[frag or None]
                    if frag:
                        nhref = f'{nhref}#{frag}'
                    ref.href = nhref

        def fix_toc_entry(toc: TOC) -> None:

            if toc.href:
                href, frag = urldefrag(toc.href)
                if href == self.item.href:
                    nhref = self.anchor_map[frag or None]
                    if frag:
                        nhref = f'{nhref}#{frag}'
                    toc.href = nhref
            for x in toc:
                fix_toc_entry(x)

        if self.oeb.toc:
            fix_toc_entry(self.oeb.toc)

        if self.oeb.pages:
            for page in self.oeb.pages:
                href, frag = urldefrag(page.href)
                if href == self.item.href:
                    nhref = self.anchor_map[frag or None]
                    if frag:
                        nhref = f'{nhref}#{frag}'
                    page.href = nhref

        self.oeb.manifest.remove(self.item)
