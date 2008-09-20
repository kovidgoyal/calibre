#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
Split the flows in an epub file to conform to size limitations.
'''

import sys, os, math, copy

from lxml.etree import parse, XMLParser
from lxml.cssselect import CSSSelector

from calibre.ebooks.metadata.opf2 import OPF
from calibre.ebooks.epub import tostring

PARSER = XMLParser(recover=True)

class SplitError(ValueError):
    
    def __init__(self, path):
        ValueError.__init__(self, _('Could not find reasonable point at which to split: ')+os.path.basename(path))

def split_tree(tree, split_point, before, opts, filepath):
    trees = set([])
    tree2 = copy.deepcopy(tree)
    path = tree.getpath(split_point)
    root, root2 = tree.getroot(), tree2.getroot()
    body, body2 = root.xpath('//body')[0], root2.xpath('//body')[0]
    split_point2 = root2.xpath(path)[0]
    
    # Tree 1
    hit_split_point = False
    for elem in body.iterdescendants():
        if elem is split_point:
            hit_split_point = True
            if before:
                elem.text = u''
                elem.tail = u''
                elem.set('calibre_split', '1')
            continue
        if hit_split_point:
            elem.text = u''
            elem.tail = u''
        elem.set('calibre_split', '1' if hit_split_point else '0')
        
    # Tree 2
    hit_split_point = False
    for elem in body2.iterdescendants():
        if elem is split_point2:
            hit_split_point = True
            if not before:
                elem.text = u''
                elem.tail = u''
                elem.set('calibre_split', '1')
            continue
        if not hit_split_point:
            elem.text = u''
            elem.tail = u''
        elem.set('calibre_split', '0' if hit_split_point else '1')
    
    for t, r in [(tree, root), (tree2, root2)]:
        if len(tostring(r)) < opts.profile.flow_size:
            trees.append(t)
        else:
            new_split_point, before = find_split_point(t)
            if new_split_point is None:
                raise SplitError(filepath)
            trees.extend(split_tree(t, new_split_point, before, opts, filepath))
            
    return trees
    

def find_split_point(tree):
    root = tree.getroot()
    css = root.xpath('//style[@type="text/css"]')
    if css:
        
        def pick_elem(elems):
            if elems:
                elems = [i for i in elems if elem.get('calibre_split', '0') != '1']
                if elems:
                    i = int(math.floor(len(elems)/2.))
                    return elems[i]
        
        def selector_element(rule):
            try:
                selector = CSSSelector(rule.selectorText)
                return pick_elem(selector(root))
            except:
                return None
        
        css = css[0].text
        from cssutils import CSSParser
        stylesheet = CSSParser().parseString(css)
        for rule in stylesheet:
            if rule.type != rule.STYLE_RULE:
                continue
            before = getattr(rule.style.getPropertyCSSValue('page-break-before'), 'cssText', '').strip().lower()
            if before and before != 'avoid':
                elem = selector_element(rule)
                if elem is not None:
                    return elem, True
            after  = getattr(rule.style.getPropertyCSSValue('page-break-after'), 'cssText', '').strip().lower()
            if after and after != 'avoid':
                elem = selector_element(rule)
                if elem is not None:
                    return elem, False
                
    for path in ('//*[re:match(name(), "h[1-6]", "i")', '/body/div', '//p'):
        elems = root.xpath(path)
        elem = pick_elem(elems)
        if elem is not None:
            return elem, True
        
    return None, True

def do_split(path, opts):
    tree = parse(path, parser=PARSER)
    split_point, before = find_split_point(tree)
    if split_point is None:
        raise SplitError(path)
    trees = split_tree(tree, split_point, before, opts, path)
    base = os.path.splitext(os.path.basename(path))[0] + '_split_%d.html'
    anchor_map = {None:base%0}
    files = []
    for i, tree in enumerate(trees):
        root = tree.getroot()
        files.append(base%i)
        for elem in root.xpath('//*[@id and @calibre_split = "1"]'):
            anchor_map[elem.get('id')] = files[-1]
            elem.attrib.pop('calibre_split')
        for elem in root.xpath('//*[@calibre_split]'):
            elem.attrib.pop('calibre_split')
        open(os.path.join(os.path.dirname(path), files[-1]), 'wb').write(tostring(root, pretty_print=opts.pretty_print))
    os.remove(path)
    return path, files, anchor_map

def fix_opf(opf, orig_file, files, anchor_map):
    orig = None
    for item in opf.manifest:
        if os.path.samefile(orig_file, item.path):
            orig = item
            break
    opf.manifest.remove(orig)
    ids = []
    for f in files:
        ids.append(opf.manifest.add_item(f))
    index = None
    for i, item in enumerate(opf.spine):
        if item.id == orig.id:
            index = i
            break
        
    
            
 
def split(pathtoopf, opts):
    return
    pathtoopf = os.path.abspath(pathtoopf)
    opf = OPF(open(pathtoopf, 'rb'), os.path.dirname(pathtoopf))
    html_files = []
    for item in opf.manifest:
        if 'html' in item.mime_type.lower():
            html_files.append(item.path)
    changes = []
    for f in html_files:
        if os.stat(f).st_size > opts.profile.flow_size:
            fix_opf(opf, *do_split(f, opts))
    if changes:
        pass
        
             
        
    

def main(args=sys.argv):
    return 0

if __name__ == '__main__':
    sys.exit(main())