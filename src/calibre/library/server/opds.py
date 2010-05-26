#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import hashlib, binascii
from functools import partial
from itertools import repeat

from lxml import etree, html
from lxml.builder import ElementMaker
import cherrypy
import routes

from calibre.constants import __appname__
from calibre.ebooks.metadata import fmt_sidx
from calibre.library.comments import comments_to_html
from calibre import guess_type

BASE_HREFS = {
        0 : '/stanza',
        1 : '/opds',
}

STANZA_FORMATS = frozenset(['epub', 'pdb'])

def url_for(name, version, **kwargs):
    if not name.endswith('_'):
        name += '_'
    return routes.url_for(name+str(version), **kwargs)

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
    href = base_href+'/navcatalog/'+binascii.hexlify(query)
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
NEXT_LINK  = partial(NAVLINK, rel='next')
PREVIOUS_LINK  = partial(NAVLINK, rel='previous')

def html_to_lxml(raw):
    raw = u'<div>%s</div>'%raw
    root = html.fragment_fromstring(raw)
    root.set('xmlns', "http://www.w3.org/1999/xhtml")
    raw = etree.tostring(root, encoding=None)
    return etree.fromstring(raw)

def ACQUISITION_ENTRY(item, version, FM, updated):
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
        extra.append(_('TAGS: %s<br />')%\
                ', '.join(tags.split(',')))
    series = item[FM['series']]
    if series:
        extra.append(_('SERIES: %s [%s]<br />')%\
                (series,
                fmt_sidx(float(item[FM['series_index']]))))
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
    if extra:
        ans.append(E.content(extra, type='xhtml'))
    formats = item[FM['formats']]
    if formats:
        for fmt in formats.split(','):
            fmt = fmt.lower()
            mt = guess_type('a.'+fmt)[0]
            href = '/get/%s/%s'%(fmt, item[FM['id']])
            if mt:
                link = E.link(type=mt, href=href)
                if version > 0:
                    link.set('rel', "http://opds-spec.org/acquisition")
                ans.append(link)
    ans.append(E.link(type='image/jpeg', href='/get/cover/%s'%item[FM['id']],
        rel="x-stanza-cover-image" if version == 0 else
        "http://opds-spec.org/cover"))
    ans.append(E.link(type='image/jpeg', href='/get/thumb/%s'%item[FM['id']],
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
                    UPDATED(updated),
                    SEARCH_LINK(self.base_href),
                    START_LINK(self.base_href)
                )
        if up_link:
            self.root.append(UP_LINK(up_link))
        if first_link:
            self.root.append(FIRST_LINK(first_link))
        if last_link:
            self.root.append(LAST_LINK(last_link))
        if next_link:
            self.root.append(NEXT_LINK(next_link))
        if previous_link:
            self.root.append(PREVIOUS_LINK(previous_link))
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
            FM):
        NavFeed.__init__(self, id_, updated, version, offsets, page_url, up_url)
        for item in items:
            self.root.append(ACQUISITION_ENTRY(item, version, FM, updated))


class OPDSOffsets(object):

    def __init__(self, offset, delta, total):
        if offset < 0:
            offset = 0
        if offset >= total:
            raise cherrypy.HTTPError(404, 'Invalid offset: %r'%offset)
        self.offset = offset
        self.next_offset = offset + delta
        if self.next_offset >= total:
            self.next_offset = -1
        if self.next_offset >= total:
            self.next_offset = -1
        self.previous_offset = self.offset - delta
        if self.previous_offset < 0:
            self.previous_offset = 0
        self.last_offset = total - delta
        if self.last_offset < 0:
            self.last_offset = 0


class OPDSServer(object):

    def add_routes(self, connect):
        for version in (0, 1):
            base_href = BASE_HREFS[version]
            ver = str(version)
            connect('opds_'+ver, base_href, self.opds, version=version)
            connect('opdsnavcatalog_'+ver, base_href+'/navcatalog/{which}',
                    self.opds_navcatalog, version=version)
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
        items = [x for x in self.db.data.iterall() if x[idx] in ids]
        self.sort(items, sort_by, ascending)
        max_items = self.opts.max_opds_items
        offsets = OPDSOffsets(offset, max_items, len(items))
        items = items[offsets.offset:offsets.next_offset]
        return str(AcquisitionFeed(self.db.last_modified(), id_, items, offsets,
            page_url, up_url, version, self.db.FIELD_MAP))

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
        return self.get_opds_acquisition_feed(ids, offset, '/search/'+query,
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

    def opds_navcatalog(self, which=None, version=0, offset=0):
        version = int(version)
        if not which or version not in BASE_HREFS:
            raise cherrypy.HTTPError(404, 'Not found')
        page_url = url_for('opdsnavcatalog', version, which=which)
        up_url = url_for('opds', version)
        which = binascii.unhexlify(which)
        type_ = which[0]
        which = which[1:]
        if type_ == 'O':
            return self.get_opds_all_books(which, page_url, up_url,
                    version=version, offset=offset)
        elif type_ == 'N':
            return self.get_opds_navcatalog(which)
        raise cherrypy.HTTPError(404, 'Not found')

    def opds(self, version=0):
        version = int(version)
        if version not in BASE_HREFS:
            raise cherrypy.HTTPError(404, 'Not found')
        categories = self.categories_cache(
                self.get_opds_allowed_ids_for_version(version))
        category_meta = self.db.get_tag_browser_categories()
        cats = [
                (_('Newest'), _('Date'), 'Onewest'),
                (_('Title'), _('Title'), 'Otitle'),
                ]
        for category in categories:
            if category == 'formats':
                continue
            meta = category_meta.get(category, None)
            if meta is None:
                continue
            cats.append((meta['name'], meta['name'], 'N'+category))
        updated = self.db.last_modified()

        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        cherrypy.response.headers['Content-Type'] = 'text/xml'

        feed = TopLevel(updated, cats, version)

        return str(feed)



