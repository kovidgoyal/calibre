#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import hashlib, binascii
from functools import partial
from itertools import repeat
from collections import OrderedDict

from lxml import etree, html
from lxml.builder import ElementMaker
import cherrypy
import routes

from calibre.constants import __appname__
from calibre.ebooks.metadata import fmt_sidx
from calibre.library.comments import comments_to_html
from calibre.library.server import custom_fields_to_display
from calibre.library.server.utils import format_tag_string, Offsets
from calibre import guess_type, prepare_string_for_xml as xml
from calibre.utils.icu import sort_key

BASE_HREFS = {
        0 : '/stanza',
        1 : '/opds',
}

STANZA_FORMATS = frozenset(['epub', 'pdb', 'pdf', 'cbr', 'cbz', 'djvu'])

def url_for(name, version, **kwargs):
    if not name.endswith('_'):
        name += '_'
    return routes.url_for(name+str(version), **kwargs)

def hexlify(x):
    if isinstance(x, unicode):
        x = x.encode('utf-8')
    return binascii.hexlify(x)

def unhexlify(x):
    return binascii.unhexlify(x).decode('utf-8')

# Vocabulary for building OPDS feeds {{{
E = ElementMaker(namespace='http://www.w3.org/2005/Atom',
                 nsmap={
                     None   : 'http://www.w3.org/2005/Atom',
                     'dc'   : 'http://purl.org/dc/terms/',
                     'opds' : 'http://opds-spec.org/2010/catalog',
                     })


FEED    = E.feed
TITLE   = E.title
ID      = E.id
ICON    = E.icon

def UPDATED(dt, *args, **kwargs):
    return E.updated(dt.strftime('%Y-%m-%dT%H:%M:%S+00:00'), *args, **kwargs)

LINK = partial(E.link, type='application/atom+xml')
NAVLINK = partial(E.link,
        type='application/atom+xml;type=feed;profile=opds-catalog')

def SEARCH_LINK(base_href, *args, **kwargs):
    kwargs['rel'] = 'search'
    kwargs['title'] = 'Search'
    kwargs['href'] = base_href+'/search/{searchTerms}'
    return LINK(*args, **kwargs)

def AUTHOR(name, uri=None):
    args = [E.name(name)]
    if uri is not None:
        args.append(E.uri(uri))
    return E.author(*args)

SUBTITLE = E.subtitle

def NAVCATALOG_ENTRY(base_href, updated, title, description, query, version=0):
    href = base_href+'/navcatalog/'+hexlify(query)
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

def CATALOG_ENTRY(item, item_kind, base_href, version, updated,
                  ignore_count=False, add_kind=False):
    id_ = 'calibre:category:'+item.name
    iid = 'N' + item.name
    if item.id is not None:
        iid = 'I' + str(item.id)
        iid += ':'+item_kind
    link = NAVLINK(href = base_href + '/' + hexlify(iid))
    count = (_('%d books') if item.count > 1 else _('%d book'))%item.count
    if ignore_count:
        count = ''
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

def CATALOG_GROUP_ENTRY(item, category, base_href, version, updated):
    id_ = 'calibre:category-group:'+category+':'+item.text
    iid = item.text
    link = NAVLINK(href = base_href + '/' + hexlify(iid))
    return E.entry(
            TITLE(item.text),
            ID(id_),
            UPDATED(updated),
            E.content(_('%d items')%item.count, type='text'),
            link
            )

def ACQUISITION_ENTRY(item, version, db, updated, CFM, CKEYS, prefix):
    FM = db.FIELD_MAP
    title = item[FM['title']]
    if not title:
        title = _('Unknown')
    authors = item[FM['authors']]
    if not authors:
        authors = _('Unknown')
    authors = ' & '.join([i.replace('|', ',') for i in
                                    authors.split(',')])
    extra = []
    rating = item[FM['rating']]
    if rating > 0:
        rating = u''.join(repeat(u'\u2605', int(rating/2.)))
        extra.append(_('RATING: %s<br />')%rating)
    tags = item[FM['tags']]
    if tags:
        extra.append(_('TAGS: %s<br />')%xml(format_tag_string(tags, ',',
                                                           ignore_max=True,
                                                           no_tag_count=True)))
    series = item[FM['series']]
    if series:
        extra.append(_('SERIES: %(series)s [%(sidx)s]<br />')%\
                dict(series=xml(series),
                sidx=fmt_sidx(float(item[FM['series_index']]))))
    for key in CKEYS:
        mi = db.get_metadata(item[CFM['id']['rec_index']], index_is_id=True)
        name, val = mi.format_field(key)
        if val:
            datatype = CFM[key]['datatype']
            if datatype == 'text' and CFM[key]['is_multiple']:
                extra.append('%s: %s<br />'%
                             (xml(name),
                              xml(format_tag_string(val,
                                    CFM[key]['is_multiple']['ui_to_list'],
                                    ignore_max=True, no_tag_count=True,
                                    joinval=CFM[key]['is_multiple']['list_to_ui']))))
            elif datatype == 'comments' or (CFM[key]['datatype'] == 'composite' and
                            CFM[key]['display'].get('contains_html', False)):
                extra.append('%s: %s<br />'%(xml(name), comments_to_html(unicode(val))))
            else:
                extra.append('%s: %s<br />'%(xml(name), xml(unicode(val))))
    comments = item[FM['comments']]
    if comments:
        comments = comments_to_html(comments)
        extra.append(comments)
    if extra:
        extra = html_to_lxml('\n'.join(extra))
    idm = 'calibre' if version == 0 else 'uuid'
    id_ = 'urn:%s:%s'%(idm, item[FM['uuid']])
    ans = E.entry(TITLE(title), E.author(E.name(authors)), ID(id_),
            UPDATED(updated))
    if len(extra):
        ans.append(E.content(extra, type='xhtml'))
    formats = item[FM['formats']]
    if formats:
        for fmt in formats.split(','):
            fmt = fmt.lower()
            mt = guess_type('a.'+fmt)[0]
            href = prefix + '/get/%s/%s'%(fmt, item[FM['id']])
            if mt:
                link = E.link(type=mt, href=href)
                if version > 0:
                    link.set('rel', "http://opds-spec.org/acquisition")
                ans.append(link)
    ans.append(E.link(type='image/jpeg', href=prefix+'/get/cover/%s'%item[FM['id']],
        rel="x-stanza-cover-image" if version == 0 else
        "http://opds-spec.org/cover"))
    ans.append(E.link(type='image/jpeg', href=prefix+'/get/thumb/%s'%item[FM['id']],
        rel="x-stanza-cover-image-thumbnail" if version == 0 else
        "http://opds-spec.org/thumbnail"))

    return ans


# }}}

class Feed(object): # {{{

    def __init__(self, id_, updated, version, subtitle=None,
            title=__appname__ + ' ' + _('Library'),
            up_link=None, first_link=None, last_link=None,
            next_link=None, previous_link=None):
        self.base_href = url_for('opds', version)

        self.root = \
            FEED(
                    TITLE(title),
                    AUTHOR(__appname__, uri='http://calibre-ebook.com'),
                    ID(id_),
                    ICON('/favicon.png'),
                    UPDATED(updated),
                    SEARCH_LINK(self.base_href),
                    START_LINK(href=self.base_href)
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

    def __str__(self):
        return etree.tostring(self.root, pretty_print=True, encoding='utf-8',
                xml_declaration=True)
    # }}}

class TopLevel(Feed): # {{{

    def __init__(self,
            updated,  # datetime object in UTC
            categories,
            version,
            id_       = 'urn:calibre:main',
            subtitle  = _('Books in your library')
            ):
        Feed.__init__(self, id_, updated, version, subtitle=subtitle)

        subc = partial(NAVCATALOG_ENTRY, self.base_href, updated,
                version=version)
        subcatalogs = [subc(_('By ')+title,
            _('Books sorted by ') + desc, q) for title, desc, q in
            categories]
        for x in subcatalogs:
            self.root.append(x)
# }}}

class NavFeed(Feed):

    def __init__(self, id_, updated, version, offsets, page_url, up_url):
        kwargs = {'up_link': up_url}
        kwargs['first_link'] = page_url
        kwargs['last_link']  = page_url+'?offset=%d'%offsets.last_offset
        if offsets.offset > 0:
            kwargs['previous_link'] = \
                page_url+'?offset=%d'%offsets.previous_offset
        if offsets.next_offset > -1:
            kwargs['next_link'] = \
                page_url+'?offset=%d'%offsets.next_offset
        Feed.__init__(self, id_, updated, version, **kwargs)

class AcquisitionFeed(NavFeed):

    def __init__(self, updated, id_, items, offsets, page_url, up_url, version,
            db, prefix):
        NavFeed.__init__(self, id_, updated, version, offsets, page_url, up_url)
        CFM = db.field_metadata
        CKEYS = [key for key in sorted(custom_fields_to_display(db),
                                       key=lambda x: sort_key(CFM[x]['name']))]
        for item in items:
            self.root.append(ACQUISITION_ENTRY(item, version, db, updated,
                                               CFM, CKEYS, prefix))

class CategoryFeed(NavFeed):

    def __init__(self, items, which, id_, updated, version, offsets, page_url, up_url, db):
        NavFeed.__init__(self, id_, updated, version, offsets, page_url, up_url)
        base_href = self.base_href + '/category/' + hexlify(which)
        ignore_count = False
        if which == 'search':
            ignore_count = True
        for item in items:
            self.root.append(CATALOG_ENTRY(item, item.category, base_href, version,
                                           updated, ignore_count=ignore_count,
                                           add_kind=which != item.category))

class CategoryGroupFeed(NavFeed):

    def __init__(self, items, which, id_, updated, version, offsets, page_url, up_url):
        NavFeed.__init__(self, id_, updated, version, offsets, page_url, up_url)
        base_href = self.base_href + '/categorygroup/' + hexlify(which)
        for item in items:
            self.root.append(CATALOG_GROUP_ENTRY(item, which, base_href, version, updated))



class OPDSServer(object):

    def add_routes(self, connect):
        for version in (0, 1):
            base_href = BASE_HREFS[version]
            ver = str(version)
            connect('opds_'+ver, base_href, self.opds, version=version)
            connect('opdst_'+ver, base_href+'/', self.opds, version=version)
            connect('opdsnavcatalog_'+ver, base_href+'/navcatalog/{which}',
                    self.opds_navcatalog, version=version)
            connect('opdscategory_'+ver, base_href+'/category/{category}/{which}',
                    self.opds_category, version=version)
            connect('opdscategorygroup_'+ver, base_href+'/categorygroup/{category}/{which}',
                    self.opds_category_group, version=version)
            connect('opdssearch_'+ver, base_href+'/search/{query}',
                    self.opds_search, version=version)

    def get_opds_allowed_ids_for_version(self, version):
        search = '' if version > 0 else ' or '.join(['format:='+x for x in
            STANZA_FORMATS])
        ids = self.search_cache(search)
        return ids

    def get_opds_acquisition_feed(self, ids, offset, page_url, up_url, id_,
            sort_by='title', ascending=True, version=0):
        idx = self.db.FIELD_MAP['id']
        ids &= self.get_opds_allowed_ids_for_version(version)
        if not ids:
            raise cherrypy.HTTPError(404, 'No books found')
        items = [x for x in self.db.data.iterall() if x[idx] in ids]
        self.sort(items, sort_by, ascending)
        max_items = self.opts.max_opds_items
        offsets = Offsets(offset, max_items, len(items))
        items = items[offsets.offset:offsets.offset+max_items]
        updated = self.db.last_modified()
        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        cherrypy.response.headers['Content-Type'] = 'application/atom+xml;profile=opds-catalog'
        return str(AcquisitionFeed(updated, id_, items, offsets,
                                   page_url, up_url, version, self.db,
                                   self.opts.url_prefix))

    def opds_search(self, query=None, version=0, offset=0):
        try:
            offset = int(offset)
            version = int(version)
        except:
            raise cherrypy.HTTPError(404, 'Not found')
        if query is None or version not in BASE_HREFS:
            raise cherrypy.HTTPError(404, 'Not found')
        try:
            ids = self.search_cache(query)
        except:
            raise cherrypy.HTTPError(404, 'Search: %r not understood'%query)
        page_url = url_for('opdssearch', version, query=query)
        return self.get_opds_acquisition_feed(ids, offset, page_url,
                url_for('opds', version), 'calibre-search:'+query,
                version=version)

    def get_opds_all_books(self, which, page_url, up_url, version=0, offset=0):
        try:
            offset = int(offset)
            version = int(version)
        except:
            raise cherrypy.HTTPError(404, 'Not found')
        if which not in ('title', 'newest') or version not in BASE_HREFS:
            raise cherrypy.HTTPError(404, 'Not found')
        sort = 'timestamp' if which == 'newest' else 'title'
        ascending = which == 'title'
        ids = self.get_opds_allowed_ids_for_version(version)
        return self.get_opds_acquisition_feed(ids, offset, page_url, up_url,
                id_='calibre-all:'+sort, sort_by=sort, ascending=ascending,
                version=version)

    # Categories {{{

    def opds_category_group(self, category=None, which=None, version=0, offset=0):
        try:
            offset = int(offset)
            version = int(version)
        except:
            raise cherrypy.HTTPError(404, 'Not found')

        if not which or not category or version not in BASE_HREFS:
            raise cherrypy.HTTPError(404, 'Not found')

        categories = self.categories_cache(
                self.get_opds_allowed_ids_for_version(version))
        page_url = url_for('opdscategorygroup', version, category=category, which=which)

        category = unhexlify(category)
        if category not in categories:
            raise cherrypy.HTTPError(404, 'Category %r not found'%which)
        which = unhexlify(which)
        owhich = hexlify('N'+which)
        up_url = url_for('opdsnavcatalog', version, which=owhich)
        items = categories[category]
        def belongs(x, which):
            return getattr(x, 'sort', x.name).lower().startswith(which.lower())
        items = [x for x in items if belongs(x, which)]
        if not items:
            raise cherrypy.HTTPError(404, 'No items in group %r:%r'%(category,
                which))
        updated = self.db.last_modified()

        id_ = 'calibre-category-group-feed:'+category+':'+which

        max_items = self.opts.max_opds_items
        offsets = Offsets(offset, max_items, len(items))
        items = list(items)[offsets.offset:offsets.offset+max_items]

        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        cherrypy.response.headers['Content-Type'] = 'application/atom+xml'

        return str(CategoryFeed(items, category, id_, updated, version, offsets,
            page_url, up_url, self.db))


    def opds_navcatalog(self, which=None, version=0, offset=0):
        try:
            offset = int(offset)
            version = int(version)
        except:
            raise cherrypy.HTTPError(404, 'Not found')

        if not which or version not in BASE_HREFS:
            raise cherrypy.HTTPError(404, 'Not found')
        page_url = url_for('opdsnavcatalog', version, which=which)
        up_url = url_for('opds', version)
        which = unhexlify(which)
        type_ = which[0]
        which = which[1:]
        if type_ == 'O':
            return self.get_opds_all_books(which, page_url, up_url,
                    version=version, offset=offset)
        elif type_ == 'N':
            return self.get_opds_navcatalog(which, page_url, up_url,
                    version=version, offset=offset)
        raise cherrypy.HTTPError(404, 'Not found')

    def get_opds_navcatalog(self, which, page_url, up_url, version=0, offset=0):
        categories = self.categories_cache(
                self.get_opds_allowed_ids_for_version(version))
        if which not in categories:
            raise cherrypy.HTTPError(404, 'Category %r not found'%which)

        items = categories[which]
        updated = self.db.last_modified()

        id_ = 'calibre-category-feed:'+which

        MAX_ITEMS = self.opts.max_opds_ungrouped_items

        if len(items) <= MAX_ITEMS:
            max_items = self.opts.max_opds_items
            offsets = Offsets(offset, max_items, len(items))
            items = list(items)[offsets.offset:offsets.offset+max_items]
            ans = CategoryFeed(items, which, id_, updated, version, offsets,
                page_url, up_url, self.db)
        else:
            class Group:
                def __init__(self, text, count):
                    self.text, self.count = text, count

            starts = set([])
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
            max_items = self.opts.max_opds_items
            offsets = Offsets(offset, max_items, len(items))
            items = items[offsets.offset:offsets.offset+max_items]
            ans = CategoryGroupFeed(items, which, id_, updated, version, offsets,
                page_url, up_url)

        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        cherrypy.response.headers['Content-Type'] = 'application/atom+xml'

        return str(ans)

    def opds_category(self, category=None, which=None, version=0, offset=0):
        try:
            offset = int(offset)
            version = int(version)
        except:
            raise cherrypy.HTTPError(404, 'Not found')

        if not which or not category or version not in BASE_HREFS:
            raise cherrypy.HTTPError(404, 'Not found')
        page_url = url_for('opdscategory', version, which=which,
                category=category)
        up_url = url_for('opdsnavcatalog', version, which=category)

        which, category = unhexlify(which), unhexlify(category)
        type_ = which[0]
        which = which[1:]
        if type_ == 'I':
            try:
                p = which.index(':')
                category = which[p+1:]
                which = int(which[:p])
            except:
                raise cherrypy.HTTPError(404, 'Tag %r not found'%which)

        categories = self.categories_cache(
                self.get_opds_allowed_ids_for_version(version))
        if category not in categories:
            raise cherrypy.HTTPError(404, 'Category %r not found'%which)

        if category == 'search':
            try:
                ids = self.search_cache('search:"%s"'%which)
            except:
                raise cherrypy.HTTPError(404, 'Search: %r not understood'%which)
            return self.get_opds_acquisition_feed(ids, offset, page_url,
                    up_url, 'calibre-search:'+which,
                    version=version)

        if type_ != 'I':
            raise cherrypy.HTTPError(404, 'Non id categories not supported')

        q = category
        if q == 'news': q = 'tags'
        ids = self.db.get_books_for_category(q, which)
        sort_by = 'series' if category == 'series' else 'title'

        return self.get_opds_acquisition_feed(ids, offset, page_url,
                up_url, 'calibre-category:'+category+':'+str(which),
                version=version, sort_by=sort_by)

    # }}}


    def opds(self, version=0):
        version = int(version)
        if version not in BASE_HREFS:
            raise cherrypy.HTTPError(404, 'Not found')
        categories = self.categories_cache(
                self.get_opds_allowed_ids_for_version(version))
        category_meta = self.db.field_metadata
        cats = [
                (_('Newest'), _('Date'), 'Onewest'),
                (_('Title'), _('Title'), 'Otitle'),
                ]
        def getter(x):
            return category_meta[x]['name'].lower()
        for category in sorted(categories, key=lambda x: sort_key(getter(x))):
            if len(categories[category]) == 0:
                continue
            if category in ('formats', 'identifiers'):
                continue
            meta = category_meta.get(category, None)
            if meta is None:
                continue
            if category_meta.is_custom_field(category) and \
                                category not in custom_fields_to_display(self.db):
                continue
            cats.append((meta['name'], meta['name'], 'N'+category))
        updated = self.db.last_modified()

        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        cherrypy.response.headers['Content-Type'] = 'application/atom+xml'

        feed = TopLevel(updated, cats, version)

        return str(feed)



