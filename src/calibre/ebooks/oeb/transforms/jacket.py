#!/usr/bin/env python


__license__   = 'GPL v3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os
import re
import sys
from contextlib import suppress
from string import Formatter
from xml.sax.saxutils import escape

from calibre import guess_type, prepare_string_for_xml
from calibre.constants import iswindows
from calibre.ebooks.chardet import strip_encoding_declarations
from calibre.ebooks.metadata import fmt_sidx, rating_to_stars
from calibre.ebooks.metadata.sources.identify import urls_from_identifiers
from calibre.ebooks.oeb.base import (
    XHTML, XHTML_NS, XPath, urldefrag, urlnormalize, xml2text
)
from calibre.library.comments import comments_to_html, markdown
from calibre.utils.config import tweaks
from calibre.utils.date import as_local_time, format_date, is_date_undefined
from calibre.utils.icu import sort_key

JACKET_XPATH = '//h:meta[@name="calibre-content" and @content="jacket"]'


class SafeFormatter(Formatter):

    def get_value(self, *args, **kwargs):
        try:
            return Formatter.get_value(self, *args, **kwargs)
        except KeyError:
            return ''


class Base:

    def remove_images(self, item, limit=1):
        path = XPath('//h:img[@src]')
        removed = 0
        for img in path(item.data):
            if removed >= limit:
                break
            href  = item.abshref(img.get('src'))
            image = self.oeb.manifest.hrefs.get(href)
            if image is None:
                href = urlnormalize(href)
                image = self.oeb.manifest.hrefs.get(href)
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
            tags = list(map(str, self.oeb.metadata.subject))
        except Exception:
            tags = []

        try:
            comments = str(self.oeb.metadata.description[0])
        except:
            comments = ''

        try:
            title = str(self.oeb.metadata.title[0])
        except:
            title = _('Unknown')

        try:
            authors = list(map(str, self.oeb.metadata.creator))
        except:
            authors = [_('Unknown')]

        root = render_jacket(mi, self.opts.output_profile,
                alt_title=title, alt_tags=tags, alt_authors=authors,
                alt_comments=comments, rescale_fonts=True, smarten_punctuation=self.opts.smarten_punctuation)
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
                self.remove_images(x, limit=sys.maxsize)
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


class Series(str):

    def __new__(self, series, series_index):
        if series and series_index is not None:
            roman = _('{1} of <em>{0}</em>').format(
                escape(series), escape(fmt_sidx(series_index, use_roman=True)))
            combined = _('{1} of <em>{0}</em>').format(
                escape(series), escape(fmt_sidx(series_index, use_roman=False)))
        else:
            combined = roman = escape(series or '')
        s = str.__new__(self, combined)
        s.roman = roman
        s.name = escape(series or '')
        s.number = escape(fmt_sidx(series_index or 1.0, use_roman=False))
        s.roman_number = escape(fmt_sidx(series_index or 1.0, use_roman=True))
        return s


class Timestamp:

    def __init__(self, dt, render_template):
        self.dt = as_local_time(dt)
        self.is_date_undefined = dt is None or is_date_undefined(dt)
        self.default_render = '' if self.is_date_undefined else escape(format_date(self.dt, render_template))

    def __repr__(self):
        return self.default_render
    __str__ = __repr__

    def __bool__(self):
        return bool(self.default_render)

    def __getattr__(self, template):
        with suppress(Exception):
            if not self.is_date_undefined:
                return escape(format_date(self.dt, template))
        return ''


class Tags(str):

    def __new__(self, tags, output_profile):
        tags = [escape(x) for x in tags or ()]
        t = str.__new__(self, ', '.join(tags))
        t.alphabetical = ', '.join(sorted(tags, key=sort_key))
        t.tags_list = tags
        return t


def postprocess_jacket(root, output_profile, has_data):
    # Post-process the generated html to strip out empty header items

    def extract(tag):
        parent = tag.getparent()
        idx = parent.index(tag)
        parent.remove(tag)
        if tag.tail:
            if idx == 0:
                parent.text = (parent.text or '') + tag.tail
            else:
                if idx >= len(parent):
                    idx = -1
                parent[-1].tail = (parent[-1].tail or '') + tag.tail

    def extract_class(cls):
        for tag in root.xpath('//*[@class="_"]'.replace('_', cls)):
            extract(tag)

    for key in 'series rating tags'.split():
        if not has_data[key]:
            extract_class('cbj_' + key)
    if not has_data['pubdate']:
        extract_class('cbj_pubdata')
    if output_profile.short_name != 'kindle':
        extract_class('cbj_kindle_banner_hr')


class Attributes:

    def __getattr__(self, name):
        return 'none'


class Identifiers:

    def __init__(self, idents):
        self.identifiers = idents or {}
        self.display = Attributes()
        for k in self.identifiers:
            setattr(self.display, k, 'initial')
        links = []
        for x in urls_from_identifiers(self.identifiers):
            name, id_typ, id_val, url = (prepare_string_for_xml(e, True) for e in x)
            links.append(f'<a href="{url}" title="{id_typ}:{id_val}">{name}</a>')
        self.links = ', '.join(links)
        self.display.links = 'initial' if self.links else 'none'

    def __getattr__(self, name):
        return self.identifiers.get(name, '')


def render_jacket(mi, output_profile,
        alt_title=_('Unknown'), alt_tags=[], alt_comments='',
        alt_publisher='', rescale_fonts=False, alt_authors=None, smarten_punctuation=False):
    css = P('jacket/stylesheet.css', data=True).decode('utf-8')
    template = P('jacket/template.xhtml', data=True).decode('utf-8')

    template = re.sub(r'<!--.*?-->', '', template, flags=re.DOTALL)
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)

    try:
        title_str = alt_title if mi.is_null('title') else mi.title
    except:
        title_str = _('Unknown')
    title_str = escape(title_str)
    title = '<span class="title">%s</span>' % title_str

    series = Series(mi.series, mi.series_index)
    try:
        publisher = mi.publisher if not mi.is_null('publisher') else alt_publisher
    except:
        publisher = ''
    publisher = escape(publisher)

    pubdate = timestamp = None
    with suppress(Exception):
        if not is_date_undefined(mi.pubdate):
            pubdate = mi.pubdate
    with suppress(Exception):
        if not is_date_undefined(mi.timestamp):
            timestamp = mi.timestamp

    rating = get_rating(mi.rating, output_profile.ratings_char, output_profile.empty_ratings_char)

    tags = Tags((mi.tags if mi.tags else alt_tags), output_profile)

    comments = mi.comments if mi.comments else alt_comments
    comments = comments.strip()
    if comments:
        comments = comments_to_html(comments)

    orig = mi.authors
    if mi.is_null('authors'):
        mi.authors = list(alt_authors or (_('Unknown'),))
    try:
        author = mi.format_authors()
    except:
        author = ''
    mi.authors = orig
    author = escape(author)
    has_data = {}

    def generate_html(comments):
        display = Attributes()
        args = dict(xmlns=XHTML_NS,
            title_str=title_str,
            identifiers=Identifiers(mi.identifiers),
            css=css,
            title=title,
            author=author,
            publisher=publisher, publisher_label=_('Publisher'),
            pubdate_label=_('Published'), pubdate=Timestamp(pubdate, tweaks['gui_pubdate_display_format']),
            series_label=ngettext('Series', 'Series', 1), series=series,
            rating_label=_('Rating'), rating=rating,
            tags_label=_('Tags'), tags=tags,
            timestamp=Timestamp(timestamp, tweaks['gui_timestamp_display_format']), timestamp_label=_('Date'),
            comments=comments,
            footer='',
            display=display,
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
                elif dt == 'datetime':
                    args[dkey] = Timestamp(mi.get(key), m.get('display', {}).get('date_format','dd MMM yyyy'))
                elif dt == 'comments':
                    val = val or ''
                    ctype = m.get('display', {}).get('interpret_as') or 'html'
                    if ctype == 'long-text':
                        val = '<pre style="white-space:pre-wrap">%s</pre>' % escape(val)
                    elif ctype == 'short-text':
                        val = '<span>%s</span>' % escape(val)
                    elif ctype == 'markdown':
                        val = markdown(val)
                    else:
                        val = comments_to_html(val)
                    args[dkey] = val
                else:
                    args[dkey] = escape(val)
                args[dkey+'_label'] = escape(display_name)
                setattr(display, dkey, 'none' if mi.is_null(key) else 'initial')
            except Exception:
                # if the val (custom column contents) is None, don't add to args
                pass

        if False:
            print("Custom column values available in jacket template:")
            for key in args.keys():
                if key.startswith('_') and not key.endswith('_label'):
                    print(" {}: {}".format('#' + key[1:], args[key]))

        # Used in the comment describing use of custom columns in templates
        # Don't change this unless you also change it in template.xhtml
        args['_genre_label'] = args.get('_genre_label', '{_genre_label}')
        args['_genre'] = args.get('_genre', '{_genre}')
        has_data['series'] = bool(series)
        has_data['tags'] = bool(tags)
        has_data['rating'] = bool(rating)
        has_data['pubdate'] = bool(pubdate)
        has_data['timestamp'] = bool(timestamp)
        has_data['publisher'] = bool(publisher)
        for k, v in has_data.items():
            setattr(display, k, 'initial' if v else 'none')
        display.title = 'initial'
        if mi.identifiers:
            display.identifiers = 'initial'

        formatter = SafeFormatter()
        generated_html = formatter.format(template, **args)

        return strip_encoding_declarations(generated_html)

    from calibre.ebooks.oeb.polish.parsing import parse
    raw = generate_html(comments)
    if smarten_punctuation:
        from calibre.ebooks.conversion.preprocess import smarten_punctuation as sp
        raw = sp(raw)
    root = parse(raw, line_numbers=False, force_html5_parse=True)

    if rescale_fonts:
        # We ensure that the conversion pipeline will set the font sizes for
        # text in the jacket to the same size as the font sizes for the rest of
        # the text in the book. That means that as long as the jacket uses
        # relative font sizes (em or %), the post conversion font size will be
        # the same as for text in the main book. So text with size x em will
        # be rescaled to the same value in both the jacket and the main content.
        #
        # We cannot use data-calibre-rescale 100 on the body tag as that will just
        # give the body tag a font size of 1em, which is useless.
        for body in root.xpath('//*[local-name()="body"]'):
            fw = body.makeelement(XHTML('div'))
            fw.set('data-calibre-rescale', '100')
            for child in body:
                fw.append(child)
            body.append(fw)
    postprocess_jacket(root, output_profile, has_data)
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
