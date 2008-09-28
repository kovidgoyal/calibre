from __future__ import with_statement
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Split the flows in an epub file to conform to size limitations.
'''

import os, math, copy, logging, functools, collections

from lxml.etree import XPath as _XPath
from lxml import etree, html
from lxml.cssselect import CSSSelector
from cssutils import CSSParser

from calibre.ebooks.metadata.opf2 import OPF
from calibre.ebooks.epub import tostring
from calibre import CurrentDir, LoggingInterface

XPath = functools.partial(_XPath, namespaces={'re':'http://exslt.org/regular-expressions'})
content = functools.partial(os.path.join, 'content')

SPLIT_ATTR       = 'cs'
SPLIT_POINT_ATTR = 'csp'

class SplitError(ValueError):
    
    def __init__(self, path, root):
        size = len(tostring(root))/1024.
        ValueError.__init__(self, _('Could not find reasonable point at which to split: %s Sub-tree size: %d KB')% 
                            (os.path.basename(path), size))

    

class Splitter(LoggingInterface):
    
    def __init__(self, path, opts, always_remove=False):
        LoggingInterface.__init__(self, logging.getLogger('htmlsplit'))
        self.setup_cli_handler(opts.verbose)
        self.path = path
        self.always_remove = always_remove
        self.base = (os.path.splitext(path)[0].replace('%', '%%') + '_split_%d.html')
        self.opts = opts
        self.orig_size = os.stat(content(path)).st_size
        self.log_info('\tSplitting %s (%d KB)', path, self.orig_size/1024.)
        root = html.fromstring(open(content(path)).read())
            
        css = XPath('//link[@type = "text/css" and @rel = "stylesheet"]')(root)
        if css:
            cssp = os.path.join('content', *(css[0].get('href').split('/')))
            self.log_debug('\t\tParsing stylesheet...')
            try: 
                stylesheet = CSSParser().parseString(open(cssp, 'rb').read())
            except:
                self.log_warn('Failed to parse CSS. Splitting on page-breaks is disabled')
                if self.opts.verbose > 1:
                    self.log_exception('')
                stylesheet = None
        else:
            stylesheet = None
        self.page_breaks = []
        if stylesheet is not None:
            self.find_page_breaks(stylesheet, root)
            
        self.trees = []
        self.split_size = 0
        self.split(root.getroottree())
        self.commit()
        self.log_info('\t\tSplit into %d parts.', len(self.trees))
        if self.opts.verbose:
            for f in self.files:
                self.log_info('\t\t\t%s - %d KB', f, os.stat(content(f)).st_size/1024.)
        self.trees = None
        
    def split(self, tree):
        '''
        Split ``tree`` into a *before* and *after* tree, preserving tag structure,
        but not duplicating any text. All tags that have had their text and tail
        removed have the attribute ``calibre_split`` set to 1.
        '''
        self.log_debug('\t\tSplitting...')
        root = tree.getroot()
        split_point, before = self.find_split_point(root)
        if split_point is None or self.split_size > 6*self.orig_size:
            if not self.always_remove:
                self.log_warn(_('\t\tToo much markup. Re-splitting without structure preservation. This may cause incorrect rendering.'))
            raise SplitError(self.path, root)
        tree2 = copy.deepcopy(tree)
        root2 = tree2.getroot()
        body, body2 = root.body, root2.body
        path = tree.getpath(split_point)
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
                    elem.set('style', 'display:none;')
        
        def fix_split_point(sp):
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
        
        for t, r in [(tree, root), (tree2, root2)]:
            size = len(tostring(r)) 
            if size <= self.opts.profile.flow_size:
                self.trees.append(t)
                self.log_debug('\t\t\tCommitted sub-tree #%d (%d KB)', len(self.trees), size/1024.)
                self.split_size += size
            else:
                self.split(t)
                
                
    def find_page_breaks(self, stylesheet, root):
        '''
        Find all elements that have either page-break-before or page-break-after set.
        '''
        page_break_selectors = set([])
        for rule in stylesheet:
            if rule.type != rule.STYLE_RULE:
                continue
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
        tree = root.getroottree()
        self.page_breaks = [(XPath(tree.getpath(x)), x.pb_before) for x in page_breaks]
        
    def find_split_point(self, root):
        '''
        Find the tag at which to split the tree rooted at `root`. 
        Search order is:
            * page breaks
            * Heading tags
            * <div> tags
            * <p> tags
            
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
    
        page_breaks = []
        for x in self.page_breaks:
            pb = x[0](root)
            if pb:
                page_breaks.append(pb[0])
                
        elem = pick_elem(page_breaks)
        if elem is not None:
            i = page_breaks.index(elem)
            return elem, self.page_breaks[i][1]
        
            
                            
        for path in ('//*[re:match(name(), "h[1-6]", "i")]', '/html/body/div', '//p'):
            elems = root.xpath(path)
            elem = pick_elem(elems)
            if elem is not None:
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
                    newf = anchor_maps[split_files.index(href)][anchor]
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
    for content in tree.getroot().xpath('//x:content[@src]', namespaces={'x':"http://www.daisy.org/z3986/2005/ncx/"}):
        href = content.get('src')
        if not href.startswith('#'):
            href = href.split('#')
            anchor = href[1] if len(href) > 1 else None
            href = href[0].split('/')[-1]
            if href in split_files:
                newf = anchor_maps[split_files.index(href)][anchor]
                frag = ('#'+anchor) if anchor else ''
                content.set('src', 'content/'+newf+frag)
                changed = True
    if changed:
        open(path, 'wb').write(etree.tostring(tree.getroot(), encoding='UTF-8', xml_declaration=True))
       
def split(pathtoopf, opts):
    pathtoopf = os.path.abspath(pathtoopf)
    with CurrentDir(os.path.dirname(pathtoopf)):
        opf = OPF(open(pathtoopf, 'rb'), os.path.dirname(pathtoopf))
        html_files = []
        for item in opf.itermanifest():
            if 'html' in item.get('media-type', '').lower():
                f = item.get('href').split('/')[-1]
                f2 = f.replace('&', '%26')
                if not os.path.exists(content(f)) and os.path.exists(content(f2)):
                    f = f2
                    item.set('href', item.get('href').replace('&', '%26'))
                html_files.append(f)
        changes = []
        always_remove = getattr(opts, 'dont_preserve_structure', False)
        for f in html_files:
            if os.stat(content(f)).st_size > opts.profile.flow_size:
                try:
                    changes.append(Splitter(f, opts, always_remove=always_remove))
                except SplitError:
                    if not always_remove:
                        changes.append(Splitter(f, opts, always_remove=True))
                    else:
                        raise
                changes[-1].fix_opf(opf)
        
        open(pathtoopf, 'wb').write(opf.render())
        fix_content_links(html_files, changes, opts)
        
        for item in opf.itermanifest():
            if item.get('media-type', '') == 'application/x-dtbncx+xml':
                fix_ncx(item.get('href'), changes)
                break 
