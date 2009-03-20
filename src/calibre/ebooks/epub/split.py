from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Split the flows in an epub file to conform to size limitations.
'''

import os, math, logging, functools, collections, re, copy, sys

from lxml.etree import XPath as _XPath
from lxml import etree, html
from lxml.cssselect import CSSSelector

from calibre.ebooks.metadata.opf2 import OPF
from calibre.ebooks.epub import tostring, rules
from calibre import CurrentDir

XPath = functools.partial(_XPath, namespaces={'re':'http://exslt.org/regular-expressions'})
content = functools.partial(os.path.join, 'content')

SPLIT_ATTR       = 'cs'
SPLIT_POINT_ATTR = 'csp'

class SplitError(ValueError):
    
    def __init__(self, path, root):
        size = len(tostring(root))/1024.
        ValueError.__init__(self, _('Could not find reasonable point at which to split: %s Sub-tree size: %d KB')% 
                            (os.path.basename(path), size))

    

class Splitter(object):
    
    def __init__(self, path, opts, stylesheet_map, opf):
        self.setup_cli_handler(opts.verbose)
        self.path = path
        self.always_remove = not opts.preserve_tag_structure or \
                    os.stat(content(path)).st_size > 5*opts.profile.flow_size
        self.base = (os.path.splitext(path)[0].replace('%', '%%') + '_split_%d.html')
        self.opts = opts
        self.orig_size = os.stat(content(path)).st_size
        self.log_info('\tSplitting %s (%d KB)', path, self.orig_size/1024.)
        root = html.fromstring(open(content(path)).read())
            
        self.page_breaks, self.trees = [], []
        self.split_size = 0
        
        # Split on page breaks
        self.splitting_on_page_breaks = True
        if not opts.dont_split_on_page_breaks:
            self.log_info('\tSplitting on page breaks...')
            if self.path in stylesheet_map:
                self.find_page_breaks(stylesheet_map[self.path], root)
            self.split_on_page_breaks(root.getroottree())
            trees = list(self.trees)
        else:
            self.trees = [root.getroottree()]
            trees = list(self.trees)
        
        # Split any remaining over-sized trees
        self.splitting_on_page_breaks = False
        if self.opts.profile.flow_size < sys.maxint:
            lt_found = False
            self.log_info('\tLooking for large trees...')
            for i, tree in enumerate(list(trees)):
                self.trees = []
                size = len(tostring(tree.getroot())) 
                if size > self.opts.profile.flow_size:
                    lt_found = True
                    try:
                        self.split_to_size(tree)
                    except (SplitError, RuntimeError): # Splitting fails
                        if not self.always_remove:
                            self.always_remove = True
                            self.split_to_size(tree)
                        else:
                            raise
                    trees[i:i+1] = list(self.trees)
            if not lt_found:
                self.log_info('\tNo large trees found')
        
        self.trees = trees
        self.was_split = len(self.trees) > 1
        if self.was_split:
            self.commit()
            self.log_info('\t\tSplit into %d parts.', len(self.trees))
            if self.opts.verbose:
                for f in self.files:
                    self.log_info('\t\t\t%s - %d KB', f, os.stat(content(f)).st_size/1024.)
            self.fix_opf(opf)
            
        self.trees = None
        
    
    def split_text(self, text, root, size):
        self.log_debug('\t\t\tSplitting text of length: %d'%len(text))
        rest = text.replace('\r', '')
        parts = re.split('\n\n', rest)
        self.log_debug('\t\t\t\tFound %d parts'%len(parts))
        if max(map(len, parts)) > size:
            raise SplitError('Cannot split as file contains a <pre> tag with a very large paragraph', root) 
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
        self.log_debug('\t\tSplitting...')
        root = tree.getroot()
        # Split large <pre> tags
        for pre in list(root.xpath('//pre')):
            text = u''.join(pre.xpath('descendant::text()'))
            pre.text = text
            for child in list(pre.iterchildren()):
                pre.remove(child)
            if len(pre.text) > self.opts.profile.flow_size*0.5:
                frags = self.split_text(pre.text, root, int(0.2*self.opts.profile.flow_size))
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
        if split_point is None or self.split_size > 6*self.orig_size:
            if not self.always_remove:
                self.log_warn(_('\t\tToo much markup. Re-splitting without '
                                'structure preservation. This may cause '
                                'incorrect rendering.'))
            raise SplitError(self.path, root)
        
        for t in self.do_split(tree, split_point, before):
            r = t.getroot()
            if self.is_page_empty(r):
                continue
            size = len(tostring(r))
            if size <= self.opts.profile.flow_size:
                self.trees.append(t)
                #print tostring(t.getroot(), pretty_print=True)
                self.log_debug('\t\t\tCommitted sub-tree #%d (%d KB)', 
                               len(self.trees), size/1024.)
                self.split_size += size
            else:
                self.split_to_size(t)
    
    def is_page_empty(self, root):
        body = root.find('body')
        if body is None:
            return False
        txt = re.sub(r'\s+', '', html.tostring(body, method='text', encoding=unicode))
        if len(txt) > 4:
            #if len(txt) < 100:
            #    print 1111111, html.tostring(body, method='html', encoding=unicode)
            return False
        for img in root.xpath('//img'):
            if img.get('style', '') != 'display:none':
                return False
        return True
                
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
            if self.always_remove:
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
                
    
    def split_on_page_breaks(self, orig_tree):
        ordered_ids = []
        for elem in orig_tree.xpath('//*[@id]'):
            id = elem.get('id')
            if id in self.page_break_ids:
                ordered_ids.append(self.page_breaks[self.page_break_ids.index(id)])
                
        self.trees = []
        tree = orig_tree
        for pattern, before in ordered_ids:
            self.log_info('\t\tSplitting on page-break')
            elem = pattern(tree)
            if elem:
                before, after = self.do_split(tree, elem[0], before)
                self.trees.append(before)
                tree = after
        self.trees.append(tree)
        self.trees = [t for t in self.trees if not self.is_page_empty(t.getroot())]
                
            
                
    def find_page_breaks(self, stylesheets, root):
        '''
        Find all elements that have either page-break-before or page-break-after set.
        Populates `self.page_breaks` with id based XPath selectors (for elements that don't 
        have ids, an id is created).
        '''
        page_break_selectors = set([])
        for rule in rules(stylesheets):
            before = getattr(rule.style.getPropertyCSSValue('page-break-before'), 'cssText', '').strip().lower()
            after  = getattr(rule.style.getPropertyCSSValue('page-break-after'), 'cssText', '').strip().lower()
            try:
                if before and before != 'avoid':
                    page_break_selectors.add((CSSSelector(rule.selectorText), True))
            except:
                pass
            try:
                if after and after != 'avoid':
                    page_break_selectors.add((CSSSelector(rule.selectorText), False))
            except:
                pass
            
        page_breaks = set([])
        for selector, before in page_break_selectors:
            for elem in selector(root):
                elem.pb_before = before
                page_breaks.add(elem)
                
        for i, elem in enumerate(root.iter()):
            elem.pb_order = i
            
        page_breaks = list(page_breaks)
        page_breaks.sort(cmp=lambda x,y : cmp(x.pb_order, y.pb_order))
        self.page_break_ids = []
        for i, x in enumerate(page_breaks):
            x.set('id', x.get('id', 'calibre_pb_%d'%i))
            id = x.get('id')
            self.page_breaks.append((XPath('//*[@id="%s"]'%id), x.pb_before))
            self.page_break_ids.append(id)                        
        
        
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
            elems = root.xpath(path, 
                    namespaces={'re':'http://exslt.org/regular-expressions'})
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
                
        for current, tree in zip(self.files, self.trees):
            for a in tree.getroot().xpath('//a[@href]'):
                href = a.get('href').strip()
                if href.startswith('#'):
                    anchor = href[1:]
                    file = self.anchor_map[anchor]
                    if file != current:
                        a.set('href', file+href)            
            open(content(current), 'wb').\
                write(tostring(tree.getroot(), pretty_print=self.opts.pretty_print))
            
        os.remove(content(self.path))


    def fix_opf(self, opf):
        '''
        Fix references to the split file in the OPF.
        '''
        items = [item for item in opf.itermanifest() if item.get('href') == 'content/'+self.path]
        new_items = [('content/'+f, None) for f in self.files]
        id_map = {}
        for item in items:
            id_map[item.get('id')] = opf.replace_manifest_item(item, new_items)
        
        for id in id_map.keys():
            opf.replace_spine_items_by_idref(id, id_map[id])
        
        for ref in opf.iterguide():
            href = ref.get('href', '') 
            if href.startswith('content/'+self.path):
                href = href.split('#')
                frag = None
                if len(href) > 1:
                    frag = href[1]
                if frag not in self.anchor_map:
                    self.log_warning('\t\tUnable to re-map OPF link', href)
                    continue
                new_file = self.anchor_map[frag]
                ref.set('href', 'content/'+new_file+('' if frag is None else ('#'+frag)))

          
                
def fix_content_links(html_files, changes, opts):
    split_files = [f.path for f in changes]
    anchor_maps = [f.anchor_map for f in changes]
    files = list(html_files)
    for j, f in enumerate(split_files):
        try:
            i = files.index(f)
            files[i:i+1] = changes[j].files
        except ValueError:
            continue
        
    for htmlfile in files:
        changed = False
        root = html.fromstring(open(content(htmlfile), 'rb').read())
        for a in root.xpath('//a[@href]'):
            href = a.get('href')
            if not href.startswith('#'):
                href = href.split('#')
                anchor = href[1] if len(href) > 1 else None
                href = href[0]
                if href in split_files:
                    try:
                        newf = anchor_maps[split_files.index(href)][anchor]
                    except:
                        print '\t\tUnable to remap HTML link:', href, anchor
                        continue
                    frag = ('#'+anchor) if anchor else ''
                    a.set('href', newf+frag)
                    changed = True
                    
        if changed:
            open(content(htmlfile), 'wb').write(tostring(root, pretty_print=opts.pretty_print))

def fix_ncx(path, changes):
    split_files = [f.path for f in changes]
    anchor_maps = [f.anchor_map for f in changes]
    tree = etree.parse(path)
    changed = False
    for content in tree.getroot().xpath('//x:content[@src]', 
                    namespaces={'x':"http://www.daisy.org/z3986/2005/ncx/"}):
        href = content.get('src')
        if not href.startswith('#'):
            href = href.split('#')
            anchor = href[1] if len(href) > 1 else None
            href = href[0].split('/')[-1]
            if href in split_files:
                try:
                    newf = anchor_maps[split_files.index(href)][anchor]
                except:
                    print 'Unable to remap NCX link:', href, anchor
                frag = ('#'+anchor) if anchor else ''
                content.set('src', 'content/'+newf+frag)
                changed = True
    if changed:
        open(path, 'wb').write(etree.tostring(tree.getroot(), encoding='UTF-8', xml_declaration=True))

def find_html_files(opf):
    '''
    Find all HTML files referenced by `opf`.
    '''
    html_files = []
    for item in opf.itermanifest():
        if 'html' in item.get('media-type', '').lower():
            f = item.get('href').split('/')[-1]
            f2 = f.replace('&', '%26')
            if not os.path.exists(content(f)) and os.path.exists(content(f2)):
                f = f2
                item.set('href', item.get('href').replace('&', '%26'))
            if os.path.exists(content(f)):
                html_files.append(f)
    return html_files
        

def split(pathtoopf, opts, stylesheet_map):
    pathtoopf = os.path.abspath(pathtoopf)
    opf = OPF(open(pathtoopf, 'rb'), os.path.dirname(pathtoopf))
    
    with CurrentDir(os.path.dirname(pathtoopf)):
        html_files = find_html_files(opf)
        changes = [Splitter(f, opts, stylesheet_map, opf) for f in html_files]
        changes = [c for c in changes if c.was_split]
        
        fix_content_links(html_files, changes, opts)
        for item in opf.itermanifest():
            if item.get('media-type', '') == 'application/x-dtbncx+xml':
                fix_ncx(item.get('href'), changes)
                break 

        open(pathtoopf, 'wb').write(opf.render())
