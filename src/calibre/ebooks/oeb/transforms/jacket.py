#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import textwrap
from xml.sax.saxutils import escape
from itertools import repeat

from lxml import etree

from calibre.ebooks.oeb.base import XPath, XPNSMAP
from calibre import guess_type
from calibre.library.comments import comments_to_html
class Jacket(object):
    '''
    Book jacket manipulation. Remove first image and insert comments at start of
    book.
    '''

    JACKET_TEMPLATE = textwrap.dedent(u'''\
    <html xmlns="%(xmlns)s">
        <head>
            <title>%(title)s</title>
            <meta name="calibre-content" content="jacket"/>
        </head>
        <body>
            <div class="calibre_rescale_100">
                <div style="text-align:center">
                    <h1 class="calibre_rescale_180">%(title)s</h1>
                    <h2 class="calibre_rescale_140">%(jacket)s</h2>
                    <div class="calibre_rescale_100">%(series)s</div>
                    <div class="calibre_rescale_100">%(rating)s</div>
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
        path = XPath('//h:img[@src]')
        for i, item in enumerate(self.oeb.spine):
            if i > 2: break
            for img in path(item.data):
                href  = item.abshref(img.get('src'))
                image = self.oeb.manifest.hrefs.get(href, None)
                if image is not None:
                    self.log('Removing first image', img.get('src'))
                    self.oeb.manifest.remove(image)
                    img.getparent().remove(img)
                    return

    def get_rating(self, rating):
        ans = ''
        if rating is None:
            return
        try:
            num = float(rating)/2
        except:
            return ans
        num = max(0, num)
        num = min(num, 5)
        if num < 1:
            return ans
        id, href = self.oeb.manifest.generate('star', 'star.png')
        self.oeb.manifest.add(id, href, 'image/png', data=I('star.png', data=True))
        ans = 'Rating: ' + ''.join(repeat('<img style="vertical-align:text-top" alt="star" src="%s" />'%href, num))
        return ans

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
        orig_comments = comments
        if comments:
            comments = comments_to_html(comments)
        series = '<b>Series: </b>' + escape(mi.series if mi.series else '')
        if mi.series and mi.series_index is not None:
            series += escape(' [%s]'%mi.format_series_index())
        if not mi.series:
            series = ''
        tags = mi.tags
        if not tags:
            try:
                tags = map(unicode, self.oeb.metadata.subject)
            except:
                tags = []
        if tags:
            tags = '<b>Tags: </b>' + escape(self.opts.dest.tags_to_string(tags))
        else:
            tags = ''
        try:
            title = mi.title if mi.title else unicode(self.oeb.metadata.title[0])
        except:
            title = _('Unknown')

        def generate_html(comments):
            return self.JACKET_TEMPLATE%dict(xmlns=XPNSMAP['h'],
                title=escape(title), comments=comments,
                jacket=escape(_('Book Jacket')), series=series,
                tags=tags, rating=self.get_rating(mi.rating))
        id, href = self.oeb.manifest.generate('jacket', 'jacket.xhtml')
        from calibre.ebooks.oeb.base import RECOVER_PARSER, XPath
        try:
            root = etree.fromstring(generate_html(comments), parser=RECOVER_PARSER)
        except:
            root = etree.fromstring(generate_html(escape(orig_comments)),
                    parser=RECOVER_PARSER)
        jacket = XPath('//h:meta[@name="calibre-content" and @content="jacket"]')
        found = None
        for item in list(self.oeb.spine)[:4]:
            try:
                if jacket(item.data):
                    found = item
                    break
            except:
                continue
        if found is None:
            item = self.oeb.manifest.add(id, href, guess_type(href)[0], data=root)
            self.oeb.spine.insert(0, item, True)
        else:
            self.log('Found existing book jacket, replacing...')
            found.data = root


    def __call__(self, oeb, opts, metadata):
        self.oeb, self.opts, self.log = oeb, opts, oeb.log
        if opts.remove_first_image:
            self.remove_first_image()
        if opts.insert_metadata:
            self.insert_metadata(metadata)
