#!/usr/bin/env python
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os
from functools import partial
from binascii import hexlify

from calibre import prepare_string_for_xml, force_unicode
from calibre.ebooks.metadata import fmt_sidx
from calibre.ebooks.metadata.sources.identify import urls_from_identifiers
from calibre.constants import filesystem_encoding
from calibre.library.comments import comments_to_html
from calibre.utils.icu import sort_key
from calibre.utils.formatter import EvalFormatter
from calibre.utils.date import is_date_undefined
from calibre.utils.localization import calibre_langcode_to_name

default_sort = ('title', 'title_sort', 'authors', 'author_sort', 'series', 'rating', 'pubdate', 'tags', 'publisher', 'identifiers')

def field_sort(mi, name):
    try:
        title = mi.metadata_for_field(name)['name']
    except:
        title = 'zzz'
    return {x:(i, None) for i, x in enumerate(default_sort)}.get(name, (10000, sort_key(title)))

def displayable_field_keys(mi):
    for k in mi.all_field_keys():
        try:
            m = mi.metadata_for_field(k)
        except:
            continue
        if (
                m is not None and m['kind'] == 'field' and m['datatype'] is not None and
                k not in ('au_map', 'marked', 'ondevice', 'cover', 'series_sort') and
                not k.endswith('_index')
        ):
            yield k

def get_field_list(mi):
    for field in sorted(displayable_field_keys(mi), key=partial(field_sort, mi)):
        yield field, True

def search_href(search_term, value):
    search = '%s:"=%s"' % (search_term, value.replace('"', '\\"'))
    return prepare_string_for_xml('search:' + hexlify(search.encode('utf-8')), True)

def mi_to_html(mi, field_list=None, default_author_link=None, use_roman_numbers=True, rating_font='Liberation Serif'):
    if field_list is None:
        field_list = get_field_list(mi)
    ans = []
    comment_fields = []
    isdevice = not hasattr(mi, 'id')
    row = u'<td class="title">%s</td><td class="value">%s</td>'
    p = prepare_string_for_xml
    a = partial(prepare_string_for_xml, attribute=True)

    for field in (field for field, display in field_list if display):
        try:
            metadata = mi.metadata_for_field(field)
        except:
            continue
        if not metadata:
            continue
        if field == 'sort':
            field = 'title_sort'
        if metadata['datatype'] == 'bool':
            isnull = mi.get(field) is None
        else:
            isnull = mi.is_null(field)
        if isnull:
            continue
        name = metadata['name']
        if not name:
            name = field
        name += ':'
        if metadata['datatype'] == 'comments' or field == 'comments':
            val = getattr(mi, field)
            if val:
                val = force_unicode(val)
                comment_fields.append(comments_to_html(val))
        elif metadata['datatype'] == 'rating':
            val = getattr(mi, field)
            if val:
                val = val/2.0
                ans.append((field,
                    u'<td class="title">%s</td><td class="rating value" '
                    'style=\'font-family:"%s"\'>%s</td>'%(
                        name, rating_font, u'\u2605'*int(val))))
        elif metadata['datatype'] == 'composite' and \
                            metadata['display'].get('contains_html', False):
            val = getattr(mi, field)
            if val:
                val = force_unicode(val)
                ans.append((field,
                    row % (name, comments_to_html(val))))
        elif field == 'path':
            if mi.path:
                path = force_unicode(mi.path, filesystem_encoding)
                scheme = u'devpath' if isdevice else u'path'
                url = prepare_string_for_xml(path if isdevice else
                        unicode(mi.id), True)
                pathstr = _('Click to open')
                extra = ''
                if isdevice:
                    durl = url
                    if durl.startswith('mtp:::'):
                        durl = ':::'.join((durl.split(':::'))[2:])
                    extra = '<br><span style="font-size:smaller">%s</span>'%(
                            prepare_string_for_xml(durl))
                link = u'<a href="%s:%s" title="%s">%s</a>%s' % (scheme, url,
                        prepare_string_for_xml(path, True), pathstr, extra)
                ans.append((field, row % (name, link)))
        elif field == 'formats':
            if isdevice:
                continue
            path = ''
            if mi.path:
                h, t = os.path.split(mi.path)
                path = '/'.join((os.path.basename(h), t))
            data = ({
                'fmt':x, 'path':a(path or ''), 'fname':a(mi.format_files.get(x, '')),
                'ext':x.lower(), 'id':mi.id
            } for x in mi.formats)
            fmts = [u'<a title="{path}/{fname}.{ext}" href="format:{id}:{fmt}">{fmt}</a>'.format(**x) for x in data]
            ans.append((field, row % (name, u', '.join(fmts))))
        elif field == 'identifiers':
            urls = urls_from_identifiers(mi.identifiers)
            links = [u'<a href="%s" title="%s:%s">%s</a>' % (a(url), a(id_typ), a(id_val), p(namel))
                    for namel, id_typ, id_val, url in urls]
            links = u', '.join(links)
            if links:
                ans.append((field, row % (_('Ids')+':', links)))
        elif field == 'authors' and not isdevice:
            authors = []
            formatter = EvalFormatter()
            for aut in mi.authors:
                link = ''
                if mi.author_link_map[aut]:
                    link = mi.author_link_map[aut]
                elif default_author_link:
                    vals = {'author': aut.replace(' ', '+')}
                    try:
                        vals['author_sort'] =  mi.author_sort_map[aut].replace(' ', '+')
                    except:
                        vals['author_sort'] = aut.replace(' ', '+')
                    link = formatter.safe_format(
                            default_author_link, vals, '', vals)
                aut = p(aut)
                if link:
                    authors.append(u'<a calibre-data="authors" title="%s" href="%s">%s</a>'%(a(link), a(link), aut))
                else:
                    authors.append(aut)
            ans.append((field, row % (name, u' & '.join(authors))))
        elif field == 'languages':
            if not mi.languages:
                continue
            names = filter(None, map(calibre_langcode_to_name, mi.languages))
            ans.append((field, row % (name, u', '.join(names))))
        else:
            val = mi.format_field(field)[-1]
            if val is None:
                continue
            val = p(val)
            if metadata['datatype'] == 'series':
                sidx = mi.get(field+'_index')
                if sidx is None:
                    sidx = 1.0
                try:
                    st = metadata['search_terms'][0]
                except Exception:
                    st = field
                series = getattr(mi, field)
                val = _(
                    'Book %(sidx)s of <a href="%(href)s" title="%(tt)s">'
                    '<span class="%(cls)s">%(series)s</span></a>') % dict(
                        sidx=fmt_sidx(sidx, use_roman=use_roman_numbers), cls="series_name",
                        series=p(series), href=search_href(st, series),
                        tt=p(_('Click to see books in this series')))
            elif metadata['datatype'] == 'datetime':
                aval = getattr(mi, field)
                if is_date_undefined(aval):
                    continue
            elif metadata['datatype'] == 'text' and metadata['is_multiple']:
                try:
                    st = metadata['search_terms'][0]
                except Exception:
                    st = field
                links = ['<a href="%s" title="%s">%s</a>' % (
                    search_href(st, x), _('Click to see books with {0}: {1}').format(metadata['name'], x), x)
                         for x in mi.get(field)]
                val = metadata['is_multiple']['list_to_ui'].join(links)
            elif metadata['datatype'] == 'enumeration':
                try:
                    st = metadata['search_terms'][0]
                except Exception:
                    st = field
                val = '<a href="%s" title="%s">%s</a>' % (search_href(st, val), _('Click to see books with {0}: {1}').format(metadata['name'], val), val)

            ans.append((field, row % (name, val)))

    dc = getattr(mi, 'device_collections', [])
    if dc:
        dc = u', '.join(sorted(dc, key=sort_key))
        ans.append(('device_collections',
            row % (_('Collections')+':', dc)))

    def classname(field):
        try:
            dt = mi.metadata_for_field(field)['datatype']
        except:
            dt = 'text'
        return 'datatype_%s'%dt

    ans = [u'<tr id="%s" class="%s">%s</tr>'%(fieldl.replace('#', '_'),
        classname(fieldl), html) for fieldl, html in ans]
    # print '\n'.join(ans)
    return u'<table class="fields">%s</table>'%(u'\n'.join(ans)), comment_fields


