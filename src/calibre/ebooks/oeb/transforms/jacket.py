#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys
from xml.sax.saxutils import escape

from lxml import etree

from calibre import guess_type, strftime
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.ebooks.oeb.base import XPath, XHTML_NS, XHTML, xml2text, urldefrag
from calibre.library.comments import comments_to_html
from calibre.utils.date import is_date_undefined
from calibre.ebooks.chardet import strip_encoding_declarations

JACKET_XPATH = '//h:meta[@name="calibre-content" and @content="jacket"]'

class Jacket(object):
    '''
    Book jacket manipulation. Remove first image and insert comments at start of
    book.
    '''

    def remove_images(self, item, limit=1):
        path = XPath('//h:img[@src]')
        removed = 0
        for img in path(item.data):
            if removed >= limit:
                break
            href  = item.abshref(img.get('src'))
            image = self.oeb.manifest.hrefs.get(href, None)
            if image is not None:
                self.oeb.manifest.remove(image)
                img.getparent().remove(img)
                removed += 1
        return removed

    def remove_first_image(self):
        deleted_item = None
        for item in self.oeb.spine:
            removed = self.remove_images(item)
            if removed > 0:
                self.log('Removed first image')
                body = XPath('//h:body')(item.data)
                if body:
                    raw = xml2text(body[0]).strip()
                    imgs = XPath('//h:img|//svg:svg')(item.data)
                    if not raw and not imgs:
                        self.log('Removing %s as it has no content'%item.href)
                        self.oeb.manifest.remove(item)
                        deleted_item = item
                break
        if deleted_item is not None:
            for item in list(self.oeb.toc):
                href = urldefrag(item.href)[0]
                if href == deleted_item.href:
                    self.oeb.toc.remove(item)

    def insert_metadata(self, mi):
        self.log('Inserting metadata into book...')

        try:
            tags = map(unicode, self.oeb.metadata.subject)
        except:
            tags = []

        try:
            comments = unicode(self.oeb.metadata.description[0])
        except:
            comments = ''

        try:
            title = unicode(self.oeb.metadata.title[0])
        except:
            title = _('Unknown')

        root = render_jacket(mi, self.opts.output_profile,
                alt_title=title, alt_tags=tags,
                alt_comments=comments)
        id, href = self.oeb.manifest.generate('calibre_jacket', 'jacket.xhtml')

        item = self.oeb.manifest.add(id, href, guess_type(href)[0], data=root)
        self.oeb.spine.insert(0, item, True)
        self.oeb.inserted_metadata_jacket = item

    def remove_existing_jacket(self):
        for x in self.oeb.spine[:4]:
            if XPath(JACKET_XPATH)(x.data):
                self.remove_images(x, limit=sys.maxint)
                self.oeb.manifest.remove(x)
                self.log('Removed existing jacket')
                break

    def __call__(self, oeb, opts, metadata):
        '''
        Add metadata in jacket.xhtml if specified in opts
        If not specified, remove previous jacket instance
        '''
        self.oeb, self.opts, self.log = oeb, opts, oeb.log
        self.remove_existing_jacket()
        if opts.remove_first_image:
            self.remove_first_image()
        if opts.insert_metadata:
            self.insert_metadata(metadata)

# Render Jacket {{{

def get_rating(rating, rchar, e_rchar):
    ans = ''
    try:
        num = float(rating)/2
    except:
        return ans
    num = max(0, num)
    num = min(num, 5)
    if num < 1:
        return ans

    ans = ("%s%s") % (rchar * int(num), e_rchar * (5 - int(num)))
    return ans

def render_jacket(mi, output_profile,
        alt_title=_('Unknown'), alt_tags=[], alt_comments='',
        alt_publisher=('')):
    css = P('jacket/stylesheet.css', data=True).decode('utf-8')

    try:
        title_str = mi.title if mi.title else alt_title
    except:
        title_str = _('Unknown')
    title = '<span class="title">%s</span>' % (escape(title_str))

    series = escape(mi.series if mi.series else '')
    if mi.series and mi.series_index is not None:
        series += escape(' [%s]'%mi.format_series_index())
    if not mi.series:
        series = ''

    try:
        publisher = mi.publisher if mi.publisher else alt_publisher
    except:
        publisher = ''

    try:
        if is_date_undefined(mi.pubdate):
            pubdate = ''
        else:
            pubdate = strftime(u'%Y', mi.pubdate.timetuple())
    except:
        pubdate = ''

    rating = get_rating(mi.rating, output_profile.ratings_char, output_profile.empty_ratings_char)

    tags = mi.tags if mi.tags else alt_tags
    if tags:
        tags = output_profile.tags_to_string(tags)
    else:
        tags = ''

    comments = mi.comments if mi.comments else alt_comments
    comments = comments.strip()
    orig_comments = comments
    if comments:
        comments = comments_to_html(comments)

    try:
        author = mi.format_authors()
    except:
        author = ''

    def generate_html(comments):
        args = dict(xmlns=XHTML_NS,
                    title_str=title_str,
                    css=css,
                    title=title,
                    author=author,
                    publisher=publisher,
                    pubdate_label=_('Published'), pubdate=pubdate,
                    series_label=_('Series'), series=series,
                    rating_label=_('Rating'), rating=rating,
                    tags_label=_('Tags'), tags=tags,
                    comments=comments,
                    footer=''
                    )
        for key in mi.custom_field_keys():
            try:
                display_name, val = mi.format_field_extended(key)[:2]
                key = key.replace('#', '_')
                args[key] = escape(val)
                args[key+'_label'] = escape(display_name)
            except:
                pass

        if False:
            print("Custom column values available in jacket template:")
            for key in args.keys():
                if key.startswith('_') and not key.endswith('_label'):
                    print(" %s: %s" % ('#' + key[1:], args[key]))

        # Used in the comment describing use of custom columns in templates
        # Don't change this unless you also change it in template.xhtml
        args['_genre_label'] = args.get('_genre_label', '{_genre_label}')
        args['_genre'] = args.get('_genre', '{_genre}')

        generated_html = P('jacket/template.xhtml',
                data=True).decode('utf-8').format(**args)

        # Post-process the generated html to strip out empty header items

        soup = BeautifulSoup(generated_html)
        if not series:
            series_tag = soup.find(attrs={'class':'cbj_series'})
            if series_tag is not None:
                series_tag.extract()
        if not rating:
            rating_tag = soup.find(attrs={'class':'cbj_rating'})
            if rating_tag is not None:
                rating_tag.extract()
        if not tags:
            tags_tag = soup.find(attrs={'class':'cbj_tags'})
            if tags_tag is not None:
                tags_tag.extract()
        if not pubdate:
            pubdate_tag = soup.find(attrs={'class':'cbj_pubdata'})
            if pubdate_tag is not None:
                pubdate_tag.extract()
        if output_profile.short_name != 'kindle':
            hr_tag = soup.find('hr', attrs={'class':'cbj_kindle_banner_hr'})
            if hr_tag is not None:
                hr_tag.extract()

        return strip_encoding_declarations(
                soup.renderContents('utf-8').decode('utf-8'))

    from calibre.ebooks.oeb.base import RECOVER_PARSER

    try:
        root = etree.fromstring(generate_html(comments), parser=RECOVER_PARSER)
    except:
        try:
            root = etree.fromstring(generate_html(escape(orig_comments)),
                parser=RECOVER_PARSER)
        except:
            root = etree.fromstring(generate_html(''),
                parser=RECOVER_PARSER)
    return root

# }}}

def linearize_jacket(oeb):
    for x in oeb.spine[:4]:
        if XPath(JACKET_XPATH)(x.data):
            for e in XPath('//h:table|//h:tr|//h:th')(x.data):
                e.tag = XHTML('div')
            for e in XPath('//h:td')(x.data):
                e.tag = XHTML('span')
            break

