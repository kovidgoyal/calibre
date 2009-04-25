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
            <h1 style="text-align: center">%(title)s</h1>
            <h2 style="text-align: center">%(jacket)s</h2>
            <div>
                %(comments)s
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

    def insert_comments(self, comments):
        self.log('Inserting metadata comments into book...')
        comments = comments.replace('\r\n', '\n').replace('\n\n', '<br/><br/>')
        html = self.JACKET_TEMPLATE%dict(xmlns=XPNSMAP['h'],
                title=self.opts.title, comments=comments,
                jacket=_('Book Jacket'))
        id, href = self.oeb.manifest.generate('jacket', 'jacket.xhtml')
        root = etree.fromstring(html)
        item = self.oeb.manifest.add(id, href, guess_type(href)[0], data=root)
        self.oeb.spine.insert(0, item, True)


    def __call__(self, oeb, opts):
        self.oeb, self.opts, self.log = oeb, opts, oeb.log
        if opts.remove_first_image:
            self.remove_fisrt_image()
        if opts.insert_comments and opts.comments:
            self.insert_comments(opts.comments)
