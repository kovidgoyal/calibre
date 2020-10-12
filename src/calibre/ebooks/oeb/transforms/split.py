
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Splitting of the XHTML flows. Splitting can happen on page boundaries or can be
forced at "likely" locations to conform to size limitations. This transform
assumes a prior call to the flatcss transform.
'''

import os, functools, collections, re, copy
from collections import OrderedDict

from lxml.etree import XPath as _XPath
from lxml import etree

from calibre import as_unicode, force_unicode
from calibre.ebooks.epub import rules
from calibre.ebooks.oeb.base import (OEB_STYLES, XPNSMAP as NAMESPACES,
        urldefrag, rewrite_links, XHTML, urlnormalize)
from calibre.ebooks.oeb.polish.split import do_split
from polyglot.builtins import iteritems, range, map, unicode_type
from polyglot.urllib import unquote
from css_selectors import Select, SelectorError

XPath = functools.partial(_XPath, namespaces=NAMESPACES)

SPLIT_POINT_ATTR = 'csp'


def tostring(root):
    return etree.tostring(root, encoding='utf-8')


class SplitError(ValueError):

    def __init__(self, path, root):
        size = len(tostring(root))/1024.
        ValueError.__init__(self,
            _('Could not find reasonable point at which to split: '
                '%(path)s Sub-tree size: %(size)d KB')%dict(
                            path=path, size=size))


class Split(object):

    def __init__(self, split_on_page_breaks=True, page_breaks_xpath=None,
            max_flow_size=0, remove_css_pagebreaks=True):
        self.split_on_page_breaks = split_on_page_breaks
        self.page_breaks_xpath = page_breaks_xpath
        self.max_flow_size = max_flow_size
        self.page_break_selectors = None
        self.remove_css_pagebreaks = remove_css_pagebreaks
        if self.page_breaks_xpath is not None:
            self.page_break_selectors = [(XPath(self.page_breaks_xpath), False)]

    def __call__(self, oeb, opts):
        self.oeb = oeb
        self.log = oeb.log
        self.log('Splitting markup on page breaks and flow limits, if any...')
        self.opts = opts
        self.map = {}
        for item in list(self.oeb.manifest.items):
            if item.spine_position is not None and etree.iselement(item.data):
                self.split_item(item)

        self.fix_links()

    def split_item(self, item):
        page_breaks, page_break_ids = [], []
        if self.split_on_page_breaks:
            page_breaks, page_break_ids = self.find_page_breaks(item)

        splitter = FlowSplitter(item, page_breaks, page_break_ids,
                self.max_flow_size, self.oeb, self.opts)
        if splitter.was_split:
            am = splitter.anchor_map
            self.map[item.href] = collections.defaultdict(
                    am.default_factory, am)

    def find_page_breaks(self, item):
        if self.page_break_selectors is None:
            self.page_break_selectors = set()
            stylesheets = [x.data for x in self.oeb.manifest if x.media_type in
                    OEB_STYLES]
            for rule in rules(stylesheets):
                before = force_unicode(getattr(rule.style.getPropertyCSSValue(
                    'page-break-before'), 'cssText', '').strip().lower())
                after  = force_unicode(getattr(rule.style.getPropertyCSSValue(
                    'page-break-after'), 'cssText', '').strip().lower())
                try:
                    if before and before not in {'avoid', 'auto', 'inherit'}:
                        self.page_break_selectors.add((rule.selectorText, True))
                        if self.remove_css_pagebreaks:
                            rule.style.removeProperty('page-break-before')
                except:
                    pass
                try:
                    if after and after not in {'avoid', 'auto', 'inherit'}:
                        self.page_break_selectors.add((rule.selectorText, False))
                        if self.remove_css_pagebreaks:
                            rule.style.removeProperty('page-break-after')
                except:
                    pass
        page_breaks = set()
        select = Select(item.data)
        if not self.page_break_selectors:
            return [], []
        body = item.data.xpath('//h:body', namespaces=NAMESPACES)
        if not body:
            return [], []
        descendants = frozenset(body[0].iterdescendants('*'))

        for selector, before in self.page_break_selectors:
            try:
                for elem in select(selector):
                    if elem in descendants and elem.tag.rpartition('}')[2].lower() not in {'html', 'body', 'head', 'style', 'script', 'meta', 'link'}:
                        elem.set('pb_before', '1' if before else '0')
                        page_breaks.add(elem)
            except SelectorError as err:
                self.log.warn('Ignoring page breaks specified with invalid CSS selector: %r (%s)' % (selector, as_unicode(err)))

        for i, elem in enumerate(item.data.iter('*')):
            try:
                elem.set('pb_order', unicode_type(i))
            except TypeError:  # Cant set attributes on comment nodes etc.
                continue

        page_breaks = list(page_breaks)
        page_breaks.sort(key=lambda x:int(x.get('pb_order')))
        page_break_ids, page_breaks_ = [], []
        for i, x in enumerate(page_breaks):
            x.set('id', x.get('id', 'calibre_pb_%d'%i))
            id = x.get('id')
            try:
                xp = XPath('//*[@id="%s"]'%id)
            except:
                try:
                    xp = XPath("//*[@id='%s']"%id)
                except:
                    # The id has both a quote and an apostrophe or some other
                    # Just replace it since I doubt its going to work anywhere else
                    # either
                    id = 'calibre_pb_%d'%i
                    x.set('id', id)
                    xp = XPath('//*[@id=%r]'%id)
            page_breaks_.append((xp, x.get('pb_before', '0') == '1'))
            page_break_ids.append(id)

        for elem in item.data.iter(etree.Element):
            elem.attrib.pop('pb_order', False)
            elem.attrib.pop('pb_before', False)

        return page_breaks_, page_break_ids

    def fix_links(self):
        '''
        Fix references to the split files in other content files.
        '''
        for item in self.oeb.manifest:
            if etree.iselement(item.data):
                self.current_item = item
                rewrite_links(item.data, self.rewrite_links)

    def rewrite_links(self, url):
        href, frag = urldefrag(url)
        try:
            href = self.current_item.abshref(href)
        except ValueError:
            # Unparseable URL
            return url
        try:
            href = urlnormalize(href)
        except ValueError:
            # href has non utf-8 quoting
            return url
        if href in self.map:
            anchor_map = self.map[href]
            nhref = anchor_map[frag if frag else None]
            nhref = self.current_item.relhref(nhref)
            if frag:
                nhref = '#'.join((unquote(nhref), frag))

            return nhref
        return url


class FlowSplitter(object):
    'The actual splitting logic'

    def __init__(self, item, page_breaks, page_break_ids, max_flow_size, oeb,
            opts):
        self.item           = item
        self.oeb            = oeb
        self.opts           = opts
        self.log            = oeb.log
        self.page_breaks    = page_breaks
        self.page_break_ids = page_break_ids
        self.max_flow_size  = max_flow_size
        self.base           = item.href
        self.csp_counter    = 0

        base, ext = os.path.splitext(self.base)
        self.base = base.replace('%', '%%')+'_split_%.3d'+ext

        self.trees = [self.item.data.getroottree()]
        self.splitting_on_page_breaks = True
        if self.page_breaks:
            self.split_on_page_breaks(self.trees[0])
        self.splitting_on_page_breaks = False

        if self.max_flow_size > 0:
            lt_found = False
            self.log('\tLooking for large trees in %s...'%item.href)
            trees = list(self.trees)
            self.tree_map = {}
            for i, tree in enumerate(trees):
                size = len(tostring(tree.getroot()))
                if size > self.max_flow_size:
                    self.log('\tFound large tree #%d'%i)
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
            self.log('\tSplit into %d parts'%len(self.trees))
        self.commit()

    def split_on_page_breaks(self, orig_tree):
        ordered_ids = OrderedDict()
        all_page_break_ids = frozenset(self.page_break_ids)
        for elem_id in orig_tree.xpath('//*/@id'):
            if elem_id in all_page_break_ids:
                ordered_ids[elem_id] = self.page_breaks[
                    self.page_break_ids.index(elem_id)]

        self.trees = [orig_tree]
        while ordered_ids:
            pb_id, (pattern, before) = next(iteritems(ordered_ids))
            del ordered_ids[pb_id]
            for i in range(len(self.trees)-1, -1, -1):
                tree = self.trees[i]
                elem = pattern(tree)
                if elem:
                    self.log.debug('\t\tSplitting on page-break at id=%s'%
                                elem[0].get('id'))
                    before_tree, after_tree = self.do_split(tree, elem[0], before)
                    self.trees[i:i+1] = [before_tree, after_tree]
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

    def get_body(self, root):
        body = root.xpath('//h:body', namespaces=NAMESPACES)
        if not body:
            return None
        return body[0]

    def do_split(self, tree, split_point, before):
        '''
        Split ``tree`` into a *before* and *after* tree at ``split_point``.

        :param before: If True tree is split before split_point, otherwise after split_point
        :return: before_tree, after_tree
        '''
        return do_split(split_point, self.log, before=before)

    def is_page_empty(self, root):
        body = self.get_body(root)
        if body is None:
            return False
        txt = re.sub(r'\s+|\xa0', '',
                etree.tostring(body, method='text', encoding='unicode'))
        if len(txt):
            return False
        for img in root.xpath('//h:img', namespaces=NAMESPACES):
            if img.get('style', '') != 'display:none':
                return False
        if root.xpath('//*[local-name() = "svg"]'):
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
        # Split large <pre> tags if they contain only text
        for pre in XPath('//h:pre')(root):
            if len(tuple(pre.iterchildren(etree.Element))) > 0:
                continue
            if pre.text and len(pre.text) > self.max_flow_size*0.5:
                self.log.debug('\t\tSplitting large <pre> tag')
                frags = self.split_text(pre.text, root, int(0.2*self.max_flow_size))
                new_pres = []
                for frag in frags:
                    pre2 = copy.copy(pre)
                    pre2.text = frag
                    pre2.tail = ''
                    new_pres.append(pre2)
                new_pres[-1].tail = pre.tail
                p = pre.getparent()
                i = p.index(pre)
                p[i:i+1] = new_pres

        split_point, before = self.find_split_point(root)
        if split_point is None:
            raise SplitError(self.item.href, root)
        self.log.debug('\t\t\tSplit point:', split_point.tag, tree.getpath(split_point))

        trees = self.do_split(tree, split_point, before)
        sizes = [len(tostring(t.getroot())) for t in trees]
        if min(sizes) < 5*1024:
            self.log.debug('\t\t\tSplit tree too small')
            self.split_to_size(tree)
            return

        for t, size in zip(trees, sizes):
            r = t.getroot()
            if self.is_page_empty(r):
                continue
            elif size <= self.max_flow_size:
                self.split_trees.append(t)
                self.log.debug(
                    '\t\t\tCommitted sub-tree #%d (%d KB)'%(
                               len(self.split_trees), size/1024.))
            else:
                self.log.debug(
                        '\t\t\tSplit tree still too large: %d KB' % (size/1024.))
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
                elems = [i for i in elems if i.get(SPLIT_POINT_ATTR, '0') !=
                        '1']
                if elems:
                    i = int(len(elems)//2)
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
                except:
                    continue
                return elem, True

        return None, True

    def commit(self):
        '''
        Commit all changes caused by the split. Calculates an *anchor_map* for
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
            for elem in root.xpath('//*[@id or @name]'):
                for anchor in elem.get('id', ''), elem.get('name', ''):
                    if anchor != '' and anchor not in self.anchor_map:
                        self.anchor_map[anchor] = self.files[-1]
            for elem in root.xpath('//*[@%s]'%SPLIT_POINT_ATTR):
                elem.attrib.pop(SPLIT_POINT_ATTR, '0')

        spine_pos = self.item.spine_position

        for current, tree in zip(*map(reversed, (self.files, self.trees))):
            for a in tree.getroot().xpath('//h:a[@href]', namespaces=NAMESPACES):
                href = a.get('href').strip()
                if href.startswith('#'):
                    anchor = href[1:]
                    file = self.anchor_map[anchor]
                    file = self.item.relhref(file)
                    if file != current:
                        a.set('href', file+href)

            new_id = self.oeb.manifest.generate(id=self.item.id)[0]
            new_item = self.oeb.manifest.add(new_id, current,
                    self.item.media_type, data=tree.getroot())
            self.oeb.spine.insert(spine_pos, new_item, self.item.linear)

        if self.oeb.guide:
            for ref in self.oeb.guide.values():
                href, frag = urldefrag(ref.href)
                if href == self.item.href:
                    nhref = self.anchor_map[frag if frag else None]
                    if frag:
                        nhref = '#'.join((nhref, frag))
                    ref.href = nhref

        def fix_toc_entry(toc):
            if toc.href:
                href, frag = urldefrag(toc.href)
                if href == self.item.href:
                    nhref = self.anchor_map[frag if frag else None]
                    if frag:
                        nhref = '#'.join((nhref, frag))
                    toc.href = nhref
            for x in toc:
                fix_toc_entry(x)

        if self.oeb.toc:
            fix_toc_entry(self.oeb.toc)

        if self.oeb.pages:
            for page in self.oeb.pages:
                href, frag = urldefrag(page.href)
                if href == self.item.href:
                    nhref = self.anchor_map[frag if frag else None]
                    if frag:
                        nhref = '#'.join((nhref, frag))
                    page.href = nhref

        self.oeb.manifest.remove(self.item)
