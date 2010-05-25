#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import hashlib, binascii
from functools import partial

from lxml import etree
from lxml.builder import ElementMaker
import cherrypy

from calibre.constants import __appname__

BASE_HREFS = {
        0 : '/stanza',
        1 : '/opds',
}

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
NAVLINK = partial(E.link, rel='subsection',
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

def NAVCATALOG_ENTRY(base_href, updated, title, description, query):
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

# }}}

class Feed(object):

    def __init__(self, id_, updated, version, subtitle=None,
            title=__appname__ + ' ' + _('Library'),
            up_link=None, first_link=None, last_link=None,
            next_link=None, previous_link=None):
        self.base_href = BASE_HREFS[version]

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

class TopLevel(Feed): # {{{

    def __init__(self,
            updated,  # datetime object in UTC
            categories,
            version,
            id_       = 'urn:calibre:main',
            subtitle  = _('Books in your library')
            ):
        Feed.__init__(self, id_, updated, version, subtitle=subtitle)

        subc = partial(NAVCATALOG_ENTRY, self.base_href, updated)
        subcatalogs = [subc(_('By ')+title,
            _('Books sorted by ') + desc, q) for title, desc, q in
            categories]
        for x in subcatalogs:
            self.root.append(x)
# }}}

class AcquisitionFeed(Feed):

    def __init__(self, updated, id_, items, offsets, page_url, up_url, version):
        kwargs = {'up_link': up_url}
        kwargs['first_link'] = page_url
        kwargs['last_link']  = page_url+'?offset=%d'%offsets.last_offset
        if offsets.offset > 0:
            kwargs['previous_link'] = \
                page_url+'?offset=%d'%offsets.previous_offset
        if offsets.next_offset > -1:
            kwargs['next_offset'] = \
                page_url+'?offset=%d'%offsets.next_offset
        Feed.__init__(self, id_, updated, version, **kwargs)

STANZA_FORMATS = frozenset(['epub', 'pdb'])

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
        for base in ('stanza', 'opds'):
            version = 0 if base == 'stanza' else 1
            base_href = BASE_HREFS[version]
            connect(base, base_href, self.opds, version=version)
            connect('opdsnavcatalog_'+base, base_href+'/navcatalog/{which}',
                    self.opds_navcatalog, version=version)
            connect('opdssearch_'+base, base_href+'/search/{query}',
                    self.opds_search, version=version)

    def get_opds_allowed_ids_for_version(self, version):
        search = '' if version > 0 else ' '.join(['format:='+x for x in
            STANZA_FORMATS])
        self.search_cache(search)

    def get_opds_acquisition_feed(self, ids, offset, page_url, up_url, id_,
            sort_by='title', ascending=True, version=0):
        idx = self.db.FIELD_MAP['id']
        ids &= self.get_opds_allowed_ids_for_version(version)
        items = [x for x in self.db.data.iterall() if x[idx] in ids]
        self.sort(items, sort_by, ascending)
        max_items = self.opts.max_opds_items
        offsets = OPDSOffsets(offset, max_items, len(items))
        items = items[offsets.offset:offsets.next_offset]
        return str(AcquisitionFeed(self.db.last_modified(), id_, items, offsets, page_url, up_url, version))

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
        return self.get_opds_acquisition_feed(ids,
                sort_by='title', version=version)

    def opds_navcatalog(self, which=None, version=0):
        version = int(version)
        if not which or version not in BASE_HREFS:
            raise cherrypy.HTTPError(404, 'Not found')
        which = binascii.unhexlify(which)
        type_ = which[0]
        which = which[1:]
        if type_ == 'O':
            return self.get_opds_all_books(which)
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



