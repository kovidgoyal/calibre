#! /usr/bin/python

from __future__ import with_statement
import sys
import os
import re
import types
import copy
import itertools
from collections import defaultdict
from lxml import etree
from stylizer import Page, Stylizer, Style

XHTML_NS = 'http://www.w3.org/1999/xhtml'
XPNSMAP = {'h': XHTML_NS,}

class Splitter(object):
    XML_PARSER = etree.XMLParser(remove_blank_text=True)
    COLLAPSE = re.compile(r'[ \n\r]+')
    CONTENT_TAGS = set(['img', 'object', 'embed'])
    for tag in list(CONTENT_TAGS):
        CONTENT_TAGS.add('{%s}%s' % (XHTML_NS, tag))
    
    def __init__(self, path):
        with open(path, 'rb') as f:
            self.tree = etree.parse(f, parser=self.XML_PARSER)
        self.stylizer = Stylizer(self.tree, path)
        self.path = path
        self.basename = os.path.splitext(
            os.path.basename(path))[0].lower()
        self.splits = []
        self.names = []
        self.idmap = {}
        self.fonts = defaultdict(int)
        self.content = False

    def split(self):
        tree = self.tree
        for prefix in ('', 'h:'):
            d = {'h': prefix}
            roots = tree.xpath('/%(h)shtml' % d, namespaces=XPNSMAP)
            if roots: break
        self.root, = roots
        self.head, = tree.xpath('/%(h)shtml/%(h)shead' % d, namespaces=XPNSMAP)
        body, = tree.xpath('/%(h)shtml/%(h)sbody' % d, namespaces=XPNSMAP)
        self._split(body, [self.new_root(str(self.basename))], 9.0)
        results = zip(self.names, self.splits)
        self.post_process_links(results, d)
        return results

    def new_root(self, name):
        nroot = self.dup(self.root)
        nroot.append(copy.deepcopy(self.head))
        self.splits.append(nroot)
        self.names.append(name + '.html')
        return nroot

    def dup(self, e):
        new = etree.Element(e.tag, nsmap=e.nsmap, **dict(e.attrib))
        new.text = e.text
        new.tail = e.tail
        return new
    
    def dupsub(self, p, e):
        new = etree.SubElement(p, e.tag, nsmap=e.nsmap, **dict(e.attrib))
        new.text = e.text
        new.tail = e.tail
        return new

    def _split(self, src, dstq, psize):
        style = self.stylizer.style(src)
        if self.new_page(style, 'before'):
            self.new_split(src, dstq)
        attrib = src.attrib
        name = self.names[-1]
        for aname in ('id', 'name'):
            if aname in attrib:
                self.idmap[attrib[aname]] = name
        text = self.COLLAPSE.sub(' ', src.text or '')
        tail = self.COLLAPSE.sub(' ', src.text or '')
        if text or tail or src.tag.lower() in self.CONTENT_TAGS:
            self.content = True
        size = style['font-size']
        self.fonts[size] += len(text)
        self.fonts[psize] += len(tail)
        new = self.dupsub(dstq[-1], src)
        if len(src) > 0:
            dstq.append(new)
            for child in src:
                self._split(child, dstq, size)
            dstq.pop()
        if self.new_page(style, 'after'):
            self.new_split(src, dstq)

    def new_page(self, style, when):
        if self.content \
                and (style['page-break-%s' % when] \
                         in ('always', 'odd', 'even')):
            return True
        return False
            
    def new_split(self, src, dstq):
        name = self.basename
        attrib = src.attrib
        if 'class' in attrib:
            name = src.attrib['class']            
            if ' ' in name:
                name = name.split(' ', 2)[0]
        if 'id' in attrib:
            name = '%s-%s' % (name, attrib['id'])
        name = name.lower().replace('_', '-')
        if (name + '.html') in self.names:
            name = '%s-%02d' % (name, len(self.names))
        prev = None
        for i in xrange(len(dstq)):
            new = self.new_root(name) if prev is None \
                else self.dupsub(prev, dstq[i])
            prev = dstq[i] = new
        self.content = False

    def post_process_links(self, results, prefixes):
        basename = os.path.basename(self.path)
        query = '//%(h)sa[@href]' % prefixes
        for name, root in results:
            elements = root.xpath(query, namespaces=XPNSMAP)
            for element in elements:
                href = element.attrib['href']
                if '#' not in href: continue
                fname, id = href.split('#', 2)
                if fname in ('', basename):
                    href = '#'.join((self.idmap[id], id))
                    element.attrib['href'] = href

def main():
    def xml2str(root):
        return etree.tostring(root, pretty_print=True,
                              encoding='utf-8', xml_declaration=True)
    tree = None
    path = sys.argv[1]
    dest = sys.argv[2]
    splitter = Splitter(path)
    for name, root in splitter.split():
        print name
        with open(os.path.join(dest, name), 'wb') as f:
            f.write(xml2str(root))
    return 0

if __name__ == '__main__':
    sys.exit(main())
