from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Splitting of the XHTML flows. Splitting can happen on page boundaries or can be
forces at "likely" locations to conform to size limitations. This transform
assumes a prior call to the flatcss transform.
'''

import os, math, functools, collections, re, copy

from lxml.etree import XPath as _XPath
from lxml import etree, html
from lxml.cssselect import CSSSelector

from calibre.ebooks.oeb.base import OEB_STYLES, XPNSMAP, urldefrag, \
                rewrite_links
from calibre.ebooks.epub import tostring, rules

NAMESPACES = dict(XPNSMAP)
NAMESPACES['re'] = 'http://exslt.org/regular-expressions'

XPath = functools.partial(_XPath, namespaces=NAMESPACES)

SPLIT_ATTR       = 'cs'
SPLIT_POINT_ATTR = 'csp'

class SplitError(ValueError):

    def __init__(self, path, root):
        size = len(tostring(root))/1024.
        ValueError.__init__(self,
            _('Could not find reasonable point at which to split: '
                '%s Sub-tree size: %d KB')%
                            (path, size))

class Split(object):

    def __init__(self, split_on_page_breaks=True, page_breaks_xpath=None,
            max_flow_size=0):
        self.split_on_page_breaks = split_on_page_breaks
        self.page_breaks_xpath = page_breaks_xpath
        self.max_flow_size = max_flow_size
        if self.page_breaks_xpath is not None:
            self.page_breaks_xpath = XPath(self.page_breaks_xpath)

    def __call__(self, oeb, context):
        self.oeb = oeb
        self.log = oeb.log
        self.map = {}
        self.page_break_selectors = None
        for item in self.oeb.manifest.items:
            if etree.iselement(item.data):
                self.split_item(item)

        self.fix_links()

    def split_item(self, item):
        if self.split_on_page_breaks:
            if self.page_breaks_xpath is None:
                page_breaks, page_break_ids = self.find_page_breaks(item)
            else:
                page_breaks, page_break_ids = self.page_breaks_xpath(item.data)

        splitter = FlowSplitter(item, page_breaks, page_break_ids,
                self.max_flow_size, self.oeb)
        if splitter.was_split:
            self.map[item.href] = dict(splitter.anchor_map)

    def find_page_breaks(self, item):
        if self.page_break_selectors is None:
            self.page_break_selectors = set([])
            stylesheets = [x.data for x in self.oeb.manifest if x.media_type in
                    OEB_STYLES]
        page_break_selectors = set([])
        for rule in rules(stylesheets):
            before = getattr(rule.style.getPropertyCSSValue(
                'page-break-before'), 'cssText', '').strip().lower()
            after  = getattr(rule.style.getPropertyCSSValue(
                'page-break-after'), 'cssText', '').strip().lower()
            try:
                if before and before != 'avoid':
                    page_break_selectors.add((CSSSelector(rule.selectorText),
                        True))
            except:
                pass
            try:
                if after and after != 'avoid':
                    page_break_selectors.add((CSSSelector(rule.selectorText),
                        False))
            except:
                pass

        page_breaks = set([])
        for selector, before in page_break_selectors:
            for elem in selector(item.data):
                elem.pb_before = before
                page_breaks.add(elem)

        for i, elem in enumerate(item.data.iter()):
            elem.pb_order = i

        page_breaks = list(page_breaks)
        page_breaks.sort(cmp=lambda x,y : cmp(x.pb_order, y.pb_order))
        page_break_ids, page_breaks_ = [], []
        for i, x in enumerate(page_breaks):
            x.set('id', x.get('id', 'calibre_pb_%d'%i))
            id = x.get('id')
            page_breaks_.append((XPath('//*[@id="%s"]'%id), x.pb_before))
            page_break_ids.append(id)

        return page_breaks_, page_break_ids

    def fix_links(self, opf):
        '''
        Fix references to the split files in other content files.
        '''
        for item in self.oeb.manifest:
            if etree.iselement(item.data):
                self.current_item = item
                rewrite_links(item.data, self.rewrite_links)

    def rewrite_links(self, url):
        href, frag = urldefrag(url)
        href = self.current_item.abshref(href)
        if href in self.map:
            anchor_map = self.map[href]
            nhref = anchor_map[frag if frag else None]
            if frag:
                nhref = '#'.joinn(href, frag)
            return nhref
        return url



class FlowSplitter(object):

    def __init__(self, item, page_breaks, page_break_ids, max_flow_size, oeb):
        self.item           = item
        self.oeb            = oeb
        self.log            = oeb.log
        self.page_breaks    = page_breaks
        self.page_break_ids = page_break_ids
        self.max_flow_size  = max_flow_size
        self.base           = item.abshref(item.href)

        base, ext = os.path.splitext(self.base)
        self.base = base.replace('%', '%%')+'_split_%d'+ext

        self.trees = [self.item.data]
        self.splitting_on_page_breaks = True
        if self.page_breaks:
            self.split_on_page_breaks(self.item.data)
        self.splitting_on_page_breaks = False

        if self.max_flow_size > 0:
            lt_found = False
            self.log('\tLooking for large trees...')
            trees = list(self.trees)
            for i, tree in enumerate(list(self.trees)):
                self.trees = []
                size = len(tostring(tree.getroot()))
                if size > self.opts.profile.flow_size:
                    lt_found = True
                    self.split_to_size(tree)
                    trees[i:i+1] = list(self.trees)
            if not lt_found:
                self.log_info('\tNo large trees found')
            self.trees = trees

        self.was_split = len(self.trees) > 1
        self.commit()

    def split_on_page_breaks(self, orig_tree):
        ordered_ids = []
        for elem in orig_tree.xpath('//*[@id]'):
            id = elem.get('id')
            if id in self.page_break_ids:
                ordered_ids.append(self.page_breaks[self.page_break_ids.index(id)])

        self.trees = []
        tree = orig_tree
        for pattern, before in ordered_ids:
            self.log.debug('\t\tSplitting on page-break')
            elem = pattern(tree)
            if elem:
                before, after = self.do_split(tree, elem[0], before)
                self.trees.append(before)
                tree = after
        self.trees.append(tree)
        self.trees = [t for t in self.trees if not self.is_page_empty(t.getroot())]

    def do_split(self, tree, split_point, before):
        '''
        Split ``tree`` into a *before* and *after* tree at ``split_point``,
        preserving tag structure, but not duplicating any text.
        All tags that have had their text and tail
        removed have the attribute ``calibre_split`` set to 1.

        :param before: If True tree is split before split_point, otherwise after split_point
        :return: before_tree, after_tree
        '''
        path         = tree.getpath(split_point)
        tree, tree2  = copy.deepcopy(tree), copy.deepcopy(tree)
        root         = tree.getroot()
        root2        = tree2.getroot()
        body, body2  = root.body, root2.body
        split_point  = root.xpath(path)[0]
        split_point2 = root2.xpath(path)[0]

        def nix_element(elem, top=True):
            if True:
                parent = elem.getparent()
                index = parent.index(elem)
                if top:
                    parent.remove(elem)
                else:
                    index = parent.index(elem)
                    parent[index:index+1] = list(elem.iterchildren())
            else:
                elem.text = u''
                elem.tail = u''
                elem.set(SPLIT_ATTR, '1')
                if elem.tag.lower() in ['ul', 'ol', 'dl', 'table', 'hr', 'img']:
                    elem.set('style', 'display:none')

        def fix_split_point(sp):
            if not self.splitting_on_page_breaks:
                sp.set('style', sp.get('style', '')+'page-break-before:avoid;page-break-after:avoid')

        # Tree 1
        hit_split_point = False
        for elem in list(body.iterdescendants(etree.Element)):
            if elem.get(SPLIT_ATTR, '0') == '1':
                continue
            if elem is split_point:
                hit_split_point = True
                if before:
                    nix_element(elem)
                fix_split_point(elem)
                continue
            if hit_split_point:
                nix_element(elem)


        # Tree 2
        hit_split_point = False
        for elem in list(body2.iterdescendants(etree.Element)):
            if elem.get(SPLIT_ATTR, '0') == '1':
                continue
            if elem is split_point2:
                hit_split_point = True
                if not before:
                    nix_element(elem, top=False)
                fix_split_point(elem)
                continue
            if not hit_split_point:
                nix_element(elem, top=False)

        return tree, tree2

    def is_page_empty(self, root):
        body = root.find('body')
        if body is None:
            return False
        txt = re.sub(r'\s+', '', html.tostring(body, method='text', encoding=unicode))
        if len(txt) > 4:
            return False
        for img in root.xpath('//img'):
            if img.get('style', '') != 'display:none':
                return False
        return True

    def split_text(self, text, root, size):
        self.log.debug('\t\t\tSplitting text of length: %d'%len(text))
        rest = text.replace('\r', '')
        parts = re.split('\n\n', rest)
        self.log.debug('\t\t\t\tFound %d parts'%len(parts))
        if max(map(len, parts)) > size:
            raise SplitError('Cannot split as file contains a <pre> tag '
                'with a very large paragraph', root)
        ans = []
        buf = ''
        for part in parts:
            if len(buf) + len(part) < size:
                buf += '\n\n'+part
            else:
                ans.append(buf)
                buf = part
        return ans


    def split_to_size(self, tree):
        self.log.debug('\t\tSplitting...')
        root = tree.getroot()
        # Split large <pre> tags
        for pre in list(root.xpath('//pre')):
            text = u''.join(pre.xpath('descendant::text()'))
            pre.text = text
            for child in list(pre.iterchildren()):
                pre.remove(child)
            if len(pre.text) > self.max_flow_size*0.5:
                frags = self.split_text(pre.text, root, int(0.2*self.max_flow_size))
                new_pres = []
                for frag in frags:
                    pre2 = copy.copy(pre)
                    pre2.text = frag
                    pre2.tail = u''
                    new_pres.append(pre2)
                new_pres[-1].tail = pre.tail
                p = pre.getparent()
                i = p.index(pre)
                p[i:i+1] = new_pres

        split_point, before = self.find_split_point(root)
        if split_point is None:
            raise SplitError(self.item.href, root)

        for t in self.do_split(tree, split_point, before):
            r = t.getroot()
            if self.is_page_empty(r):
                continue
            size = len(tostring(r))
            if size <= self.max_flow_size:
                self.trees.append(t)
                #print tostring(t.getroot(), pretty_print=True)
                self.log.debug('\t\t\tCommitted sub-tree #%d (%d KB)',
                               len(self.trees), size/1024.)
                self.split_size += size
            else:
                self.split_to_size(t)

    def find_split_point(self, root):
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
        def pick_elem(elems):
            if elems:
                elems = [i for i in elems if i.get(SPLIT_POINT_ATTR, '0') != '1'\
                          and i.get(SPLIT_ATTR, '0') != '1']
                if elems:
                    i = int(math.floor(len(elems)/2.))
                    elems[i].set(SPLIT_POINT_ATTR, '1')
                    return elems[i]

        for path in (
                     '//*[re:match(name(), "h[1-6]", "i")]',
                     '/html/body/div',
                     '//pre',
                     '//hr',
                     '//p',
                     '//div',
                     '//br',
                     '//li',
                     ):
            elems = root.xpath(path, namespaces=NAMESPACES)
            elem = pick_elem(elems)
            if elem is not None:
                try:
                    XPath(elem.getroottree().getpath(elem))
                except:
                    continue
                return elem, True

        return None, True

    def commit(self):
        '''
        Commit all changes caused by the split. This removes the previously
        introduced ``calibre_split`` attribute and calculates an *anchor_map* for
        all anchors in the original tree. Internal links are re-directed. The
        original file is deleted and the split files are saved.
        '''
        if not self.was_split:
            return
        self.anchor_map = collections.defaultdict(lambda :self.base%0)
        self.files = []

        for i, tree in enumerate(self.trees):
            root = tree.getroot()
            self.files.append(self.base%i)
            for elem in root.xpath('//*[@id]'):
                if elem.get(SPLIT_ATTR, '0') == '0':
                    self.anchor_map[elem.get('id')] = self.files[-1]
            for elem in root.xpath('//*[@%s or @%s]'%(SPLIT_ATTR, SPLIT_POINT_ATTR)):
                elem.attrib.pop(SPLIT_ATTR, None)
                elem.attrib.pop(SPLIT_POINT_ATTR, '0')

        spine_pos = self.item.spine_pos
        for current, tree in zip(map(reversed, (self.files, self.trees))):
            for a in tree.getroot().xpath('//h:a[@href]', namespaces=NAMESPACES):
                href = a.get('href').strip()
                if href.startswith('#'):
                    anchor = href[1:]
                    file = self.anchor_map[anchor]
                    if file != current:
                        a.set('href', file+href)

            new_id = self.oeb.manifest.generate(id=self.item.id)[0]
            new_item = self.oeb.manifest.add(new_id, current,
                    self.item.media_type, data=tree.getroot())
            self.oeb.spine.insert(spine_pos, new_item, self.item.linear)

        if self.oeb.guide:
            for ref in self.oeb.guide:
                href, frag = urldefrag(ref.href)
                if href == self.item.href:
                    nhref = self.anchor_map[frag if frag else None]
                    if frag:
                        nhref = '#'.join(nhref, frag)
                    ref.href = nhref

        def fix_toc_entry(toc):
            if toc.href:
                href, frag = urldefrag(toc.href)
                if href == self.item.href:
                    nhref = self.anchor_map[frag if frag else None]
                    if frag:
                        nhref = '#'.join(nhref, frag)
                    toc.href = nhref
            for x in toc:
                fix_toc_entry(x)


        if self.oeb.toc:
            fix_toc_entry(self.oeb.toc)

        self.oeb.manifest.remove(self.item)



