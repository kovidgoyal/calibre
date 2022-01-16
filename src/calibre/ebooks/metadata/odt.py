#!/usr/bin/env python
#
# Copyright (C) 2006 Søren Roug, European Environment Agency
#
# This is free software.  You may redistribute it under the terms
# of the Apache license and the GNU General Public License Version
# 2 or at your option any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public
# License along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301  USA
#
# Contributor(s):
#


import io
import json
import os
import re

from lxml.etree import fromstring, tostring

from calibre.ebooks.metadata import (
    MetaInformation, authors_to_string, check_isbn, string_to_authors
)
from calibre.utils.date import isoformat, parse_date
from calibre.utils.imghdr import identify
from calibre.utils.localization import canonicalize_lang, lang_as_iso639_1
from calibre.utils.zipfile import ZipFile, safe_replace
from odf.draw import Frame as odFrame, Image as odImage
from odf.namespaces import DCNS, METANS, OFFICENS
from odf.opendocument import load as odLoad
from polyglot.builtins import as_unicode

fields = {
    'title':            (DCNS, 'title'),
    'description':      (DCNS, 'description'),
    'subject':          (DCNS, 'subject'),
    'creator':          (DCNS, 'creator'),
    'date':             (DCNS, 'date'),
    'language':         (DCNS, 'language'),
    'generator':        (METANS, 'generator'),
    'initial-creator':  (METANS, 'initial-creator'),
    'keyword':          (METANS, 'keyword'),
    'keywords':         (METANS, 'keywords'),
    'editing-duration': (METANS, 'editing-duration'),
    'editing-cycles':   (METANS, 'editing-cycles'),
    'printed-by':       (METANS, 'printed-by'),
    'print-date':       (METANS, 'print-date'),
    'creation-date':    (METANS, 'creation-date'),
    'user-defined':     (METANS, 'user-defined'),
    # 'template':         (METANS, 'template'),
}


def uniq(vals):
    ''' Remove all duplicates from vals, while preserving order.  '''
    vals = vals or ()
    seen = set()
    seen_add = seen.add
    return list(x for x in vals if x not in seen and not seen_add(x))


def get_metadata(stream, extract_cover=True):
    whitespace = re.compile(r'\s+')

    def normalize(s):
        return whitespace.sub(' ', s).strip()

    with ZipFile(stream) as zf:
        meta = zf.read('meta.xml')
        root = fromstring(meta)

        def find(field):
            ns, tag = fields[field]
            ans = root.xpath(f'//ns0:{tag}', namespaces={'ns0': ns})
            if ans:
                return normalize(tostring(ans[0], method='text', encoding='unicode', with_tail=False)).strip()

        def find_all(field):
            ns, tag = fields[field]
            for x in root.xpath(f'//ns0:{tag}', namespaces={'ns0': ns}):
                yield normalize(tostring(x, method='text', encoding='unicode', with_tail=False)).strip()

        mi = MetaInformation(None, [])
        title = find('title')
        if title:
            mi.title = title
        creator = find('initial-creator') or find('creator')
        if creator:
            mi.authors = string_to_authors(creator)
        desc = find('description')
        if desc:
            mi.comments = desc
        lang = find('language')
        if lang and canonicalize_lang(lang):
            mi.languages = [canonicalize_lang(lang)]
        keywords = []
        for q in ('keyword', 'keywords'):
            for kw in find_all(q):
                keywords += [x.strip() for x in kw.split(',') if x.strip()]
        mi.tags = uniq(keywords)
        data = {}
        for tag in root.xpath('//ns0:user-defined', namespaces={'ns0': fields['user-defined'][0]}):
            name = (tag.get('{%s}name' % METANS) or '').lower()
            vtype = tag.get('{%s}value-type' % METANS) or 'string'
            val = tag.text
            if name and val:
                if vtype == 'boolean':
                    val = val == 'true'
                data[name] = val
        opfmeta = False  # we need this later for the cover
        opfnocover = False
        if data.get('opf.metadata'):
            # custom metadata contains OPF information
            opfmeta = True
            if data.get('opf.titlesort', ''):
                mi.title_sort = data['opf.titlesort']
            if data.get('opf.authors', ''):
                mi.authors = string_to_authors(data['opf.authors'])
            if data.get('opf.authorsort', ''):
                mi.author_sort = data['opf.authorsort']
            if data.get('opf.isbn', ''):
                isbn = check_isbn(data['opf.isbn'])
                if isbn is not None:
                    mi.isbn = isbn
            if data.get('opf.publisher', ''):
                mi.publisher = data['opf.publisher']
            if data.get('opf.pubdate', ''):
                mi.pubdate = parse_date(data['opf.pubdate'], assume_utc=True)
            if data.get('opf.identifiers'):
                try:
                    mi.identifiers = json.loads(data['opf.identifiers'])
                except Exception:
                    pass
            if data.get('opf.rating'):
                try:
                    mi.rating = max(0, min(float(data['opf.rating']), 10))
                except Exception:
                    pass
            if data.get('opf.series', ''):
                mi.series = data['opf.series']
                if data.get('opf.seriesindex', ''):
                    try:
                        mi.series_index = float(data['opf.seriesindex'])
                    except Exception:
                        mi.series_index = 1.0
            if data.get('opf.language', ''):
                cl = canonicalize_lang(data['opf.language'])
                if cl:
                    mi.languages = [cl]
            opfnocover = data.get('opf.nocover', False)
        if not opfnocover:
            try:
                read_cover(stream, zf, mi, opfmeta, extract_cover)
            except Exception:
                pass  # Do not let an error reading the cover prevent reading other data

    return mi


def set_metadata(stream, mi):

    with ZipFile(stream) as zf:
        raw = _set_metadata(zf.open('meta.xml').read(), mi)
        # print(raw.decode('utf-8'))

    stream.seek(os.SEEK_SET)
    safe_replace(stream, "meta.xml", io.BytesIO(raw))


def _set_metadata(raw, mi):
    root = fromstring(raw)
    namespaces = {'office': OFFICENS, 'meta': METANS, 'dc': DCNS}
    nsrmap = {v: k for k, v in namespaces.items()}

    def xpath(expr, parent=root):
        return parent.xpath(expr, namespaces=namespaces)

    def remove(*tag_names):
        for tag_name in tag_names:
            ns = fields[tag_name][0]
            tag_name = f'{nsrmap[ns]}:{tag_name}'
            for x in xpath('descendant::' + tag_name, meta):
                x.getparent().remove(x)

    def add(tag, val=None):
        ans = meta.makeelement('{%s}%s' % fields[tag])
        ans.text = val
        meta.append(ans)
        return ans

    def remove_user_metadata(*names):
        for x in xpath('//meta:user-defined'):
            q = (x.get('{%s}name' % METANS) or '').lower()
            if q in names:
                x.getparent().remove(x)

    def add_um(name, val, vtype='string'):
        ans = add('user-defined', val)
        ans.set('{%s}value-type' % METANS, vtype)
        ans.set('{%s}name' % METANS, name)

    def add_user_metadata(name, val):
        if not hasattr(add_user_metadata, 'sentinel_added'):
            add_user_metadata.sentinel_added = True
            remove_user_metadata('opf.metadata')
            add_um('opf.metadata', 'true', 'boolean')
        val_type = 'string'
        if hasattr(val, 'strftime'):
            val = isoformat(val, as_utc=True).split('T')[0]
            val_type = 'date'
        add_um(name, val, val_type)

    meta = xpath('//office:meta')[0]

    if not mi.is_null('title'):
        remove('title')
        add('title', mi.title)
        if not mi.is_null('title_sort'):
            remove_user_metadata('opf.titlesort')
            add_user_metadata('opf.titlesort', mi.title_sort)
    if not mi.is_null('authors'):
        remove('initial-creator', 'creator')
        val = authors_to_string(mi.authors)
        add('initial-creator', val), add('creator', val)
        remove_user_metadata('opf.authors')
        add_user_metadata('opf.authors', val)
        if not mi.is_null('author_sort'):
            remove_user_metadata('opf.authorsort')
            add_user_metadata('opf.authorsort', mi.author_sort)
    if not mi.is_null('comments'):
        remove('description')
        add('description', mi.comments)
    if not mi.is_null('tags'):
        remove('keyword')
        add('keyword', ', '.join(mi.tags))
    if not mi.is_null('languages'):
        lang = lang_as_iso639_1(mi.languages[0])
        if lang:
            remove('language')
            add('language', lang)
    if not mi.is_null('pubdate'):
        remove_user_metadata('opf.pubdate')
        add_user_metadata('opf.pubdate', mi.pubdate)
    if not mi.is_null('publisher'):
        remove_user_metadata('opf.publisher')
        add_user_metadata('opf.publisher', mi.publisher)
    if not mi.is_null('series'):
        remove_user_metadata('opf.series', 'opf.seriesindex')
        add_user_metadata('opf.series', mi.series)
        add_user_metadata('opf.seriesindex', f'{mi.series_index}')
    if not mi.is_null('identifiers'):
        remove_user_metadata('opf.identifiers')
        add_user_metadata('opf.identifiers', as_unicode(json.dumps(mi.identifiers)))
    if not mi.is_null('rating'):
        remove_user_metadata('opf.rating')
        add_user_metadata('opf.rating', '%.2g' % mi.rating)

    return tostring(root, encoding='utf-8', pretty_print=True)


def read_cover(stream, zin, mi, opfmeta, extract_cover):
    # search for an draw:image in a draw:frame with the name 'opf.cover'
    # if opf.metadata prop is false, just use the first image that
    # has a proper size (borrowed from docx)
    otext = odLoad(stream)
    cover_href = None
    cover_data = None
    cover_frame = None
    imgnum = 0
    for frm in otext.topnode.getElementsByType(odFrame):
        img = frm.getElementsByType(odImage)
        if len(img) == 0:
            continue
        i_href = img[0].getAttribute('href')
        try:
            raw = zin.read(i_href)
        except KeyError:
            continue
        try:
            fmt, width, height = identify(raw)
        except Exception:
            continue
        imgnum += 1
        if opfmeta and frm.getAttribute('name').lower() == 'opf.cover':
            cover_href = i_href
            cover_data = (fmt, raw)
            cover_frame = frm.getAttribute('name')  # could have upper case
            break
        if cover_href is None and imgnum == 1 and 0.8 <= height/width <= 1.8 and height*width >= 12000:
            # Pick the first image as the cover if it is of a suitable size
            cover_href = i_href
            cover_data = (fmt, raw)
            if not opfmeta:
                break

    if cover_href is not None:
        mi.cover = cover_href
        mi.odf_cover_frame = cover_frame
        if extract_cover:
            if not cover_data:
                raw = zin.read(cover_href)
                try:
                    fmt = identify(raw)[0]
                except Exception:
                    pass
                else:
                    cover_data = (fmt, raw)
            mi.cover_data = cover_data
