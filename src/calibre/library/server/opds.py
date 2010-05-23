#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai

__license__   = 'GPL v3'
__copyright__ = '2010, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import re
from itertools import repeat

import cherrypy

from calibre.utils.genshi.template import MarkupTemplate
from calibre.library.server.utils import strftime, expose
from calibre.ebooks.metadata import fmt_sidx, title_sort
from calibre import guess_type, prepare_string_for_xml

# Templates {{{

STANZA_ENTRY=MarkupTemplate('''\
<entry xmlns:py="http://genshi.edgewall.org/">
    <title>${record[FM['title']]}</title>
    <id>urn:calibre:${urn}</id>
    <author><name>${authors}</name></author>
    <updated>${timestamp}</updated>
    <link type="${mimetype}" href="/get/${fmt}/${record[FM['id']]}" />
    <link rel="x-stanza-cover-image" type="image/jpeg" href="/get/cover/${record[FM['id']]}" />
    <link rel="x-stanza-cover-image-thumbnail" type="image/jpeg" href="/get/thumb/${record[FM['id']]}" />
    <content type="xhtml">
        <div xmlns="http://www.w3.org/1999/xhtml" style="text-align: center">${Markup(extra)}${record[FM['comments']]}</div>
    </content>
</entry>
''')

STANZA_SUBCATALOG_ENTRY=MarkupTemplate('''\
<entry xmlns:py="http://genshi.edgewall.org/">
    <title>${title}</title>
    <id>urn:calibre:${id}</id>
    <updated>${updated.strftime('%Y-%m-%dT%H:%M:%S+00:00')}</updated>
    <link type="application/atom+xml" href="/stanza/?${what}id=${id}" />
    <content type="text">${count} books</content>
</entry>
''')

STANZA = MarkupTemplate('''\
<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:py="http://genshi.edgewall.org/">
    <title>calibre Library</title>
    <id>$id</id>
    <updated>${updated.strftime('%Y-%m-%dT%H:%M:%S+00:00')}</updated>
    <link rel="search" title="Search" type="application/atom+xml" href="/stanza/?search={searchTerms}"/>
    ${Markup(next_link)}
    <author>
    <name>calibre</name>
    <uri>http://calibre-ebook.com</uri>
    </author>
    <subtitle>
        ${subtitle}
    </subtitle>
    <py:for each="entry in data">
    ${Markup(entry)}
    </py:for>
</feed>
''')

STANZA_MAIN = MarkupTemplate('''\
<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:py="http://genshi.edgewall.org/">
    <title>calibre Library</title>
    <id>$id</id>
    <updated>${updated.strftime('%Y-%m-%dT%H:%M:%S+00:00')}</updated>
    <link rel="search" title="Search" type="application/atom+xml" href="/stanza/?search={searchTerms}"/>
    <author>
    <name>calibre</name>
    <uri>http://calibre-ebook.com</uri>
    </author>
    <subtitle>
        ${subtitle}
    </subtitle>
    <entry>
    <title>By Author</title>
    <id>urn:uuid:fc000fa0-8c23-11de-a31d-0002a5d5c51b</id>
    <updated>${updated.strftime('%Y-%m-%dT%H:%M:%S+00:00')}</updated>
    <link type="application/atom+xml" href="/stanza/?sortby=byauthor" />
    <content type="text">Books sorted by Author</content>
    </entry>
    <entry>
    <title>By Title</title>
    <id>urn:uuid:1df4fe40-8c24-11de-b4c6-0002a5d5c51b</id>
    <updated>${updated.strftime('%Y-%m-%dT%H:%M:%S+00:00')}</updated>
    <link type="application/atom+xml" href="/stanza/?sortby=bytitle" />
    <content type="text">Books sorted by Title</content>
    </entry>
    <entry>
    <title>By Newest</title>
    <id>urn:uuid:3c6d4940-8c24-11de-a4d7-0002a5d5c51b</id>
    <updated>${updated.strftime('%Y-%m-%dT%H:%M:%S+00:00')}</updated>
    <link type="application/atom+xml" href="/stanza/?sortby=bynewest" />
    <content type="text">Books sorted by Date</content>
    </entry>
    <entry>
    <title>By Tag</title>
    <id>urn:uuid:824921e8-db8a-4e61-7d38-f1ce41502853</id>
    <updated>${updated.strftime('%Y-%m-%dT%H:%M:%S+00:00')}</updated>
    <link type="application/atom+xml" href="/stanza/?sortby=bytag" />
    <content type="text">Books sorted by Tags</content>
    </entry>
    <entry>
    <title>By Series</title>
    <id>urn:uuid:512a5e50-a88f-f6b8-82aa-8f129c719f61</id>
    <updated>${updated.strftime('%Y-%m-%dT%H:%M:%S+00:00')}</updated>
    <link type="application/atom+xml" href="/stanza/?sortby=byseries" />
    <content type="text">Books sorted by Series</content>
    </entry>
</feed>
''')

# }}}

class OPDSServer(object):

    def get_matches(self, location, query):
        base = self.db.data.get_matches(location, query)
        epub = self.db.data.get_matches('format', '=epub')
        pdb = self.db.data.get_matches('format', '=pdb')
        return base.intersection(epub.union(pdb))

    def stanza_sortby_subcategory(self, updated, sortby, offset):
        pat = re.compile(r'\(.*\)')

        def clean_author(x):
            return pat.sub('', x).strip()

        def author_cmp(x, y):
            x = x if ',' in x else clean_author(x).rpartition(' ')[-1]
            y = y if ',' in y else clean_author(y).rpartition(' ')[-1]
            return cmp(x.lower(), y.lower())

        def get_author(x):
            pref, ___, suff = clean_author(x).rpartition(' ')
            return suff + (', '+pref) if pref else suff


        what, subtitle = sortby[2:], ''
        if sortby == 'byseries':
            data = self.db.all_series()
            data = [(x[0], x[1], len(self.get_matches('series', '='+x[1]))) for x in data]
            subtitle = 'Books by series'
        elif sortby == 'byauthor':
            data = self.db.all_authors()
            data = [(x[0], x[1], len(self.get_matches('authors', '='+x[1]))) for x in data]
            subtitle = 'Books by author'
        elif sortby == 'bytag':
            data = self.db.all_tags2()
            data = [(x[0], x[1], len(self.get_matches('tags', '='+x[1]))) for x in data]
            subtitle = 'Books by tag'
        fcmp = author_cmp if sortby == 'byauthor' else cmp
        data = [x for x in data if x[2] > 0]
        data.sort(cmp=lambda x, y: fcmp(x[1], y[1]))
        next_offset = offset + self.max_stanza_items
        rdata = data[offset:next_offset]
        if next_offset >= len(data):
            next_offset = -1
        gt = get_author if sortby == 'byauthor' else lambda x: x
        entries = [STANZA_SUBCATALOG_ENTRY.generate(title=gt(title), id=id,
            what=what, updated=updated, count=c).render('xml').decode('utf-8') for id,
            title, c in rdata]
        next_link = ''
        if next_offset > -1:
            next_link = ('<link rel="next" title="Next" '
            'type="application/atom+xml" href="/stanza/?sortby=%s&amp;offset=%d"/>\n'
            ) % (sortby, next_offset)
        return STANZA.generate(subtitle=subtitle, data=entries, FM=self.db.FIELD_MAP,
                    updated=updated, id='urn:calibre:main', next_link=next_link).render('xml')

    def stanza_main(self, updated):
        return STANZA_MAIN.generate(subtitle='', data=[], FM=self.db.FIELD_MAP,
                    updated=updated, id='urn:calibre:main').render('xml')

    @expose
    def stanza(self, search=None, sortby=None, authorid=None, tagid=None,
            seriesid=None, offset=0):
        'Feeds to read calibre books on a ipod with stanza.'
        books = []
        updated = self.db.last_modified()
        offset = int(offset)
        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        cherrypy.response.headers['Content-Type'] = 'text/xml'
        # Main feed
        if not sortby and not search and not authorid and not tagid and not seriesid:
            return self.stanza_main(updated)
        if sortby in ('byseries', 'byauthor', 'bytag'):
            return self.stanza_sortby_subcategory(updated, sortby, offset)

        # Get matching ids
        if authorid:
            authorid=int(authorid)
            au = self.db.author_name(authorid)
            ids = self.get_matches('authors', au)
        elif tagid:
            tagid=int(tagid)
            ta = self.db.tag_name(tagid)
            ids = self.get_matches('tags', ta)
        elif seriesid:
            seriesid=int(seriesid)
            se = self.db.series_name(seriesid)
            ids = self.get_matches('series', se)
        else:
            ids = self.db.data.parse(search) if search and search.strip() else self.db.data.universal_set()
        record_list = list(iter(self.db))

        FM = self.db.FIELD_MAP
        # Sort the record list
        if sortby == "bytitle" or authorid or tagid:
            record_list.sort(lambda x, y:
                    cmp(title_sort(x[FM['title']]),
                        title_sort(y[FM['title']])))
        elif seriesid:
            record_list.sort(lambda x, y:
                    cmp(x[FM['series_index']],
                        y[FM['series_index']]))
        else: # Sort by date
            record_list = reversed(record_list)


        fmts = FM['formats']
        pat = re.compile(r'EPUB|PDB', re.IGNORECASE)
        record_list = [x for x in record_list if x[FM['id']] in ids and
                pat.search(x[fmts] if x[fmts] else '') is not None]
        next_offset = offset + self.max_stanza_items
        nrecord_list = record_list[offset:next_offset]
        if next_offset >= len(record_list):
            next_offset = -1

        next_link = ''
        if next_offset > -1:
            q = ['offset=%d'%next_offset]
            for x in ('search', 'sortby', 'authorid', 'tagid', 'seriesid'):
                val = locals()[x]
                if val is not None:
                    val = prepare_string_for_xml(unicode(val), True)
                    q.append('%s=%s'%(x, val))
            next_link = ('<link rel="next" title="Next" '
            'type="application/atom+xml" href="/stanza/?%s"/>\n'
            ) % '&amp;'.join(q)

        for record in nrecord_list:
            r = record[FM['formats']]
            r = r.upper() if r else ''

            z = record[FM['authors']]
            if not z:
                z = _('Unknown')
            authors = ' & '.join([i.replace('|', ',') for i in
                                    z.split(',')])

            # Setup extra description
            extra = []
            rating = record[FM['rating']]
            if rating > 0:
                rating = ''.join(repeat('&#9733;', rating))
                extra.append('RATING: %s<br />'%rating)
            tags = record[FM['tags']]
            if tags:
                extra.append('TAGS: %s<br />'%\
                        prepare_string_for_xml(', '.join(tags.split(','))))
            series = record[FM['series']]
            if series:
                extra.append('SERIES: %s [%s]<br />'%\
                        (prepare_string_for_xml(series),
                        fmt_sidx(float(record[FM['series_index']]))))

            fmt = 'epub' if 'EPUB' in r else 'pdb'
            mimetype = guess_type('dummy.'+fmt)[0]

            # Create the sub-catalog, which is either a list of
            # authors/tags/series or a list of books
            data = dict(
                    record=record,
                    updated=updated,
                    authors=authors,
                    tags=tags,
                    series=series,
                    FM=FM,
                    extra='\n'.join(extra),
                    mimetype=mimetype,
                    fmt=fmt,
                    urn=record[FM['uuid']],
                    timestamp=strftime('%Y-%m-%dT%H:%M:%S+00:00',
                        record[FM['timestamp']])
                    )
            books.append(STANZA_ENTRY.generate(**data)\
                                        .render('xml').decode('utf8'))

        return STANZA.generate(subtitle='', data=books, FM=FM,
                next_link=next_link, updated=updated, id='urn:calibre:main').render('xml')




