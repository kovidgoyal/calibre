#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap

from lxml import etree

from calibre.ebooks.oeb.base import XPNSMAP
from calibre import guess_type

class Jacket(object):
    '''
    Book jacket manipulation. Remove first image and insert comments at start of
    book.
    '''

    JACKET_TEMPLATE = textwrap.dedent(u'''\
    <html xmlns="%(xmlns)s">
        <head>
            <title>%(title)s</title>
        </head>
        <body>
            <div class="calibre_rescale_100">
                <div style="text-align:center">
                    <h1 class="calibre_rescale_180">%(title)s</h1>
                    <h2 class="calibre_rescale_140">%(jacket)s</h2>
                    <div class="calibre_rescale_100">%(series)s</div>
                    <div class="calibre_rescale_100">%(tags)s</div>
                </div>
                <div style="margin-top:2em" class="calibre_rescale_100">
                    %(comments)s
                </div>
            </div>
        </body>
    </html>
    ''')

    def remove_first_image(self):
        for i, item in enumerate(self.oeb.spine):
            if i > 2: break
            for img in item.data.xpath('//h:img[@src]', namespace=XPNSMAP):
                href = item.abshref(img.get('src'))
                image = self.oeb.manifest.hrefs.get(href, None)
                if image is not None:
                    self.log('Removing first image', img.get('src'))
                    self.oeb.manifest.remove(image)
                    img.getparent().remove(img)
                    return

    def insert_metadata(self, mi):
        self.log('Inserting metadata into book...')
        comments = mi.comments
        if not comments:
            try:
                comments = unicode(self.oeb.metadata.description[0])
            except:
                comments = ''
        if not comments.strip():
            comments = ''
        comments = comments.replace('\r\n', '\n').replace('\n\n', '<br/><br/>')
        series = '<b>Series: </b>' + mi.series if mi.series else ''
        if series and mi.series_index is not None:
            series += ' [%s]'%mi.format_series_index()
        tags = mi.tags
        if not tags:
            try:
                tags = map(unicode, self.oeb.metadata.subject)
            except:
                tags = []
        if tags:
            tags = '<b>Tags: </b>' + self.opts.dest.tags_to_string(tags)
        else:
            tags = ''
        try:
            title = mi.title if mi.title else unicode(self.oeb.metadata.title[0])
        except:
            title = _('Unknown')
        html = self.JACKET_TEMPLATE%dict(xmlns=XPNSMAP['h'],
                title=title, comments=comments,
                jacket=_('Book Jacket'), series=series, tags=tags)
        id, href = self.oeb.manifest.generate('jacket', 'jacket.xhtml')
        root = etree.fromstring(html)
        item = self.oeb.manifest.add(id, href, guess_type(href)[0], data=root)
        self.oeb.spine.insert(0, item, True)


    def __call__(self, oeb, opts, metadata):
        self.oeb, self.opts, self.log = oeb, opts, oeb.log
        if opts.remove_first_image:
            self.remove_first_image()
        if opts.insert_metadata:
            self.insert_metadata(metadata)
