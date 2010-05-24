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
NAVLINK = partial(E.link,
        type='application/atom+xml;type=feed;profile=opds-catalog')

def SEARCH(base_href, *args, **kwargs):
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

# }}}

class Feed(object):

    def __str__(self):
        return etree.tostring(self.root, pretty_print=True, encoding='utf-8',
                xml_declaration=True)

class TopLevel(Feed):

    def __init__(self,
            updated,  # datetime object in UTC
            categories,
            version,
            id_       = 'urn:calibre:main',
            ):
        base_href = BASE_HREFS[version]
        self.base_href = base_href
        subc = partial(NAVCATALOG_ENTRY, base_href, updated)

        subcatalogs = [subc(_('By ')+title,
            _('Books sorted by ') + desc, q) for title, desc, q in
            categories]

        self.root = \
            FEED(
                    TITLE(__appname__ + ' ' + _('Library')),
                    ID(id_),
                    UPDATED(updated),
                    SEARCH(base_href),
                    AUTHOR(__appname__, uri='http://calibre-ebook.com'),
                    SUBTITLE(_('Books in your library')),
                    *subcatalogs
                )

STANZA_FORMATS = frozenset(['epub', 'pdb'])

class OPDSServer(object):

    def add_routes(self, connect):
        for base in ('stanza', 'opds'):
            version = 0 if base == 'stanza' else 1
            base_href = BASE_HREFS[version]
            connect(base, base_href, self.opds, version=version)
            connect('opdsnavcatalog_'+base, base_href+'/navcatalog/{which}',
                    self.opds_navcatalog, version=version)
            connect('opdssearch_'+base, base_href+'/search/{terms}',
                    self.opds_search, version=version)

    def get_opds_allowed_ids_for_version(self, version):
        search = '' if version > 0 else ' '.join(['format:='+x for x in
            STANZA_FORMATS])
        self.seach_cache(search)

    def opds_search(self, terms=None, version=0):
        version = int(version)
        if not terms or version not in BASE_HREFS:
            raise cherrypy.HTTPError(404, 'Not found')

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



