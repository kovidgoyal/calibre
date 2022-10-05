#!/usr/bin/env python


__license__ = 'GPL v3'
__copyright__ = '2014, Kovid Goyal <kovid at kovidgoyal.net>'

import os
from functools import partial

from calibre import prepare_string_for_xml, force_unicode
from calibre.ebooks.metadata import fmt_sidx, rating_to_stars
from calibre.ebooks.metadata.search_internet import name_for, url_for_author_search, url_for_book_search, qquote, DEFAULT_AUTHOR_SOURCE
from calibre.ebooks.metadata.sources.identify import urls_from_identifiers
from calibre.constants import filesystem_encoding
from calibre.library.comments import comments_to_html, markdown
from calibre.utils.icu import sort_key
from calibre.utils.formatter import EvalFormatter
from calibre.utils.date import is_date_undefined, format_date
from calibre.utils.localization import calibre_langcode_to_name
from calibre.utils.serialize import json_dumps
from polyglot.binary import as_hex_unicode

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
                m is not None and m.get('kind') == 'field' and m.get('datatype') is not None and
                k not in ('au_map', 'marked', 'ondevice', 'cover', 'series_sort', 'in_tag_browser') and
                not k.endswith('_index')
        ):
            yield k


def get_field_list(mi):
    for field in sorted(displayable_field_keys(mi), key=partial(field_sort, mi)):
        yield field, True


def action(main, **keys):
    keys['type'] = main
    return 'action:' + as_hex_unicode(json_dumps(keys))


def search_action(search_term, value, **k):
    return action('search', term=search_term, value=value, **k)


def search_action_with_data(search_term, value, book_id, field=None, **k):
    field = field or search_term
    return search_action(search_term, value, field=field, book_id=book_id, **k)


DEFAULT_AUTHOR_LINK = f'search-{DEFAULT_AUTHOR_SOURCE}'


def author_search_href(which, title=None, author=None):
    if which == 'calibre':
        return 'calibre', _('Search the calibre library for books by %s') % author
    search_type, key = 'author', which
    if which.endswith('-book'):
        key, search_type = which.rpartition('-')[::2]
    name = name_for(key)
    if name is None:
        search_type = 'author'
        return author_search_href(DEFAULT_AUTHOR_LINK.partition('-')[2], title=title, author=author)
    if search_type == 'author':
        tt = _('Search {0} for the author: {1}').format(name, author)
    else:
        tt = _('Search {0} for the book: {1} by the author {2}').format(name, title, author)
    func = url_for_book_search if search_type == 'book' else url_for_author_search
    return func(key, title=title, author=author), tt


def mi_to_html(
        mi,
        field_list=None, default_author_link=None, use_roman_numbers=True,
        rating_font='Liberation Serif', rtl=False, comments_heading_pos='hide',
        for_qt=False, vertical_fields=()
    ):
    if field_list is None:
        field_list = get_field_list(mi)
    ans = []
    comment_fields = []
    isdevice = not hasattr(mi, 'id')
    row = '<td class="title">%s</td><td class="value">%s</td>'
    p = prepare_string_for_xml
    a = partial(prepare_string_for_xml, attribute=True)
    book_id = getattr(mi, 'id', 0)

    for field in (field for field, display in field_list if display):
        try:
            metadata = mi.metadata_for_field(field)
        except:
            continue
        if not metadata:
            continue

        def value_list(sep, vals):
            if field in vertical_fields:
                return '<br/>'.join(vals)
            return sep.join(vals)

        if field == 'sort':
            field = 'title_sort'
        if metadata['is_custom'] and metadata['datatype'] in {'bool', 'int', 'float'}:
            isnull = mi.get(field) is None
        else:
            isnull = mi.is_null(field)
        if isnull:
            continue
        name = metadata['name']
        if not name:
            name = field
        name += ':'
        disp = metadata['display']
        if metadata['datatype'] == 'comments' or field == 'comments':
            val = getattr(mi, field)
            if val:
                ctype = disp.get('interpret_as') or 'html'
                val = force_unicode(val)
                if ctype == 'long-text':
                    val = '<pre style="white-space:pre-wrap">%s</pre>' % p(val)
                elif ctype == 'short-text':
                    val = '<span>%s</span>' % p(val)
                elif ctype == 'markdown':
                    val = markdown(val)
                else:
                    val = comments_to_html(val)
                heading_position = disp.get('heading_position', comments_heading_pos)
                if heading_position == 'side':
                    ans.append((field, row % (name, val)))
                else:
                    if heading_position == 'above':
                        val = f'<h3 class="comments-heading">{p(name)}</h3>{val}'
                    comment_fields.append('<div id="{}" class="comments">{}</div>'.format(field.replace('#', '_'), val))
        elif metadata['datatype'] == 'rating':
            val = getattr(mi, field)
            if val:
                star_string = rating_to_stars(val, disp.get('allow_half_stars', False))
                ans.append((field,
                    '<td class="title">%s</td><td class="rating value" '
                    'style=\'font-family:"%s"\'>%s</td>'%(
                        name, rating_font, star_string)))
        elif metadata['datatype'] == 'composite':
            val = getattr(mi, field)
            if val:
                val = force_unicode(val)
                if disp.get('contains_html', False):
                    ans.append((field, row % (name, comments_to_html(val))))
                else:
                    if not metadata['is_multiple']:
                        val = '<a href="{}" title="{}">{}</a>'.format(
                              search_action(field, val),
                              _('Click to see books with {0}: {1}').format(metadata['name'], a(val)), p(val))
                    else:
                        all_vals = [v.strip()
                            for v in val.split(metadata['is_multiple']['cache_to_list']) if v.strip()]
                        links = ['<a href="{}" title="{}">{}</a>'.format(
                            search_action(field, x), _('Click to see books with {0}: {1}').format(
                                     metadata['name'], a(x)), p(x)) for x in all_vals]
                        val = value_list(metadata['is_multiple']['list_to_ui'], links)
                    ans.append((field, row % (name, val)))
        elif field == 'path':
            if mi.path:
                path = force_unicode(mi.path, filesystem_encoding)
                scheme = 'devpath' if isdevice else 'path'
                loc = path if isdevice else book_id
                pathstr = _('Click to open')
                extra = ''
                if isdevice:
                    durl = path
                    if durl.startswith('mtp:::'):
                        durl = ':::'.join((durl.split(':::'))[2:])
                    extra = '<br><span style="font-size:smaller">%s</span>'%(
                            prepare_string_for_xml(durl))
                link = '<a href="{}" title="{}">{}</a>{}'.format(action(scheme, loc=loc),
                        prepare_string_for_xml(path, True), pathstr, extra)
                ans.append((field, row % (name, link)))
        elif field == 'formats':
            if isdevice:
                continue
            path = mi.path or ''
            bpath = ''
            if path:
                h, t = os.path.split(path)
                bpath = os.sep.join((os.path.basename(h), t))
            data = ({
                'fmt':x, 'path':a(path or ''), 'fname':a(mi.format_files.get(x, '')),
                'ext':x.lower(), 'id':book_id, 'bpath':bpath, 'sep':os.sep,
                'action':action('format', book_id=book_id, fmt=x, path=path or '', fname=mi.format_files.get(x, ''))
            } for x in mi.formats)
            fmts = ['<a title="{bpath}{sep}{fname}.{ext}" href="{action}">{fmt}</a>'.format(**x)
                    for x in data]
            ans.append((field, row % (name, value_list(', ', fmts))))
        elif field == 'identifiers':
            urls = urls_from_identifiers(mi.identifiers, sort_results=True)
            links = [
                '<a href="{}" title="{}:{}">{}</a>'.format(
                    action('identifier', url=url, name=namel, id_type=id_typ, value=id_val, field='identifiers', book_id=book_id),
                    a(id_typ), a(id_val), p(namel))
                for namel, id_typ, id_val, url in urls]
            links = value_list(', ', links)
            if links:
                ans.append((field, row % (_('Ids')+':', links)))
        elif field == 'authors':
            authors = []
            formatter = EvalFormatter()
            for aut in mi.authors:
                link = ''
                if mi.author_link_map.get(aut):
                    link = lt = mi.author_link_map[aut]
                elif default_author_link:
                    if default_author_link.startswith('search-'):
                        which_src = default_author_link.partition('-')[2]
                        link, lt = author_search_href(which_src, title=mi.title, author=aut)
                    else:
                        vals = {'author': qquote(aut), 'title': qquote(mi.title)}
                        try:
                            vals['author_sort'] =  qquote(mi.author_sort_map[aut])
                        except KeyError:
                            vals['author_sort'] = qquote(aut)
                        link = lt = formatter.safe_format(default_author_link, vals, '', vals)
                aut = p(aut)
                if link:
                    authors.append('<a title="%s" href="%s">%s</a>'%(a(lt), action('author', url=link, name=aut, title=lt), aut))
                else:
                    authors.append(aut)
            ans.append((field, row % (name, value_list(' & ', authors))))
        elif field == 'languages':
            if not mi.languages:
                continue
            names = filter(None, map(calibre_langcode_to_name, mi.languages))
            names = ['<a href="{}" title="{}">{}</a>'.format(search_action_with_data('languages', n, book_id), _(
                'Search calibre for books with the language: {}').format(n), n) for n in names]
            ans.append((field, row % (name, value_list(', ', names))))
        elif field == 'publisher':
            if not mi.publisher:
                continue
            val = '<a href="{}" title="{}">{}</a>'.format(
                search_action_with_data('publisher', mi.publisher, book_id),
                _('Click to see books with {0}: {1}').format(metadata['name'], a(mi.publisher)),
                p(mi.publisher))
            ans.append((field, row % (name, val)))
        elif field == 'title':
            # otherwise title gets metadata['datatype'] == 'text'
            # treatment below with a click to search link (which isn't
            # too bad), and a right-click 'Delete' option to delete
            # the title (which is bad).
            val = mi.format_field(field)[-1]
            ans.append((field, row % (name, val)))
        else:
            val = unescaped_val = mi.format_field(field)[-1]
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
                    '%(sidx)s of <a href="%(href)s" title="%(tt)s">'
                    '<span class="%(cls)s">%(series)s</span></a>') % dict(
                        sidx=fmt_sidx(sidx, use_roman=use_roman_numbers), cls="series_name",
                        series=p(series), href=search_action_with_data(st, series, book_id, field),
                        tt=p(_('Click to see books in this series')))
            elif metadata['datatype'] == 'datetime':
                aval = getattr(mi, field)
                if is_date_undefined(aval):
                    continue
                aval = format_date(aval, 'yyyy-MM-dd')
                key = field if field != 'timestamp' else 'date'
                if val == aval:
                    val = '<a href="{}" title="{}">{}</a>'.format(
                        search_action_with_data(key, str(aval), book_id, None, original_value=val), a(
                            _('Click to see books with {0}: {1}').format(metadata['name'] or field, val)), val)
                else:
                    val = '<a href="{}" title="{}">{}</a>'.format(
                        search_action_with_data(key, str(aval), book_id, None, original_value=val), a(
                            _('Click to see books with {0}: {1} (derived from {2})').format(
                                metadata['name'] or field, aval, val)), val)
            elif metadata['datatype'] == 'text' and metadata['is_multiple']:
                try:
                    st = metadata['search_terms'][0]
                except Exception:
                    st = field
                all_vals = mi.get(field)
                if not metadata.get('display', {}).get('is_names', False):
                    all_vals = sorted(all_vals, key=sort_key)
                links = ['<a href="{}" title="{}">{}</a>'.format(
                    search_action_with_data(st, x, book_id, field), _('Click to see books with {0}: {1}').format(
                        metadata['name'] or field, a(x)), p(x))
                         for x in all_vals]
                val = value_list(metadata['is_multiple']['list_to_ui'], links)
            elif metadata['datatype'] == 'text' or metadata['datatype'] == 'enumeration':
                # text/is_multiple handled above so no need to add the test to the if
                try:
                    st = metadata['search_terms'][0]
                except Exception:
                    st = field
                val = '<a href="{}" title="{}">{}</a>'.format(
                    search_action_with_data(st, unescaped_val, book_id, field), a(
                        _('Click to see books with {0}: {1}').format(metadata['name'] or field, val)), val)
            elif metadata['datatype'] == 'bool':
                val = '<a href="{}" title="{}">{}</a>'.format(
                    search_action_with_data(field, val, book_id, None), a(
                        _('Click to see books with {0}: {1}').format(metadata['name'] or field, val)), val)
            else:
                try:
                    aval = str(getattr(mi, field))
                    if not aval:
                        continue
                    if val == aval:
                        val = '<a href="{}" title="{}">{}</a>'.format(
                            search_action_with_data(field, str(aval), book_id, None, original_value=val), a(
                                _('Click to see books with {0}: {1}').format(metadata['name'] or field, val)), val)
                    else:
                        val = '<a href="{}" title="{}">{}</a>'.format(
                            search_action_with_data(field, str(aval), book_id, None, original_value=val), a(
                                _('Click to see books with {0}: {1} (derived from {2})').format(
                                    metadata['name'] or field, aval, val)), val)
                except Exception:
                    import traceback
                    traceback.print_exc()

            ans.append((field, row % (name, val)))

    dc = getattr(mi, 'device_collections', [])
    if dc:
        dc = ', '.join(sorted(dc, key=sort_key))
        ans.append(('device_collections',
            row % (_('Collections')+':', dc)))

    def classname(field):
        try:
            dt = mi.metadata_for_field(field)['datatype']
        except:
            dt = 'text'
        return 'datatype_%s'%dt

    ans = ['<tr id="%s" class="%s">%s</tr>'%(fieldl.replace('#', '_'),
        classname(fieldl), html) for fieldl, html in ans]
    # print '\n'.join(ans)
    direction = 'rtl' if rtl else 'ltr'
    rans = '<style>table.fields td { vertical-align:top}</style><table class="fields" style="direction: %s; ' % direction
    if not for_qt:
        # This causes wasted space at the edge of the table in Qt's rich text
        # engine, see https://bugs.launchpad.net/calibre/+bug/1881488
        margin = 'left' if rtl else 'right'
        rans += f'margin-{margin}: auto; '
    return '{}">{}</table>'.format(rans, '\n'.join(ans)), comment_fields
