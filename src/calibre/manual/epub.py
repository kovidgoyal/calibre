#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, mimetypes, uuid, shutil
from datetime import datetime
from docutils import nodes
from xml.sax.saxutils import escape, quoteattr
from urlparse import urldefrag
from zipfile import ZipFile, ZIP_STORED, ZipInfo

from sphinx import addnodes
from sphinx.builders.html import StandaloneHTMLBuilder

NCX = '''\
<?xml version="1.0"  encoding="UTF-8"?>
<ncx version="2005-1"
     xml:lang="en"
     xmlns="http://www.daisy.org/z3986/2005/ncx/"
     xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata"
>
    <head>
        <meta name="dtb:uid" content="{uid}"/>
        <meta name="dtb:depth" content="{depth}"/>
        <meta name="dtb:generator" content="sphinx"/>
        <meta name="dtb:totalPageCount" content="0"/>
        <meta name="dtb:maxPageNumber" content="0"/>
    </head>
    <docTitle><text>Table of Contents</text></docTitle>
    <navMap>
        {navpoints}
    </navMap>
</ncx>
'''

OPF = '''\
<?xml version="1.0"  encoding="UTF-8"?>
<package version="2.0"
         xmlns="http://www.idpf.org/2007/opf"
         unique-identifier="sphinx_id"
>
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf" xmlns:calibre="http://calibre.kovidgoyal.net/2009/metadata">
        <dc:title>{title}</dc:title>
        <dc:creator opf:role="aut">{author}</dc:creator>
        <dc:contributor opf:role="bkp">Sphinx</dc:contributor>
        <dc:identifier opf:scheme="sphinx" id="sphinx_id">{uid}</dc:identifier>
        <dc:date>{date}</dc:date>
        <meta name="calibre:publication_type" content="sphinx_manual" />
    </metadata>
    <manifest>
    {manifest}
    </manifest>
    <spine toc="ncx">
    {spine}
    </spine>
    <guide>
    {guide}
    </guide>
</package>
'''

CONTAINER='''\
<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
   <rootfiles>
      <rootfile full-path="{0}" media-type="application/oebps-package+xml"/>
   </rootfiles>
</container>
'''
class TOC(list):

    def __init__(self, title=None, href=None):
        list.__init__(self)
        self.title, self.href = title, href

    def create_child(self, title, href):
        self.append(TOC(title, href))
        return self[-1]

    def depth(self):
        try:
            return max(node.depth() for node in self)+1
        except ValueError:
            return 1


class EPUBHelpBuilder(StandaloneHTMLBuilder):
    """
    Builder that also outputs Qt help project, contents and index files.
    """
    name = 'epub'

    # don't copy the reST source
    copysource = False

    supported_image_types = ['image/svg+xml', 'image/png', 'image/gif',
                             'image/jpeg']

    # don't add links
    add_permalinks = False
    # don't add sidebar etc.
    embedded = True

    def init(self):
        StandaloneHTMLBuilder.init(self)
        self.out_suffix = '.html'
        self.link_suffix = '.html'
        self.html_outdir = self.outdir = os.path.join(self.outdir, 'src')
        self.conf = self.config

    def finish(self):
        StandaloneHTMLBuilder.finish(self)
        self.create_titlepage()
        self.outdir = os.path.dirname(self.outdir)
        cwd = os.getcwd()
        os.chdir(self.html_outdir)
        try:
            self.generate_manifest()
            self.generate_toc()
            self.render_opf()
            self.render_epub()
        finally:
            os.chdir(cwd)

    def render_epub(self):
        container = CONTAINER.format('content.opf')
        path = os.path.abspath('..'+os.sep+self.conf.project+'.epub')
        zf = ZipFile(path, 'w')
        zi = ZipInfo('mimetype')
        zi.compress_type = ZIP_STORED
        zf.writestr(zi, 'application/epub+zip')
        zf.writestr('META-INF/container.xml', container)
        for url in self.manifest:
            fp = os.path.join(self.html_outdir, *url.split('/'))
            zf.write(fp, url)
        zf.close()
        self.info('EPUB created at: '+path)


    def render_opf(self):
        manifest = []
        for href in self.manifest:
            mt, id = self.manifest[href]
            manifest.append(' '*8 + '<item id=%s href=%s media-type=%s />'%\
                    tuple(map(quoteattr, (id, href, mt))))
        manifest = '\n'.join(manifest)
        spine = [' '*8+'<itemref idref=%s />'%quoteattr(x) for x in self.spine]
        spine = '\n'.join(spine)
        guide = ''
        if self.conf.epub_titlepage:
            guide = ' '*8 + '<reference type="cover"  href="_static/titlepage.html" />'

        opf = OPF.format(title=escape(self.conf.html_title),
                author=escape(self.conf.epub_author), uid=str(uuid.uuid4()),
                date=datetime.now().isoformat(), manifest=manifest, spine=spine,
                guide=guide)
        open('content.opf', 'wb').write(opf)
        self.manifest['content.opf'] = ('application/oebps-package+xml', 'opf')

    def create_titlepage(self):
        if self.conf.epub_titlepage:
            img = ''
            if self.conf.epub_logo:
                img = '_static/epub_logo'+os.path.splitext(self.conf.epub_logo)[1]
                shutil.copyfile(self.conf.epub_logo,
                        os.path.join(self.html_outdir, *img.split('/')))
            raw = open(self.conf.epub_titlepage, 'rb').read()
            raw = raw%dict(title=self.conf.html_title,
                    version=self.conf.version,
                    img=img.split('/')[-1],
                    author=self.conf.epub_author)
            open(os.path.join(self.html_outdir, '_static', 'titlepage.html'), 'wb').write(raw)

    def generate_manifest(self):
        self.manifest = {}
        id = 1
        for dirpath, dirnames, filenames in os.walk('.'):
            for fname in filenames:
                if fname == '.buildinfo':
                    continue
                fpath = os.path.abspath(os.path.join(dirpath, fname))
                url = os.path.relpath(fpath).replace(os.sep, '/')
                self.manifest[url] = mimetypes.guess_type(url, False)[0]
                if self.manifest[url] is None:
                    self.warn('Unknown mimetype for: ' + url)
                    self.manifest[url] = 'application/octet-stream'
                if self.manifest[url] == 'text/html':
                    self.manifest[url] = 'application/xhtml+xml'
                self.manifest[url] = (self.manifest[url], 'id'+str(id))
                id += 1

    def isdocnode(self, node):
        if not isinstance(node, nodes.list_item):
            return False
        if len(node.children) != 2:
            return False
        if not isinstance(node.children[0], addnodes.compact_paragraph):
            return False
        if not isinstance(node.children[0][0], nodes.reference):
            return False
        if not isinstance(node.children[1], nodes.bullet_list):
            return False
        return True

    def generate_toc(self):
        tocdoc = self.env.get_and_resolve_doctree(self.config.master_doc, self,
                                                  prune_toctrees=False)
        istoctree = lambda node: (
                        isinstance(node, addnodes.compact_paragraph)
                            and node.has_key('toctree'))
        toc = TOC()
        for node in tocdoc.traverse(istoctree):
            self.extend_toc(toc, node)
        self._parts = []
        self._po = 0
        self._po_map = {}
        self.spine_map = {}
        self.spine = []
        self.render_toc(toc)
        navpoints = '\n'.join(self._parts).strip()
        ncx = NCX.format(uid=str(uuid.uuid4()), depth=toc.depth(),
                navpoints=navpoints)
        open('toc.ncx', 'wb').write(ncx)
        self.manifest['toc.ncx'] = ('application/x-dtbncx+xml', 'ncx')
        self.spine.insert(0, self.manifest[self.conf.master_doc+'.html'][1])
        if self.conf.epub_titlepage:
            self.spine.insert(0, self.manifest['_static/titlepage.html'][1])

    def add_to_spine(self, href):
        href = urldefrag(href)[0]
        if href not in self.spine_map:
            for url in self.manifest:
                if url == href:
                    self.spine_map[href]= self.manifest[url][1]
                    self.spine.append(self.spine_map[href])

    def render_toc(self, toc, level=2):
        for child in toc:
            if child.title and child.href:
                href = child.href
                self.add_to_spine(href)
                title = escape(child.title)
                if isinstance(title, unicode):
                    title = title.encode('utf-8')
                if child.href in self._po_map:
                    po = self._po_map[child.href]
                else:
                    self._po += 1
                    po = self._po
                self._parts.append(' '*(level*4)+
                        '<navPoint id="%s" playOrder="%d">'%(uuid.uuid4(),
                            po))
                self._parts.append(' '*((level+1)*4)+
                    '<navLabel><text>%s</text></navLabel>'%title)
                self._parts.append(' '*((level+1)*4)+
                    '<content src=%s />'%quoteattr(href))
                self.render_toc(child, level+1)
                self._parts.append(' '*(level*4)+'</navPoint>')




    def extend_toc(self, toc, node):
        if self.isdocnode(node):
            refnode = node.children[0][0]
            parent = toc.create_child(refnode.astext(), refnode['refuri'])
            for subnode in node.children[1]:
                self.extend_toc(parent, subnode)
        elif isinstance(node, (nodes.list_item, nodes.bullet_list,
            addnodes.compact_paragraph)):
            for subnode in node:
                self.extend_toc(toc, subnode)
        elif isinstance(node, nodes.reference):
            parent = toc.create_child(node.astext(), node['refuri'])


