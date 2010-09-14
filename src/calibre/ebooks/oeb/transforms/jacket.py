#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, textwrap
from xml.sax.saxutils import escape
from itertools import repeat

from lxml import etree

from calibre import guess_type, strftime
from calibre.constants import __appname__, __version__
from calibre.utils.date import now
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.ebooks.oeb.base import XPath, XPNSMAP
from calibre.library.comments import comments_to_html
class Jacket(object):
    '''
    Book jacket manipulation. Remove first image and insert comments at start of
    book.
    '''

    JACKET_TEMPLATE = textwrap.dedent(u'''\
    <html xmlns="%(xmlns)s">
        <head>
            <title>%(title_str)s</title>
            <meta name="calibre-content" content="jacket"/>
            <style type="text/css" media="screen">%(css)s</style>
        </head>
        <body>
            <div class="cbj_banner">
                <div class="cbj_title">%(title)s</div>
                <table class="cbj_header">
                  <tr class="cbj_series">
                    <td class="cbj_label">Series:</td>
                    <td class="cbj_content">%(series)s</td>
                  </tr>
                  <tr class="cbj_pubdate">
                    <td class="cbj_label">Published:</td>
                    <td class="cbj_content">%(pubdate)s</td>
                  </tr>
                  <tr class="cbj_rating">
                    <td class="cbj_label">Rating:</td>
                    <td class="cbj_content">%(rating)s</td>
                  </tr>
                  <tr class="cbj_tags">
                    <td class="cbj_label">Tags:</td>
                    <td class="cbj_content">%(tags)s</td>
                  </tr>
                </table>
                <div class="cbj_footer">%(footer)s</div>
            </div>
            <hr class="cbj_kindle_banner_hr" />
            <div class="cbj_comments">%(comments)s</div>
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
            return ans
        try:
            num = float(rating)/2
        except:
            return ans
        num = max(0, num)
        num = min(num, 5)
        if num < 1:
            return ans
        if self.opts.output_profile.name == 'Kindle':
            ans = '%s' % ''.join(repeat('&#9733;', num))
        else:
            id, href = self.oeb.manifest.generate('star', 'star.png')
            self.oeb.manifest.add(id, href, 'image/png', data=I('star.png', data=True))
            ans = '%s' % ''.join(repeat('<img style="vertical-align:text-bottom" alt="star" src="%s" />'%href, num))
        return ans

    def insert_metadata(self, mi):
        self.log('Inserting metadata into book...')
        jacket_resources = P("jacket")

        css_data = ''
        stylesheet = os.path.join(jacket_resources, 'stylesheet.css')
        with open(stylesheet) as f:
            css = f.read()

        try:
            title_str = mi.title if mi.title else unicode(self.oeb.metadata.title[0])
        except:
            title_str = _('Unknown')
        title = '<span class="title">%s</span>' % (escape(title_str))

        series = escape(mi.series if mi.series else '')
        if mi.series and mi.series_index is not None:
            series += escape(' [%s]'%mi.format_series_index())
        if not mi.series:
            series = ''

        try:
            pubdate = strftime(u'%Y', mi.pubdate.timetuple())
        except:
            #pubdate = strftime(u'%Y', now())
            pubdate = ''

        rating = self.get_rating(mi.rating)

        tags = mi.tags
        if not tags:
            try:
                tags = map(unicode, self.oeb.metadata.subject)
            except:
                tags = []
        if tags:
            #tags = self.opts.dest.tags_to_string(tags)
            tags = ', '.join(tags)
        else:
            tags = ''

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

        footer = 'B<span class="cbj_smallcaps">OOK JACKET GENERATED BY %s %s</span>' % (__appname__.upper(),__version__)

        def generate_html(comments):
            args = dict(xmlns=XPNSMAP['h'],
                        title_str=title_str,
                        css=css,
                        title=title,
                        pubdate=pubdate,
                        series=series,
                        rating=rating,
                        tags=tags,
                        comments=comments,
                        footer = footer)

            # Post-process the generated html to strip out empty header items
            generated_html = self.JACKET_TEMPLATE % args
            soup = BeautifulSoup(generated_html)
            if not series:
                series_tag = soup.find('tr', attrs={'class':'cbj_series'})
                series_tag.extract()
            if not rating:
                rating_tag = soup.find('tr', attrs={'class':'cbj_rating'})
                rating_tag.extract()
            if not tags:
                tags_tag = soup.find('tr', attrs={'class':'cbj_tags'})
                tags_tag.extract()
            if not pubdate:
                pubdate_tag = soup.find('tr', attrs={'class':'cbj_pubdate'})
                pubdate_tag.extract()
            if self.opts.output_profile.name != 'Kindle':
                hr_tag = soup.find('hr', attrs={'class':'cbj_kindle_banner_hr'})
                hr_tag.extract()

            return soup.renderContents()

        id, href = self.oeb.manifest.generate('calibre_jacket', 'jacket.xhtml')
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
        '''
        Add metadata in jacket.xhtml if specifed in opts
        If not specified, remove previous jacket instance
        '''
        self.oeb, self.opts, self.log = oeb, opts, oeb.log
        if opts.remove_first_image:
            self.remove_first_image()
        if opts.insert_metadata:
            self.insert_metadata(metadata)
        else:
            jacket = XPath('//h:meta[@name="calibre-content" and @content="jacket"]')
            for item in list(self.oeb.spine)[:4]:
                if jacket(item.data):
                    try:
                        self.log.info("Removing previous jacket instance")
                        self.oeb.manifest.remove(item)
                        break
                    except:
                        continue
