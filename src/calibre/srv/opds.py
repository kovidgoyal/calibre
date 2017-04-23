#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import hashlib, binascii
from functools import partial
from collections import OrderedDict, namedtuple
from urllib import urlencode

from lxml import etree, html
from lxml.builder import ElementMaker

from calibre.constants import __appname__
from calibre.db.view import sanitize_sort_field_name
from calibre.ebooks.metadata import fmt_sidx, authors_to_string, rating_to_stars
from calibre.library.comments import comments_to_html
from calibre import guess_type, prepare_string_for_xml as xml
from calibre.utils.icu import sort_key
from calibre.utils.date import as_utc, timestampfromdt, is_date_undefined

from calibre.srv.errors import HTTPNotFound
from calibre.srv.routes import endpoint
from calibre.srv.utils import get_library_data, http_date, Offsets


def hexlify(x):
    if isinstance(x, unicode):
        x = x.encode('utf-8')
    return binascii.hexlify(x)


def unhexlify(x):
    return binascii.unhexlify(x).decode('utf-8')


def atom(ctx, rd, endpoint, output):
    rd.outheaders.set('Content-Type', 'application/atom+xml; charset=UTF-8', replace_all=True)
    if isinstance(output, bytes):
        ans = output  # Assume output is already UTF-8 XML
    elif isinstance(output, type('')):
        ans = output.encode('utf-8')
    else:
        from lxml import etree
        ans = etree.tostring(output, encoding='utf-8', xml_declaration=True, pretty_print=True)
    return ans


def format_tag_string(tags, sep, joinval=', '):
    if tags:
        tlist = tags if sep is None else [t.strip() for t in tags.split(sep)]
    else:
        tlist = []
    tlist.sort(key=sort_key)
    return joinval.join(tlist) if tlist else ''


# Vocabulary for building OPDS feeds {{{
DC_NS = 'http://purl.org/dc/terms/'
E = ElementMaker(namespace='http://www.w3.org/2005/Atom',
                 nsmap={
                     None   : 'http://www.w3.org/2005/Atom',
                     'dc'   : DC_NS,
                     'opds' : 'http://opds-spec.org/2010/catalog',
                     })


FEED    = E.feed
TITLE   = E.title
ID      = E.id
ICON    = E.icon


def UPDATED(dt, *args, **kwargs):
    return E.updated(as_utc(dt).strftime('%Y-%m-%dT%H:%M:%S+00:00'), *args, **kwargs)


LINK = partial(E.link, type='application/atom+xml')
NAVLINK = partial(E.link,
        type='application/atom+xml;type=feed;profile=opds-catalog')


def SEARCH_LINK(url_for, *args, **kwargs):
    kwargs['rel'] = 'search'
    kwargs['title'] = 'Search'
    kwargs['href'] = url_for('/opds/search', query='XXX').replace('XXX', '{searchTerms}')
    return LINK(*args, **kwargs)


def AUTHOR(name, uri=None):
    args = [E.name(name)]
    if uri is not None:
        args.append(E.uri(uri))
    return E.author(*args)


SUBTITLE = E.subtitle


def NAVCATALOG_ENTRY(url_for, updated, title, description, query):
    href = url_for('/opds/navcatalog', which=hexlify(query))
    id_ = 'calibre-navcatalog:'+str(hashlib.sha1(href).hexdigest())
    return E.entry(
        TITLE(title),
        ID(id_),
        UPDATED(updated),
        E.content(description, type='text'),
        NAVLINK(href=href)
    )


START_LINK = partial(NAVLINK, rel='start')
UP_LINK = partial(NAVLINK, rel='up')
FIRST_LINK = partial(NAVLINK, rel='first')
LAST_LINK  = partial(NAVLINK, rel='last')
NEXT_LINK  = partial(NAVLINK, rel='next', title='Next')
PREVIOUS_LINK  = partial(NAVLINK, rel='previous')


def html_to_lxml(raw):
    raw = u'<div>%s</div>'%raw
    root = html.fragment_fromstring(raw)
    root.set('xmlns', "http://www.w3.org/1999/xhtml")
    raw = etree.tostring(root, encoding=None)
    try:
        return etree.fromstring(raw)
    except:
        for x in root.iterdescendants():
            remove = []
            for attr in x.attrib:
                if ':' in attr:
                    remove.append(attr)
            for a in remove:
                del x.attrib[a]
        raw = etree.tostring(root, encoding=None)
        try:
            return etree.fromstring(raw)
        except:
            from calibre.ebooks.oeb.parse_utils import _html4_parse
            return _html4_parse(raw)


def CATALOG_ENTRY(item, item_kind, request_context, updated, catalog_name,
                  ignore_count=False, add_kind=False):
    id_ = 'calibre:category:'+item.name
    iid = 'N' + item.name
    if item.id is not None:
        iid = 'I' + str(item.id)
        iid += ':'+item_kind
    href = request_context.url_for('/opds/category', category=hexlify(catalog_name), which=hexlify(iid))
    link = NAVLINK(href=href)
    if ignore_count:
        count = ''
    else:
        count = ngettext('one book', '{} books', item.count).format(item.count)
    if item.use_sort_as_name:
        name = item.sort
    else:
        name = item.name
    return E.entry(
            TITLE(name + ('' if not add_kind else ' (%s)'%item_kind)),
            ID(id_),
            UPDATED(updated),
            E.content(count, type='text'),
            link
            )


def CATALOG_GROUP_ENTRY(item, category, request_context, updated):
    id_ = 'calibre:category-group:'+category+':'+item.text
    iid = item.text
    link = NAVLINK(href=request_context.url_for('/opds/categorygroup', category=hexlify(category), which=hexlify(iid)))
    return E.entry(
        TITLE(item.text),
        ID(id_),
        UPDATED(updated),
        E.content(ngettext('one item', '{} items', item.count).format(item.count), type='text'),
        link
    )


def ACQUISITION_ENTRY(book_id, updated, request_context):
    field_metadata = request_context.db.field_metadata
    mi = request_context.db.get_metadata(book_id)
    extra = []
    if mi.rating > 0:
        rating = rating_to_stars(mi.rating)
        extra.append(_('RATING: %s<br />')%rating)
    if mi.tags:
        extra.append(_('TAGS: %s<br />')%xml(format_tag_string(mi.tags, None)))
    if mi.series:
        extra.append(_('SERIES: %(series)s [%(sidx)s]<br />')%
                dict(series=xml(mi.series),
                sidx=fmt_sidx(float(mi.series_index))))
    for key in filter(request_context.ctx.is_field_displayable, field_metadata.ignorable_field_keys()):
        name, val = mi.format_field(key)
        if val:
            fm = field_metadata[key]
            datatype = fm['datatype']
            if datatype == 'text' and fm['is_multiple']:
                extra.append('%s: %s<br />'%
                             (xml(name),
                              xml(format_tag_string(val,
                                    fm['is_multiple']['ui_to_list'],
                                    joinval=fm['is_multiple']['list_to_ui']))))
            elif datatype == 'comments' or (fm['datatype'] == 'composite' and
                            fm['display'].get('contains_html', False)):
                extra.append('%s: %s<br />'%(xml(name), comments_to_html(unicode(val))))
            else:
                extra.append('%s: %s<br />'%(xml(name), xml(unicode(val))))
    if mi.comments:
        comments = comments_to_html(mi.comments)
        extra.append(comments)
    if extra:
        extra = html_to_lxml('\n'.join(extra))
    ans = E.entry(TITLE(mi.title), E.author(E.name(authors_to_string(mi.authors))), ID('urn:uuid:' + mi.uuid), UPDATED(mi.last_modified),
                  E.published(mi.timestamp.isoformat()))
    if mi.pubdate and not is_date_undefined(mi.pubdate):
        ans.append(ans.makeelement('{%s}date' % DC_NS))
        ans[-1].text = mi.pubdate.isoformat()
    if len(extra):
        ans.append(E.content(extra, type='xhtml'))
    get = partial(request_context.ctx.url_for, '/get', book_id=book_id, library_id=request_context.library_id)
    if mi.formats:
        fm = mi.format_metadata
        for fmt in mi.formats:
            fmt = fmt.lower()
            mt = guess_type('a.'+fmt)[0]
            if mt:
                link = E.link(type=mt, href=get(what=fmt), rel="http://opds-spec.org/acquisition")
                ffm = fm.get(fmt.upper())
                if ffm:
                    link.set('length', str(ffm['size']))
                    link.set('mtime', ffm['mtime'].isoformat())
                ans.append(link)
    ans.append(E.link(type='image/jpeg', href=get(what='cover'), rel="http://opds-spec.org/cover"))
    ans.append(E.link(type='image/jpeg', href=get(what='thumb'), rel="http://opds-spec.org/thumbnail"))

    return ans


# }}}

default_feed_title = __appname__ + ' ' + _('Library')


class Feed(object):  # {{{

    def __init__(self, id_, updated, request_context, subtitle=None,
            title=None,
            up_link=None, first_link=None, last_link=None,
            next_link=None, previous_link=None):
        self.base_href = request_context.url_for('/opds')

        self.root = \
            FEED(
                    TITLE(title or default_feed_title),
                    AUTHOR(__appname__, uri='https://calibre-ebook.com'),
                    ID(id_),
                    ICON(request_context.ctx.url_for('/favicon.png')),
                    UPDATED(updated),
                    SEARCH_LINK(request_context.url_for),
                    START_LINK(href=request_context.url_for('/opds'))
                )
        if up_link:
            self.root.append(UP_LINK(href=up_link))
        if first_link:
            self.root.append(FIRST_LINK(href=first_link))
        if last_link:
            self.root.append(LAST_LINK(href=last_link))
        if next_link:
            self.root.append(NEXT_LINK(href=next_link))
        if previous_link:
            self.root.append(PREVIOUS_LINK(href=previous_link))
        if subtitle:
            self.root.insert(1, SUBTITLE(subtitle))

    # }}}


class TopLevel(Feed):  # {{{

    def __init__(self,
            updated,  # datetime object in UTC
            categories,
            request_context,
            id_='urn:calibre:main',
            subtitle=_('Books in your library')
            ):
        Feed.__init__(self, id_, updated, request_context, subtitle=subtitle)

        subc = partial(NAVCATALOG_ENTRY, request_context.url_for, updated)
        subcatalogs = [subc(_('By ')+title,
            _('Books sorted by ') + desc, q) for title, desc, q in
            categories]
        for x in subcatalogs:
            self.root.append(x)
        for library_id, library_name in request_context.library_map.iteritems():
            id_ = 'calibre-library:' + library_id
            self.root.append(E.entry(
                TITLE(_('Library:') + ' ' + library_name),
                ID(id_),
                UPDATED(updated),
                E.content(_('Change calibre library to:') + ' ' + library_name, type='text'),
                NAVLINK(href=request_context.url_for('/opds', library_id=library_id))
            ))
# }}}


class NavFeed(Feed):

    def __init__(self, id_, updated, request_context, offsets, page_url, up_url, title=None):
        kwargs = {'up_link': up_url}
        kwargs['first_link'] = page_url
        kwargs['last_link']  = page_url+'&offset=%d'%offsets.last_offset
        if offsets.offset > 0:
            kwargs['previous_link'] = \
                page_url+'&offset=%d'%offsets.previous_offset
        if offsets.next_offset > -1:
            kwargs['next_link'] = \
                page_url+'&offset=%d'%offsets.next_offset
        if title:
            kwargs['title'] = title
        Feed.__init__(self, id_, updated, request_context, **kwargs)


class AcquisitionFeed(NavFeed):

    def __init__(self, id_, updated, request_context, items, offsets, page_url, up_url, title=None):
        NavFeed.__init__(self, id_, updated, request_context, offsets, page_url, up_url, title=title)
        for book_id in items:
            self.root.append(ACQUISITION_ENTRY(book_id, updated, request_context))


class CategoryFeed(NavFeed):

    def __init__(self, items, which, id_, updated, request_context, offsets, page_url, up_url, title=None):
        NavFeed.__init__(self, id_, updated, request_context, offsets, page_url, up_url, title=title)
        ignore_count = False
        if which == 'search':
            ignore_count = True
        for item in items:
            self.root.append(CATALOG_ENTRY(
                item, item.category, request_context, updated, which, ignore_count=ignore_count, add_kind=which != item.category))


class CategoryGroupFeed(NavFeed):

    def __init__(self, items, which, id_, updated, request_context, offsets, page_url, up_url, title=None):
        NavFeed.__init__(self, id_, updated, request_context, offsets, page_url, up_url, title=title)
        for item in items:
            self.root.append(CATALOG_GROUP_ENTRY(item, which, request_context, updated))


class RequestContext(object):

    def __init__(self, ctx, rd):
        self.db, self.library_id, self.library_map, self.default_library = get_library_data(ctx, rd)
        self.ctx, self.rd = ctx, rd

    def url_for(self, path, **kwargs):
        lid = kwargs.pop('library_id', self.library_id)
        ans = self.ctx.url_for(path, **kwargs)
        q = {'library_id':lid}
        ans += '?' + urlencode(q)
        return ans

    def all_book_ids(self):
        return self.db.all_book_ids()

    @property
    def outheaders(self):
        return self.rd.outheaders

    @property
    def opts(self):
        return self.ctx.opts

    def last_modified(self):
        return self.db.last_modified()

    def get_categories(self):
        return self.ctx.get_categories(self.rd, self.db)

    def search(self, query):
        return self.ctx.search(self.rd, self.db, query)


def get_acquisition_feed(rc, ids, offset, page_url, up_url, id_,
        sort_by='title', ascending=True, feed_title=None):
    if not ids:
        raise HTTPNotFound('No books found')
    with rc.db.safe_read_lock:
        sort_by = sanitize_sort_field_name(rc.db.field_metadata, sort_by)
        items = rc.db.multisort([(sort_by, ascending)], ids)
        max_items = rc.opts.max_opds_items
        offsets = Offsets(offset, max_items, len(items))
        items = items[offsets.offset:offsets.offset+max_items]
        lm = rc.last_modified()
        rc.outheaders['Last-Modified'] = http_date(timestampfromdt(lm))
        return AcquisitionFeed(id_, lm, rc, items, offsets, page_url, up_url, title=feed_title).root


def get_all_books(rc, which, page_url, up_url, offset=0):
    try:
        offset = int(offset)
    except Exception:
        raise HTTPNotFound('Not found')
    if which not in ('title', 'newest'):
        raise HTTPNotFound('Not found')
    sort = 'timestamp' if which == 'newest' else 'title'
    ascending = which == 'title'
    feed_title = {'newest':_('Newest'), 'title': _('Title')}.get(which, which)
    feed_title = default_feed_title + ' :: ' + _('By %s') % feed_title
    ids = rc.all_book_ids()
    return get_acquisition_feed(rc, ids, offset, page_url, up_url,
            id_='calibre-all:'+sort, sort_by=sort, ascending=ascending,
            feed_title=feed_title)


def get_navcatalog(request_context, which, page_url, up_url, offset=0):
    categories = request_context.get_categories()
    if which not in categories:
        raise HTTPNotFound('Category %r not found'%which)

    items = categories[which]
    updated = request_context.last_modified()
    category_meta = request_context.db.field_metadata
    meta = category_meta.get(which, {})
    category_name = meta.get('name', which)
    feed_title = default_feed_title + ' :: ' + _('By %s') % category_name

    id_ = 'calibre-category-feed:'+which

    MAX_ITEMS = request_context.opts.max_opds_ungrouped_items

    if MAX_ITEMS > 0 and len(items) <= MAX_ITEMS:
        max_items = request_context.opts.max_opds_items
        offsets = Offsets(offset, max_items, len(items))
        items = list(items)[offsets.offset:offsets.offset+max_items]
        ans = CategoryFeed(items, which, id_, updated, request_context, offsets,
            page_url, up_url, title=feed_title)
    else:
        Group = namedtuple('Group', 'text count')
        starts = set()
        for x in items:
            val = getattr(x, 'sort', x.name)
            if not val:
                val = 'A'
            starts.add(val[0].upper())
        category_groups = OrderedDict()
        for x in sorted(starts, key=sort_key):
            category_groups[x] = len([y for y in items if
                getattr(y, 'sort', y.name).startswith(x)])
        items = [Group(x, y) for x, y in category_groups.items()]
        max_items = request_context.opts.max_opds_items
        offsets = Offsets(offset, max_items, len(items))
        items = items[offsets.offset:offsets.offset+max_items]
        ans = CategoryGroupFeed(items, which, id_, updated, request_context, offsets,
            page_url, up_url, title=feed_title)

    request_context.outheaders['Last-Modified'] = http_date(timestampfromdt(updated))

    return ans.root


@endpoint('/opds', postprocess=atom)
def opds(ctx, rd):
    rc = RequestContext(ctx, rd)
    db = rc.db
    categories = rc.get_categories()
    category_meta = db.field_metadata
    cats = [
        (_('Newest'), _('Date'), 'Onewest'),
        (_('Title'), _('Title'), 'Otitle'),
    ]

    def getter(x):
        try:
            return category_meta[x]['name'].lower()
        except KeyError:
            return x

    for category in sorted(categories, key=lambda x: sort_key(getter(x))):
        if len(categories[category]) == 0:
            continue
        if category in ('formats', 'identifiers'):
            continue
        meta = category_meta.get(category, None)
        if meta is None:
            continue
        cats.append((meta['name'], meta['name'], 'N'+category))
    last_modified = db.last_modified()
    rd.outheaders['Last-Modified'] = http_date(timestampfromdt(last_modified))
    return TopLevel(last_modified, cats, rc).root


@endpoint('/opds/navcatalog/{which}', postprocess=atom)
def opds_navcatalog(ctx, rd, which):
    try:
        offset = int(rd.query.get('offset', 0))
    except Exception:
        raise HTTPNotFound('Not found')
    rc = RequestContext(ctx, rd)

    page_url = rc.url_for('/opds/navcatalog', which=which)
    up_url = rc.url_for('/opds')
    which = unhexlify(which)
    type_ = which[0]
    which = which[1:]
    if type_ == 'O':
        return get_all_books(rc, which, page_url, up_url, offset=offset)
    elif type_ == 'N':
        return get_navcatalog(rc, which, page_url, up_url, offset=offset)
    raise HTTPNotFound('Not found')


@endpoint('/opds/category/{category}/{which}', postprocess=atom)
def opds_category(ctx, rd, category, which):
    try:
        offset = int(rd.query.get('offset', 0))
    except Exception:
        raise HTTPNotFound('Not found')

    if not which or not category:
        raise HTTPNotFound('Not found')
    rc = RequestContext(ctx, rd)
    page_url = rc.url_for('/opds/category', which=which, category=category)
    up_url = rc.url_for('/opds/navcatalog', which=category)

    which, category = unhexlify(which), unhexlify(category)
    type_ = which[0]
    which = which[1:]
    if type_ == 'I':
        try:
            p = which.rindex(':')
            category = which[p+1:]
            which = which[:p]
            # This line will toss an exception for composite columns
            which = int(which[:p])
        except Exception:
            # Might be a composite column, where we have the lookup key
            if not (category in rc.db.field_metadata and
                    rc.db.field_metadata[category]['datatype'] == 'composite'):
                raise HTTPNotFound('Tag %r not found'%which)

    categories = rc.get_categories()
    if category not in categories:
        raise HTTPNotFound('Category %r not found'%which)

    if category == 'search':
        try:
            ids = rc.search('search:"%s"'%which)
        except Exception:
            raise HTTPNotFound('Search: %r not understood'%which)
        return get_acquisition_feed(rc, ids, offset, page_url, up_url, 'calibre-search:'+which)

    if type_ != 'I':
        raise HTTPNotFound('Non id categories not supported')

    q = category
    if q == 'news':
        q = 'tags'
    ids = rc.db.get_books_for_category(q, which)
    sort_by = 'series' if category == 'series' else 'title'

    return get_acquisition_feed(rc, ids, offset, page_url, up_url, 'calibre-category:'+category+':'+str(which), sort_by=sort_by)


@endpoint('/opds/categorygroup/{category}/{which}', postprocess=atom)
def opds_categorygroup(ctx, rd, category, which):
    try:
        offset = int(rd.query.get('offset', 0))
    except Exception:
        raise HTTPNotFound('Not found')

    if not which or not category:
        raise HTTPNotFound('Not found')

    rc = RequestContext(ctx, rd)
    categories = rc.get_categories()
    page_url = rc.url_for('/opds/categorygroup', category=category, which=which)

    category = unhexlify(category)
    if category not in categories:
        raise HTTPNotFound('Category %r not found'%which)
    category_meta = rc.db.field_metadata
    meta = category_meta.get(category, {})
    category_name = meta.get('name', which)
    which = unhexlify(which)
    feed_title = default_feed_title + ' :: ' + (_('By {0} :: {1}').format(category_name, which))
    owhich = hexlify('N'+which)
    up_url = rc.url_for('/opds/navcatalog', which=owhich)
    items = categories[category]

    def belongs(x, which):
        return getattr(x, 'sort', x.name).lower().startswith(which.lower())
    items = [x for x in items if belongs(x, which)]
    if not items:
        raise HTTPNotFound('No items in group %r:%r'%(category, which))
    updated = rc.last_modified()

    id_ = 'calibre-category-group-feed:'+category+':'+which

    max_items = rc.opts.max_opds_items
    offsets = Offsets(offset, max_items, len(items))
    items = list(items)[offsets.offset:offsets.offset+max_items]

    rc.outheaders['Last-Modified'] = http_date(timestampfromdt(updated))

    return CategoryFeed(items, category, id_, updated, rc, offsets, page_url, up_url, title=feed_title).root


@endpoint('/opds/search/{query=""}', postprocess=atom)
def opds_search(ctx, rd, query):
    try:
        offset = int(rd.query.get('offset', 0))
    except Exception:
        raise HTTPNotFound('Not found')

    rc = RequestContext(ctx, rd)
    try:
        ids = rc.search(query)
    except Exception:
        raise HTTPNotFound('Search: %r not understood'%query)
    page_url = rc.url_for('/opds/search', query=query)
    return get_acquisition_feed(rc, ids, offset, page_url, rc.url_for('/opds'), 'calibre-search:'+query)
