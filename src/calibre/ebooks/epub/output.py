#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
from urllib import unquote

from calibre.customize.conversion import OutputFormatPlugin
from calibre.ptempfile import TemporaryDirectory
from calibre.constants import __appname__, __version__
from calibre import strftime, guess_type
from lxml import etree


class EPUBOutput(OutputFormatPlugin):

    name = 'EPUB Output'
    author = 'Kovid Goyal'
    file_type = 'epub'

    TITLEPAGE_COVER = '''\
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
    <head>
        <title>Cover</title>
        <style type="text/css" title="override_css">
            @page {padding: 0pt; margin:0pt}
            body { text-align: center; padding:0pt; margin: 0pt; }
            div { margin: 0pt; padding: 0pt; }
        </style>
    </head>
    <body>
        <div>
            <img src="%s" alt="cover" style="height: 100%%" />
        </div>
    </body>
</html>
'''

    TITLEPAGE = '''\
<html  xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
    <head>
        <style type="text/css">
            body {
                background: white no-repeat fixed center center;
                text-align: center;
                vertical-align: center;
                overflow: hidden;
                font-size: 18px;
            }
            h1 { font-family: serif; }
            h2, h4 { font-family: monospace; }
        </style>
    </head>
    <body>
        <h1>%(title)s</h1>
        <br/><br/>
        <div style="position:relative">
            <div style="position: absolute; left: 0; top: 0; width:100%%; height:100%%; vertical-align:center">
                <img src="%(img)s" alt="calibre" style="opacity:0.3"/>
            </div>
            <div style="position: absolute; left: 0; top: 0; width:100%%; height:100%%; vertical-align:center">
                <h2>%(date)s</h2>
                <br/><br/><br/><br/><br/>
                <h3>%(author)s</h3>
                <br/><br/></br/><br/><br/><br/><br/><br/><br/>
                <h4>Produced by %(app)s</h4>
            </div>
        </div>
    </body>
</html>
'''

    def convert(self, oeb, output_path, input_plugin, opts, log):
        self.log, self.opts, self.oeb = log, opts, oeb

        self.workaround_ade_quirks()

        from calibre.ebooks.oeb.transforms.rescale import RescaleImages
        RescaleImages()(oeb, opts)
        self.insert_cover()

        with TemporaryDirectory('_epub_output') as tdir:
            from calibre.customize.ui import plugin_for_output_format
            oeb_output = plugin_for_output_format('oeb')
            oeb_output.convert(oeb, tdir, input_plugin, opts, log)
            opf = [x for x in os.listdir(tdir) if x.endswith('.opf')][0]
            self.condense_ncx([os.path.join(tdir, x) for x in os.listdir(tdir)\
                    if x.endswith('.ncx')][0])

            from calibre.ebooks.epub import initialize_container
            epub = initialize_container(output_path, os.path.basename(opf))
            epub.add_dir(tdir)
            epub.close()

    def default_cover(self):
        '''
        Create a generic cover for books that dont have a cover
        '''
        try:
            from calibre.gui2 import images_rc # Needed for access to logo
            from PyQt4.Qt import QApplication, QFile, QIODevice
        except:
            return None
        from calibre.ebooks.metadata import authors_to_string
        images_rc
        m = self.oeb.metadata
        title = unicode(m.title[0])
        a = [unicode(x) for x in m.creators if m.role == 'aut']
        author = authors_to_string(a)
        if QApplication.instance() is None: QApplication([])
        f = QFile(':/library')
        f.open(QIODevice.ReadOnly)
        img_data = str(f.readAll())
        id, href = self.oeb.manifest.generate('calibre-logo',
                'calibre-logo.png')
        self.oeb.manifest.add(id, href, 'image/png', data=img_data)
        html = self.TITLEPAGE%dict(title=title, author=author,
                date=strftime('%d %b, %Y'),
                app=__appname__ +' '+__version__,
                img=href)
        id, href = self.oeb.manifest.generate('calibre-titlepage',
                'calibre-titlepage.xhtml')
        return self.oeb.manifest.add(id, href, guess_type('t.xhtml')[0],
                data=etree.fromstring(html))


    def insert_cover(self):
        from calibre.ebooks.oeb.base import urldefrag
        from calibre import guess_type
        g, m = self.oeb.guide, self.oeb.manifest
        if 'titlepage' not in g:
            if 'cover' in g:
                tp = self.TITLEPAGE_COVER%unquote(g['cover'].href)
                id, href = m.generate('titlepage', 'titlepage.xhtml')
                item = m.add(id, href, guess_type('t.xhtml')[0],
                        data=etree.fromstring(tp))
            else:
                item = self.default_cover()
        else:
            item = self.oeb.manifest.hrefs[
                    urldefrag(self.oeb.guide['titlepage'].href)[0]]
        if item is not None:
            self.oeb.spine.insert(0, item, True)
            self.oeb.guide.refs['cover'].href = item.href
            if 'titlepage' in self.oeb.guide.refs:
                self.oeb.guide.refs['titlepage'].href = item.href



    def condense_ncx(self, ncx_path):
        if not self.opts.pretty_print:
            tree = etree.parse(ncx_path)
            for tag in tree.getroot().iter(tag=etree.Element):
                if tag.text:
                    tag.text = tag.text.strip()
                if tag.tail:
                    tag.tail = tag.tail.strip()
            compressed = etree.tostring(tree.getroot(), encoding='utf-8')
            open(ncx_path, 'wb').write(compressed)



    def workaround_ade_quirks(self):
        '''
        Perform various markup transforms to get the output to render correctly
        in the quirky ADE.
        '''
        from calibre.ebooks.oeb.base import XPNSMAP, XHTML
        from lxml.etree import XPath as _XPath
        from functools import partial
        XPath = partial(_XPath, namespaces=XPNSMAP)

        for x in self.oeb.spine:
            root = x.data
            body = XPath('//h:body')(root)
            if body:
                body = body[0]
            # Replace <br> that are children of <body> as ADE doesn't handle them
            if hasattr(body, 'xpath'):
                for br in XPath('./h:br')(body):
                    if br.getparent() is None:
                        continue
                    try:
                        sibling = br.itersiblings().next()
                    except:
                        sibling = None
                    br.tag = XHTML('p')
                    br.text = u'\u00a0'
                    if (br.tail and br.tail.strip()) or sibling is None or \
                    getattr(sibling, 'tag', '') != XHTML('br'):
                        style = br.get('style', '').split(';')
                        style = filter(None, map(lambda x: x.strip(), style))
                        style.append('margin: 0pt; border:0pt; height:0pt')
                        br.set('style', '; '.join(style))
                    else:
                        sibling.getparent().remove(sibling)
                        if sibling.tail:
                            if not br.tail:
                                br.tail = ''
                            br.tail += sibling.tail


            if self.opts.output_profile.remove_object_tags:
                for tag in XPath('//h:embed')(root):
                    tag.getparent().remove(tag)
                for tag in XPath('//h:object')(root):
                    if tag.get('type', '').lower().strip() in ('image/svg+xml',):
                        continue
                    tag.getparent().remove(tag)

            for tag in XPath('//h:title|//h:style')(root):
                if not tag.text:
                    tag.getparent().remove(tag)
            for tag in XPath('//h:script')(root):
                if not tag.text and not tag.get('src', False):
                    tag.getparent().remove(tag)

            for tag in XPath('//h:form')(root):
                tag.getparent().remove(tag)

            for tag in XPath('//h:center')(root):
                tag.tag = XHTML('div')
                tag.set('style', 'text-align:center')

            # ADE can't handle &amp; in an img url
            for tag in XPath('//h:img[@src]')(root):
                tag.set('src', tag.get('src', '').replace('&', ''))

            stylesheet = self.oeb.manifest.hrefs['stylesheet.css']
            stylesheet.data.add('a { color: inherit; text-decoration: inherit; '
                    'cursor: default; }')
            stylesheet.data.add('a[href] { color: blue; '
                    'text-decoration: underline; cursor:pointer; }')



