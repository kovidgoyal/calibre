#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import with_statement

__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import sys, os, re
from xml.sax.saxutils import escape
from string import Formatter

from lxml import etree

from calibre import guess_type, strftime
from calibre.constants import iswindows
from calibre.ebooks.BeautifulSoup import BeautifulSoup
from calibre.ebooks.oeb.base import XPath, XHTML_NS, XHTML, xml2text, urldefrag
from calibre.library.comments import comments_to_html
from calibre.utils.date import is_date_undefined, as_local_time
from calibre.utils.icu import sort_key
from calibre.ebooks.chardet import strip_encoding_declarations
from calibre.ebooks.metadata import fmt_sidx, rating_to_stars

JACKET_XPATH = '//h:meta[@name="calibre-content" and @content="jacket"]'


class SafeFormatter(Formatter):

    def get_value(self, *args, **kwargs):
        try:
            return Formatter.get_value(self, *args, **kwargs)
        except KeyError:
            return ''


class Base(object):

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
                self.oeb.guide.remove_by_href(href)
                img.getparent().remove(img)
                removed += 1
        return removed


class RemoveFirstImage(Base):

    def remove_first_image(self):
        deleted_item = None
        for item in self.oeb.spine:
            if XPath(JACKET_XPATH)(item.data):
                continue
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
        else:
            self.log.warn('Could not find first image to remove')
        if deleted_item is not None:
            for item in list(self.oeb.toc):
                href = urldefrag(item.href)[0]
                if href == deleted_item.href:
                    self.oeb.toc.remove(item)
            self.oeb.guide.remove_by_href(deleted_item.href)

    def __call__(self, oeb, opts, metadata):
        '''
        Add metadata in jacket.xhtml if specified in opts
        If not specified, remove previous jacket instance
        '''
        self.oeb, self.opts, self.log = oeb, opts, oeb.log
        if opts.remove_first_image:
            self.remove_first_image()


class Jacket(Base):
    '''
    Book jacket manipulation. Remove first image and insert comments at start of
    book.
    '''

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
                alt_comments=comments, rescale_fonts=True)
        id, href = self.oeb.manifest.generate('calibre_jacket', 'jacket.xhtml')

        jacket = self.oeb.manifest.add(id, href, guess_type(href)[0], data=root)
        self.oeb.spine.insert(0, jacket, True)
        self.oeb.inserted_metadata_jacket = jacket
        for img, path in referenced_images(root):
            self.oeb.log('Embedding referenced image %s into jacket' % path)
            ext = path.rpartition('.')[-1].lower()
            item_id, href = self.oeb.manifest.generate('jacket_image', 'jacket_img.'+ext)
            with open(path, 'rb') as f:
                item = self.oeb.manifest.add(item_id, href, guess_type(href)[0], data=f.read())
            item.unload_data_from_memory()
            img.set('src', jacket.relhref(item.href))

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


class Series(unicode):

    def __new__(self, series, series_index):
        if series and series_index is not None:
            roman = _('{1} of <em>{0}</em>').format(
                escape(series), escape(fmt_sidx(series_index, use_roman=True)))
            combined = _('{1} of <em>{0}</em>').format(
                escape(series), escape(fmt_sidx(series_index, use_roman=False)))
        else:
            combined = roman = escape(series or u'')
        s = unicode.__new__(self, combined)
        s.roman = roman
        s.name = escape(series or u'')
        s.number = escape(fmt_sidx(series_index or 1.0, use_roman=False))
        s.roman_number = escape(fmt_sidx(series_index or 1.0, use_roman=True))
        return s


class Tags(unicode):

    def __new__(self, tags, output_profile):
        tags = [escape(x) for x in tags or ()]
        t = unicode.__new__(self, ', '.join(tags))
        t.alphabetical = ', '.join(sorted(tags, key=sort_key))
        t.tags_list = tags
        return t


def render_jacket(mi, output_profile,
        alt_title=_('Unknown'), alt_tags=[], alt_comments='',
        alt_publisher=(''), rescale_fonts=False):
    css = P('jacket/stylesheet.css', data=True).decode('utf-8')
    template = P('jacket/template.xhtml', data=True).decode('utf-8')

    template = re.sub(r'<!--.*?-->', '', template, flags=re.DOTALL)
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)

    try:
        title_str = mi.title if mi.title else alt_title
    except:
        title_str = _('Unknown')
    title_str = escape(title_str)
    title = '<span class="title">%s</span>' % title_str

    series = Series(mi.series, mi.series_index)
    try:
        publisher = mi.publisher if mi.publisher else alt_publisher
    except:
        publisher = ''
    publisher = escape(publisher)

    try:
        if is_date_undefined(mi.pubdate):
            pubdate = ''
        else:
            dt = as_local_time(mi.pubdate)
            pubdate = strftime(u'%Y', dt.timetuple())
    except:
        pubdate = ''

    rating = get_rating(mi.rating, output_profile.ratings_char, output_profile.empty_ratings_char)

    tags = Tags((mi.tags if mi.tags else alt_tags), output_profile)

    comments = mi.comments if mi.comments else alt_comments
    comments = comments.strip()
    orig_comments = comments
    if comments:
        comments = comments_to_html(comments)

    try:
        author = mi.format_authors()
    except:
        author = ''
    author = escape(author)

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
                    footer='',
                    searchable_tags=' '.join(escape(t)+'ttt' for t in tags.tags_list),
                    )
        for key in mi.custom_field_keys():
            m = mi.get_user_metadata(key, False) or {}
            try:
                display_name, val = mi.format_field_extended(key)[:2]
                dkey = key.replace('#', '_')
                dt = m.get('datatype')
                if dt == 'series':
                    args[dkey] = Series(mi.get(key), mi.get(key + '_index'))
                elif dt == 'rating':
                    args[dkey] = rating_to_stars(mi.get(key), m.get('display', {}).get('allow_half_stars', False))
                else:
                    args[dkey] = escape(val)
                args[dkey+'_label'] = escape(display_name)
            except Exception:
                # if the val (custom column contents) is None, don't add to args
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

        formatter = SafeFormatter()
        generated_html = formatter.format(template, **args)

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
    if rescale_fonts:
        # We ensure that the conversion pipeline will set the font sizes for
        # text in the jacket to the same size as the font sizes for the rest of
        # the text in the book. That means that as long as the jacket uses
        # relative font sizes (em or %), the post conversion font size will be
        # the same as for text in the main book. So text with size x em will
        # be rescaled to the same value in both the jacket and the main content.
        #
        # We cannot use calibre_rescale_100 on the body tag as that will just
        # give the body tag a font size of 1em, which is useless.
        for body in root.xpath('//*[local-name()="body"]'):
            fw = body.makeelement(XHTML('div'))
            fw.set('class', 'calibre_rescale_100')
            for child in body:
                fw.append(child)
            body.append(fw)
    from calibre.ebooks.oeb.polish.pretty import pretty_html_tree
    pretty_html_tree(None, root)
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


def referenced_images(root):
    for img in XPath('//h:img[@src]')(root):
        src = img.get('src')
        if src.startswith('file://'):
            path = src[7:]
            if iswindows and path.startswith('/'):
                path = path[1:]
            if os.path.exists(path):
                yield img, path
