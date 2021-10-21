#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid at kovidgoyal.net>'

import os, glob, re, functools
from collections import Counter

from lxml import etree
from lxml.builder import ElementMaker

from calibre.constants import __appname__, __version__
from calibre.ebooks.chardet import xml_to_unicode
from calibre.utils.xml_parse import safe_xml_fromstring
from calibre.utils.cleantext import clean_xml_chars
from polyglot.urllib import unquote, urlparse

NCX_NS = "http://www.daisy.org/z3986/2005/ncx/"
CALIBRE_NS = "http://calibre.kovidgoyal.net/2009/metadata"
NSMAP = {None: NCX_NS, 'calibre':CALIBRE_NS}
E = ElementMaker(namespace=NCX_NS, nsmap=NSMAP)
C = ElementMaker(namespace=CALIBRE_NS, nsmap=NSMAP)


def parse_html_toc(data):
    from html5_parser import parse
    from calibre.utils.cleantext import clean_xml_chars
    from lxml import etree
    if isinstance(data, bytes):
        data = xml_to_unicode(data, strip_encoding_pats=True, resolve_entities=True)[0]
    root = parse(clean_xml_chars(data), maybe_xhtml=True, keep_doctype=False, sanitize_names=True)
    for a in root.xpath('//*[@href and local-name()="a"]'):
        purl = urlparse(unquote(a.get('href')))
        href, fragment = purl[2], purl[5]
        if not fragment:
            fragment = None
        else:
            fragment = fragment.strip()
        href = href.strip()

        txt = etree.tostring(a, method='text', encoding='unicode')
        yield href, fragment, txt


class TOC(list):

    def __init__(self, href=None, fragment=None, text=None, parent=None,
            play_order=0, base_path=os.getcwd(), type='unknown', author=None,
            description=None, toc_thumbnail=None):
        self.href = href
        self.fragment = fragment
        if not self.fragment:
            self.fragment = None
        self.text = text
        self.parent = parent
        self.base_path = base_path
        self.play_order = play_order
        self.type = type
        self.author = author
        self.description = description
        self.toc_thumbnail = toc_thumbnail

    def __str__(self):
        lines = ['TOC: %s#%s %s'%(self.href, self.fragment, self.text)]
        for child in self:
            c = str(child).splitlines()
            for l in c:
                lines.append('\t'+l)
        return '\n'.join(lines)

    def count(self, type):
        return len([i for i in self.flat() if i.type == type])

    def purge(self, types, max=0):
        remove = []
        for entry in self.flat():
            if entry.type in types:
                remove.append(entry)
        remove = remove[max:]
        for entry in remove:
            if entry.parent is None:
                continue
            entry.parent.remove(entry)
        return remove

    def remove(self, entry):
        list.remove(self, entry)
        entry.parent = None

    def add_item(self, href, fragment, text, play_order=None, type='unknown',
            author=None, description=None, toc_thumbnail=None):
        if play_order is None:
            play_order = (self[-1].play_order if len(self) else self.play_order) + 1
        self.append(TOC(href=href, fragment=fragment, text=text, parent=self,
                        base_path=self.base_path, play_order=play_order,
                        type=type, author=author, description=description, toc_thumbnail=toc_thumbnail))
        return self[-1]

    def top_level_items(self):
        for item in self:
            if item.text is not None:
                yield item

    def depth(self):
        depth = 1
        for obj in self:
            c = obj.depth()
            if c > depth - 1:
                depth = c + 1
        return depth

    def flat(self):
        'Depth first iteration over the tree rooted at self'
        yield self
        for obj in self:
            yield from obj.flat()

    @property
    def abspath(self):
        'Return the file this toc entry points to as a absolute path to a file on the system.'

        if self.href is None:
            return None
        path = self.href.replace('/', os.sep)
        if not os.path.isabs(path):
            path = os.path.join(self.base_path, path)
        return path

    def read_from_opf(self, opfreader):
        toc = opfreader.soup.find('spine', toc=True)
        if toc is not None:
            toc = toc['toc']
        if toc is None:
            try:
                toc = opfreader.soup.find('guide').find('reference', attrs={'type':'toc'})['href']
            except:
                for item in opfreader.manifest:
                    if 'toc' in item.href().lower():
                        toc = item.href()
                        break

        if toc is not None:
            if toc.lower() not in ('ncx', 'ncxtoc'):
                toc = urlparse(unquote(toc))[2]
                toc = toc.replace('/', os.sep)
                if not os.path.isabs(toc):
                    toc = os.path.join(self.base_path, toc)
                try:
                    if not os.path.exists(toc):
                        bn  = os.path.basename(toc)
                        bn  = bn.replace('_top.htm', '_toc.htm')  # Bug in BAEN OPF files
                        toc = os.path.join(os.path.dirname(toc), bn)

                    self.read_html_toc(toc)
                except:
                    print('WARNING: Could not read Table of Contents. Continuing anyway.')
            else:
                path = opfreader.manifest.item(toc.lower())
                path = getattr(path, 'path', path)
                if path and os.access(path, os.R_OK):
                    try:
                        self.read_ncx_toc(path)
                    except Exception as err:
                        print('WARNING: Invalid NCX file:', err)
                    return
                cwd = os.path.abspath(self.base_path)
                m = glob.glob(os.path.join(cwd, '*.ncx'))
                if m:
                    toc = m[0]
                    self.read_ncx_toc(toc)

    def read_ncx_toc(self, toc, root=None):
        self.base_path = os.path.dirname(toc)
        if root is None:
            with open(toc, 'rb') as f:
                raw  = xml_to_unicode(f.read(), assume_utf8=True,
                        strip_encoding_pats=True)[0]
            root = safe_xml_fromstring(raw)
        xpn = {'re': 'http://exslt.org/regular-expressions'}
        XPath = functools.partial(etree.XPath, namespaces=xpn)

        def get_attr(node, default=None, attr='playorder'):
            for name, val in node.attrib.items():
                if name and val and name.lower().endswith(attr):
                    return val
            return default

        nl_path = XPath('./*[re:match(local-name(), "navlabel$", "i")]')
        txt_path = XPath('./*[re:match(local-name(), "text$", "i")]')
        content_path = XPath('./*[re:match(local-name(), "content$", "i")]')
        np_path = XPath('./*[re:match(local-name(), "navpoint$", "i")]')

        def process_navpoint(np, dest):
            try:
                play_order = int(get_attr(np, 1))
            except:
                play_order = 1
            href = fragment = text = None
            nd = dest
            nl = nl_path(np)
            if nl:
                nl = nl[0]
                text = ''
                for txt in txt_path(nl):
                    text += etree.tostring(txt, method='text',
                            encoding='unicode', with_tail=False)
                content = content_path(np)
                if content and text:
                    content = content[0]
                    # if get_attr(content, attr='src'):
                    purl = urlparse(content.get('src'))
                    href, fragment = unquote(purl[2]), unquote(purl[5])
                    nd = dest.add_item(href, fragment, text)
                    nd.play_order = play_order

            for c in np_path(np):
                process_navpoint(c, nd)

        nm = XPath('//*[re:match(local-name(), "navmap$", "i")]')(root)
        if not nm:
            raise ValueError('NCX files must have a <navmap> element.')
        nm = nm[0]

        for child in np_path(nm):
            process_navpoint(child, self)

    def read_html_toc(self, toc):
        self.base_path = os.path.dirname(toc)
        with lopen(toc, 'rb') as f:
            parsed_toc = parse_html_toc(f.read())
        for href, fragment, txt in parsed_toc:
            add = True
            for i in self.flat():
                if i.href == href and i.fragment == fragment:
                    add = False
                    break
            if add:
                self.add_item(href, fragment, txt)

    def render(self, stream, uid):
        root = E.ncx(
                E.head(
                    E.meta(name='dtb:uid', content=str(uid)),
                    E.meta(name='dtb:depth', content=str(self.depth())),
                    E.meta(name='dtb:generator', content='%s (%s)'%(__appname__,
                        __version__)),
                    E.meta(name='dtb:totalPageCount', content='0'),
                    E.meta(name='dtb:maxPageNumber', content='0'),
                ),
                E.docTitle(E.text('Table of Contents')),
        )
        navmap = E.navMap()
        root.append(navmap)
        root.set('{http://www.w3.org/XML/1998/namespace}lang', 'en')
        c = Counter()

        def navpoint(parent, np):
            text = np.text
            if not text:
                text = ''
            c[1] += 1
            item_id = 'num_%d'%c[1]
            text = clean_xml_chars(text)
            elem = E.navPoint(
                    E.navLabel(E.text(re.sub(r'\s+', ' ', text))),
                    E.content(src=str(np.href)+(('#' + str(np.fragment))
                        if np.fragment else '')),
                    id=item_id,
                    playOrder=str(np.play_order)
            )
            au = getattr(np, 'author', None)
            if au:
                au = re.sub(r'\s+', ' ', au)
                elem.append(C.meta(au, name='author'))
            desc = getattr(np, 'description', None)
            if desc:
                desc = re.sub(r'\s+', ' ', desc)
                try:
                    elem.append(C.meta(desc, name='description'))
                except ValueError:
                    elem.append(C.meta(clean_xml_chars(desc), name='description'))
            idx = getattr(np, 'toc_thumbnail', None)
            if idx:
                elem.append(C.meta(idx, name='toc_thumbnail'))
            parent.append(elem)
            for np2 in np:
                navpoint(elem, np2)

        for np in self:
            navpoint(navmap, np)
        raw = etree.tostring(root, encoding='utf-8', xml_declaration=True,
                pretty_print=True)
        stream.write(raw)
