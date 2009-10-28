#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
HTTP server for remote access to the calibre database.
'''

import sys, textwrap, operator, os, re, logging, cStringIO
import __builtin__
from itertools import repeat
from logging.handlers import RotatingFileHandler
from datetime import datetime
from threading import Thread

import cherrypy
try:
    from PIL import Image as PILImage
    PILImage
except ImportError:
    import Image as PILImage

from calibre.constants import __version__, __appname__
from calibre.utils.genshi.template import MarkupTemplate
from calibre import fit_image, guess_type, prepare_string_for_xml, \
        strftime as _strftime, prints
from calibre.library import server_config as config
from calibre.library.database2 import LibraryDatabase2, FIELD_MAP
from calibre.utils.config import config_dir
from calibre.utils.mdns import publish as publish_zeroconf, \
                               stop_server as stop_zeroconf
from calibre.ebooks.metadata import fmt_sidx, title_sort

def strftime(fmt='%Y/%m/%d %H:%M:%S', dt=None):
    if not hasattr(dt, 'timetuple'):
        dt = datetime.now()
    dt = dt.timetuple()
    try:
        return _strftime(fmt, dt)
    except:
        return _strftime(fmt, datetime.now().timetuple())

def expose(func):

    def do(self, *args, **kwargs):
        dict.update(cherrypy.response.headers, {'Server':self.server_name})
        return func(self, *args, **kwargs)

    return cherrypy.expose(do)

log_access_file = os.path.join(config_dir, 'server_access_log.txt')
log_error_file = os.path.join(config_dir, 'server_error_log.txt')


class LibraryServer(object):

    server_name = __appname__ + '/' + __version__

    BOOK = textwrap.dedent('''\
        <book xmlns:py="http://genshi.edgewall.org/"
            id="${r[0]}"
            title="${r[1]}"
            sort="${r[11]}"
            author_sort="${r[12]}"
            authors="${authors}"
            rating="${r[4]}"
            timestamp="${timestamp}"
            pubdate="${pubdate}"
            size="${r[6]}"
            isbn="${r[14] if r[14] else ''}"
            formats="${r[13] if r[13] else ''}"
            series = "${r[9] if r[9] else ''}"
            series_index="${r[10]}"
            tags="${r[7] if r[7] else ''}"
            publisher="${r[3] if r[3] else ''}">${r[8] if r[8] else ''}
            </book>
        ''')

    MOBILE_UA = re.compile('(?i)(?:iPhone|Opera Mini|NetFront|webOS|Mobile|Android|imode|DoCoMo|Minimo|Blackberry|MIDP|Symbian)')

    MOBILE_BOOK = textwrap.dedent('''\
    <tr xmlns:py="http://genshi.edgewall.org/">
    <td class="thumbnail">
        <img type="image/jpeg" src="/get/thumb/${r[0]}" border="0"/>
    </td>
    <td>
        <py:for each="format in r[13].split(',')">
            <span class="button"><a href="/get/${format}/${authors}-${r[1]}_${r[0]}.${format}">${format.lower()}</a></span>&nbsp;
        </py:for>
       ${r[1]} by ${authors} - ${r[6]/1024}k - ${r[3] if r[3] else ''} ${pubdate} ${'['+r[7]+']' if r[7] else ''}
    </td>
    </tr>
    ''')

    MOBILE = MarkupTemplate(textwrap.dedent('''\
    <html xmlns:py="http://genshi.edgewall.org/">
    <head>
    <style>
    .navigation table.buttons {
        width: 100%;
    }
    .navigation .button {
        width: 50%;
    }
    .button a, .button:visited a {
        padding: 0.5em;
        font-size: 1.25em;
        border: 1px solid black;
        text-color: black;
        background-color: #ddd;
        border-top: 1px solid ThreeDLightShadow;
        border-right: 1px solid ButtonShadow;
        border-bottom: 1px solid ButtonShadow;
        border-left: 1 px solid ThreeDLightShadow;
        -moz-border-radius: 0.25em;
        -webkit-border-radius: 0.25em;
    }

    .button:hover a {
        border-top: 1px solid #666;
        border-right: 1px solid #CCC;
        border-bottom: 1 px solid #CCC;
        border-left: 1 px solid #666;


    }
    div.navigation {
        padding-bottom: 1em;
        clear: both;
    }

    #search_box {
        border: 1px solid #393;
        -moz-border-radius: 0.5em;
        -webkit-border-radius: 0.5em;
        padding: 1em;
        margin-bottom: 0.5em;
        float: right;
    }

    #listing {
        width: 100%;
        border-collapse: collapse;
    }
    #listing td {
        padding: 0.25em;
    }

    #listing td.thumbnail {
        height: 60px;
        width: 60px;
    }

    #listing tr:nth-child(even) {

        background: #eee;
    }

    #listing .button a{
        display: inline-block;
        width: 2.5em;
        padding-left: 0em;
        padding-right: 0em;
        overflow: hidden;
        text-align: center;
    }

    #logo {
        float: left;
    }
    #spacer {
        clear: both;
    }

    </style>
    <link rel="icon" href="http://calibre.kovidgoyal.net/chrome/site/favicon.ico" type="image/x-icon" />
    </head>
    <body>
        <div id="logo">
        <img src="/static/calibre.png" alt="Calibre" />
        </div>
        <div id="search_box">
        <form method="get" action="/mobile">
        Show <select name="num">
            <py:for each="option in [5,10,25,100]">
                 <option py:if="option == num" value="${option}" SELECTED="SELECTED">${option}</option>
                 <option py:if="option != num" value="${option}">${option}</option>
            </py:for>
            </select>
        books matching <input name="search" id="s" value="${search}" /> sorted by

        <select name="sort">
            <py:for each="option in ['date','author','title','rating','size','tags','series']">
                 <option py:if="option == sort" value="${option}" SELECTED="SELECTED">${option}</option>
                 <option py:if="option != sort" value="${option}">${option}</option>
            </py:for>
        </select>
        <select name="order">
            <py:for each="option in ['ascending','descending']">
                 <option py:if="option == order" value="${option}" SELECTED="SELECTED">${option}</option>
                 <option py:if="option != order" value="${option}">${option}</option>
            </py:for>
        </select>
        <input id="go" type="submit" value="Search"/>
        </form>
        </div>
        <div class="navigation">
        <span style="display: block; text-align: center;">Books ${start} to ${ min((start+num-1) , total) } of ${total}</span>
        <table class="buttons">
        <tr>
        <td class="button" style="text-align:left;">
			<a py:if="start > 1" href="${url_base};start=1">First</a>
			<a py:if="start > 1" href="${url_base};start=${max(start-(num+1),1)}">Previous</a>
		</td>
        <td class="button" style="text-align: right;">
            <a py:if=" total > (start + num) " href="${url_base};start=${start+num}">Next</a>
            <a py:if=" total > (start + num) " href="${url_base};start=${total-num+1}">Last</a>
        </td>
        </tr>
        </table>
        </div>
        <hr class="spacer" />
        <table id="listing">
            <py:for each="book in books">
                ${Markup(book)}
            </py:for>
        </table>
    </body>
    </html>
    '''))

    LIBRARY = MarkupTemplate(textwrap.dedent('''\
    <?xml version="1.0" encoding="utf-8"?>
    <library xmlns:py="http://genshi.edgewall.org/" start="$start" num="${len(books)}" total="$total" updated="${updated.strftime('%Y-%m-%dT%H:%M:%S+00:00')}">
    <py:for each="book in books">
        ${Markup(book)}
    </py:for>
    </library>
    '''))

    STANZA_ENTRY=MarkupTemplate(textwrap.dedent('''\
    <entry xmlns:py="http://genshi.edgewall.org/">
        <title>${record[FM['title']]}</title>
        <id>urn:calibre:${record[FM['id']]}</id>
        <author><name>${authors}</name></author>
        <updated>${timestamp}</updated>
        <link type="${mimetype}" href="/get/${fmt}/${record[FM['id']]}" />
        <link rel="x-stanza-cover-image" type="image/jpeg" href="/get/cover/${record[FM['id']]}" />
        <link rel="x-stanza-cover-image-thumbnail" type="image/jpeg" href="/get/thumb/${record[FM['id']]}" />
        <content type="xhtml">
          <div xmlns="http://www.w3.org/1999/xhtml" style="text-align: center">${Markup(extra)}${record[FM['comments']]}</div>
        </content>
    </entry>
    '''))

    STANZA_SUBCATALOG_ENTRY=MarkupTemplate(textwrap.dedent('''\
    <entry xmlns:py="http://genshi.edgewall.org/">
        <title>${title}</title>
        <id>urn:calibre:${id}</id>
        <updated>${updated.strftime('%Y-%m-%dT%H:%M:%S+00:00')}</updated>
        <link type="application/atom+xml" href="/stanza/?${what}id=${id}" />
        <content type="text">${count} books</content>
    </entry>
    '''))

    STANZA = MarkupTemplate(textwrap.dedent('''\
    <?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:py="http://genshi.edgewall.org/">
      <title>calibre Library</title>
      <id>$id</id>
      <updated>${updated.strftime('%Y-%m-%dT%H:%M:%S+00:00')}</updated>
      <link rel="search" title="Search" type="application/atom+xml" href="/stanza/?search={searchTerms}"/>
      ${Markup(next_link)}
      <author>
        <name>calibre</name>
        <uri>http://calibre.kovidgoyal.net</uri>
      </author>
      <subtitle>
            ${subtitle}
      </subtitle>
      <py:for each="entry in data">
      ${Markup(entry)}
      </py:for>
    </feed>
    '''))

    STANZA_MAIN = MarkupTemplate(textwrap.dedent('''\
    <?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:py="http://genshi.edgewall.org/">
      <title>calibre Library</title>
      <id>$id</id>
      <updated>${updated.strftime('%Y-%m-%dT%H:%M:%S+00:00')}</updated>
      <link rel="search" title="Search" type="application/atom+xml" href="/stanza/?search={searchTerms}"/>
      <author>
        <name>calibre</name>
        <uri>http://calibre.kovidgoyal.net</uri>
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
    '''))


    def __init__(self, db, opts, embedded=False, show_tracebacks=True):
        self.db = db
        for item in self.db:
            item
            break
        self.opts = opts
        self.max_cover_width, self.max_cover_height = \
                        map(int, self.opts.max_cover.split('x'))
        self.max_stanza_items = opts.max_opds_items
        path = P('content_server')
        self.build_time = datetime.fromtimestamp(os.stat(path).st_mtime)
        self.default_cover =  open(P('content_server/default_cover.jpg'), 'rb').read()

        cherrypy.config.update({
                                'log.screen'             : opts.develop,
                                'engine.autoreload_on'   : opts.develop,
                                'tools.log_headers.on'   : opts.develop,
                                'checker.on'             : opts.develop,
                                'request.show_tracebacks': show_tracebacks,
                                'server.socket_host'     : '0.0.0.0',
                                'server.socket_port'     : opts.port,
                                'server.socket_timeout'  : opts.timeout, #seconds
                                'server.thread_pool'     : opts.thread_pool, # number of threads
                               })
        if embedded:
            cherrypy.config.update({'engine.SIGHUP'          : None,
                                    'engine.SIGTERM'         : None,})
        self.config = {'global': {
            'tools.gzip.on'        : True,
            'tools.gzip.mime_types': ['text/html', 'text/plain', 'text/xml', 'text/javascript', 'text/css'],
        }}
        if opts.password:
            self.config['/'] = {
                      'tools.digest_auth.on'    : True,
                      'tools.digest_auth.realm' : (_('Password to access your calibre library. Username is ') + opts.username.strip()).encode('ascii', 'replace'),
                      'tools.digest_auth.users' : {opts.username.strip():opts.password.strip()},
                      }

        self.is_running = False
        self.exception = None

    def setup_loggers(self):
        access_file = log_access_file
        error_file  = log_error_file
        log = cherrypy.log

        maxBytes = getattr(log, "rot_maxBytes", 10000000)
        backupCount = getattr(log, "rot_backupCount", 1000)

        # Make a new RotatingFileHandler for the error log.
        h = RotatingFileHandler(error_file, 'a', maxBytes, backupCount)
        h.setLevel(logging.DEBUG)
        h.setFormatter(cherrypy._cplogging.logfmt)
        log.error_log.addHandler(h)

        # Make a new RotatingFileHandler for the access log.
        h = RotatingFileHandler(access_file, 'a', maxBytes, backupCount)
        h.setLevel(logging.DEBUG)
        h.setFormatter(cherrypy._cplogging.logfmt)
        log.access_log.addHandler(h)


    def start(self):
        self.is_running = False
        self.setup_loggers()
        cherrypy.tree.mount(self, '', config=self.config)
        try:
            cherrypy.engine.start()
            self.is_running = True
            publish_zeroconf('Books in calibre', '_stanza._tcp',
                             self.opts.port, {'path':'/stanza'})
            cherrypy.engine.block()
        except Exception, e:
            self.exception = e
        finally:
            self.is_running = False
            stop_zeroconf()

    def exit(self):
        cherrypy.engine.exit()

    def get_cover(self, id, thumbnail=False):
        cover = self.db.cover(id, index_is_id=True, as_file=False)
        if cover is None:
            cover = self.default_cover
        cherrypy.response.headers['Content-Type'] = 'image/jpeg'
        cherrypy.response.timeout = 3600
        path = getattr(cover, 'name', False)
        updated = datetime.utcfromtimestamp(os.stat(path).st_mtime) if path and \
            os.access(path, os.R_OK) else self.build_time
        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        try:
            f = cStringIO.StringIO(cover)
            try:
                im = PILImage.open(f)
            except IOError:
                raise cherrypy.HTTPError(404, 'No valid cover found')
            width, height = im.size
            scaled, width, height = fit_image(width, height,
                60 if thumbnail else self.max_cover_width,
                80 if thumbnail else self.max_cover_height)
            if not scaled:
                return cover
            im = im.resize((int(width), int(height)), PILImage.ANTIALIAS)
            of = cStringIO.StringIO()
            im.convert('RGB').save(of, 'JPEG')
            return of.getvalue()
        except Exception, err:
            import traceback
            traceback.print_exc()
            raise cherrypy.HTTPError(404, 'Failed to generate cover: %s'%err)

    def get_format(self, id, format):
        format = format.upper()
        fmt = self.db.format(id, format, index_is_id=True, as_file=True,
                mode='rb')
        if fmt is None:
            raise cherrypy.HTTPError(404, 'book: %d does not have format: %s'%(id, format))
        if format == 'EPUB':
            from tempfile import TemporaryFile
            from calibre.ebooks.metadata.meta import set_metadata
            raw = fmt.read()
            fmt = TemporaryFile()
            fmt.write(raw)
            fmt.seek(0)
            set_metadata(fmt, self.db.get_metadata(id, index_is_id=True),
                    'epub')
            fmt.seek(0)
        mt = guess_type('dummy.'+format.lower())[0]
        if mt is None:
            mt = 'application/octet-stream'
        cherrypy.response.headers['Content-Type'] = mt
        cherrypy.response.timeout = 3600
        path = getattr(fmt, 'name', None)
        if path and os.path.exists(path):
            updated = datetime.utcfromtimestamp(os.stat(path).st_mtime)
            cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        return fmt.read()

    def sort(self, items, field, order):
        field = field.lower().strip()
        if field == 'author':
            field = 'authors'
        if field == 'date':
            field = 'timestamp'
        if field not in ('title', 'authors', 'rating', 'timestamp', 'tags', 'size', 'series'):
            raise cherrypy.HTTPError(400, '%s is not a valid sort field'%field)
        cmpf = cmp if field in ('rating', 'size', 'timestamp') else \
                lambda x, y: cmp(x.lower() if x else '', y.lower() if y else '')
        if field == 'series':
            items.sort(cmp=self.seriescmp, reverse=not order)
        else:
            field = FIELD_MAP[field]
            getter = operator.itemgetter(field)
            items.sort(cmp=lambda x, y: cmpf(getter(x), getter(y)), reverse=not order)

    def seriescmp(self, x, y):
        si = FIELD_MAP['series']
        try:
            ans = cmp(x[si].lower(), y[si].lower())
        except AttributeError: # Some entries may be None
            ans = cmp(x[si], y[si])
        if ans != 0: return ans
        return cmp(x[FIELD_MAP['series_index']], y[FIELD_MAP['series_index']])


    def last_modified(self, updated):
        lm = updated.strftime('day, %d month %Y %H:%M:%S GMT')
        day ={0:'Sun', 1:'Mon', 2:'Tue', 3:'Wed', 4:'Thu', 5:'Fri', 6:'Sat'}
        lm = lm.replace('day', day[int(updated.strftime('%w'))])
        month = {1:'Jan', 2:'Feb', 3:'Mar', 4:'Apr', 5:'May', 6:'Jun', 7:'Jul',
                 8:'Aug', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dec'}
        return lm.replace('month', month[updated.month])

    def get_matches(self, location, query):
        base = self.db.data.get_matches(location, query)
        epub = self.db.data.get_matches('format', 'epub')
        pdb = self.db.data.get_matches('format', 'pdb')
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
            data = [(x[0], x[1], len(self.get_matches('series', x[1]))) for x in data]
            subtitle = 'Books by series'
        elif sortby == 'byauthor':
            data = self.db.all_authors()
            data = [(x[0], x[1], len(self.get_matches('authors', x[1]))) for x in data]
            subtitle = 'Books by author'
        elif sortby == 'bytag':
            data = self.db.all_tags2()
            data = [(x[0], x[1], len(self.get_matches('tags', x[1]))) for x in data]
            subtitle = 'Books by tag'
        fcmp = author_cmp if sortby == 'byauthor' else cmp
        data = [x for x in data if x[2] > 0]
        data.sort(cmp=lambda x, y: fcmp(x[1], y[1]))
        next_offset = offset + self.max_stanza_items
        rdata = data[offset:next_offset]
        if next_offset >= len(data):
            next_offset = -1
        gt = get_author if sortby == 'byauthor' else lambda x: x
        entries = [self.STANZA_SUBCATALOG_ENTRY.generate(title=gt(title), id=id,
            what=what, updated=updated, count=c).render('xml').decode('utf-8') for id,
            title, c in rdata]
        next_link = ''
        if next_offset > -1:
            next_link = ('<link rel="next" title="Next" '
            'type="application/atom+xml" href="/stanza/?sortby=%s&amp;offset=%d"/>\n'
            ) % (sortby, next_offset)
        return self.STANZA.generate(subtitle=subtitle, data=entries, FM=FIELD_MAP,
                    updated=updated, id='urn:calibre:main', next_link=next_link).render('xml')

    def stanza_main(self, updated):
        return self.STANZA_MAIN.generate(subtitle='', data=[], FM=FIELD_MAP,
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

        # Sort the record list
        if sortby == "bytitle" or authorid or tagid:
            record_list.sort(lambda x, y: cmp(title_sort(x[FIELD_MAP['title']]),
                title_sort(y[FIELD_MAP['title']])))
        elif seriesid:
            record_list.sort(lambda x, y: cmp(x[FIELD_MAP['series_index']], y[FIELD_MAP['series_index']]))
        else: # Sort by date
            record_list = reversed(record_list)


        fmts = FIELD_MAP['formats']
        pat = re.compile(r'EPUB|PDB', re.IGNORECASE)
        record_list = [x for x in record_list if x[0] in ids and
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

        author_list=[]
        tag_list=[]
        series_list=[]

        for record in nrecord_list:
            r = record[FIELD_MAP['formats']]
            r = r.upper() if r else ''

            z = record[FIELD_MAP['authors']]
            if not z:
                z = _('Unknown')
            authors = ' & '.join([i.replace('|', ',') for i in
                                    z.split(',')])

            # Setup extra description
            extra = []
            rating = record[FIELD_MAP['rating']]
            if rating > 0:
                rating = ''.join(repeat('&#9733;', rating))
                extra.append('RATING: %s<br />'%rating)
            tags = record[FIELD_MAP['tags']]
            if tags:
                extra.append('TAGS: %s<br />'%\
                        prepare_string_for_xml(', '.join(tags.split(','))))
            series = record[FIELD_MAP['series']]
            if series:
                extra.append('SERIES: %s [%s]<br />'%\
                        (prepare_string_for_xml(series),
                        fmt_sidx(float(record[FIELD_MAP['series_index']]))))

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
                    FM=FIELD_MAP,
                    extra='\n'.join(extra),
                    mimetype=mimetype,
                    fmt=fmt,
                    timestamp=strftime('%Y-%m-%dT%H:%M:%S+00:00', record[5])
                    )
            books.append(self.STANZA_ENTRY.generate(**data)\
                                        .render('xml').decode('utf8'))

        return self.STANZA.generate(subtitle='', data=books, FM=FIELD_MAP,
                next_link=next_link, updated=updated, id='urn:calibre:main').render('xml')


    @expose
    def mobile(self, start='1', num='25', sort='date', search='',
                _=None, order='descending'):
        '''
        Serves metadata from the calibre database as XML.

        :param sort: Sort results by ``sort``. Can be one of `title,author,rating`.
        :param search: Filter results by ``search`` query. See :class:`SearchQueryParser` for query syntax
        :param start,num: Return the slice `[start:start+num]` of the sorted and filtered results
        :param _: Firefox seems to sometimes send this when using XMLHttpRequest with no caching
        '''
        try:
            start = int(start)
        except ValueError:
            raise cherrypy.HTTPError(400, 'start: %s is not an integer'%start)
        try:
            num = int(num)
        except ValueError:
            raise cherrypy.HTTPError(400, 'num: %s is not an integer'%num)
        ids = self.db.data.parse(search) if search and search.strip() else self.db.data.universal_set()
        ids = sorted(ids)
        items = [r for r in iter(self.db) if r[0] in ids]
        if sort is not None:
            self.sort(items, sort, (order.lower().strip() == 'ascending'))

        book, books = MarkupTemplate(self.MOBILE_BOOK), []
        for record in items[(start-1):(start-1)+num]:
            aus = record[2] if record[2] else __builtin__._('Unknown')
            authors = '|'.join([i.replace('|', ',') for i in aus.split(',')])
            record[10] = fmt_sidx(float(record[10]))
            ts, pd = strftime('%Y/%m/%d %H:%M:%S', record[5]), \
                strftime('%Y/%m/%d %H:%M:%S', record[FIELD_MAP['pubdate']])
            books.append(book.generate(r=record, authors=authors, timestamp=ts,
                pubdate=pd).render('xml').decode('utf-8'))
        updated = self.db.last_modified()

        cherrypy.response.headers['Content-Type'] = 'text/html; charset=utf-8'
        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)


        url_base = "/mobile?search=" + search+";order="+order+";sort="+sort+";num="+str(num)

        return self.MOBILE.generate(books=books, start=start, updated=updated, search=search, sort=sort, order=order, num=num,
                                     total=len(ids), url_base=url_base).render('html')


    @expose
    def library(self, start='0', num='50', sort=None, search=None,
                _=None, order='ascending'):
        '''
        Serves metadata from the calibre database as XML.

        :param sort: Sort results by ``sort``. Can be one of `title,author,rating`.
        :param search: Filter results by ``search`` query. See :class:`SearchQueryParser` for query syntax
        :param start,num: Return the slice `[start:start+num]` of the sorted and filtered results
        :param _: Firefox seems to sometimes send this when using XMLHttpRequest with no caching
        '''
        try:
            start = int(start)
        except ValueError:
            raise cherrypy.HTTPError(400, 'start: %s is not an integer'%start)
        try:
            num = int(num)
        except ValueError:
            raise cherrypy.HTTPError(400, 'num: %s is not an integer'%num)
        order = order.lower().strip() == 'ascending'
        ids = self.db.data.parse(search) if search and search.strip() else self.db.data.universal_set()
        ids = sorted(ids)
        items = [r for r in iter(self.db) if r[0] in ids]
        if sort is not None:
            self.sort(items, sort, order)

        book, books = MarkupTemplate(self.BOOK), []
        for record in items[start:start+num]:
            aus = record[2] if record[2] else __builtin__._('Unknown')
            authors = '|'.join([i.replace('|', ',') for i in aus.split(',')])
            record[10] = fmt_sidx(float(record[10]))
            ts, pd = strftime('%Y/%m/%d %H:%M:%S', record[5]), \
                strftime('%Y/%m/%d %H:%M:%S', record[FIELD_MAP['pubdate']])
            books.append(book.generate(r=record, authors=authors, timestamp=ts,
                pubdate=pd).render('xml').decode('utf-8'))
        updated = self.db.last_modified()

        cherrypy.response.headers['Content-Type'] = 'text/xml'
        cherrypy.response.headers['Last-Modified'] = self.last_modified(updated)
        return self.LIBRARY.generate(books=books, start=start, updated=updated,
                                     total=len(ids)).render('xml')

    @expose
    def index(self, **kwargs):
        'The / URL'
        ua = cherrypy.request.headers.get('User-Agent', '').strip()
        want_opds = \
            cherrypy.request.headers.get('Stanza-Device-Name', 919) != 919 or \
            cherrypy.request.headers.get('Want-OPDS-Catalog', 919) != 919 or \
            ua.startswith('Stanza')

        # A better search would be great
        want_mobile = self.MOBILE_UA.search(ua) is not None
        if self.opts.develop and not want_mobile:
            prints('User agent:', ua)

        if want_opds:
            return self.stanza(search=kwargs.get('search', None), sortby=kwargs.get('sortby',None), authorid=kwargs.get('authorid',None),
                           tagid=kwargs.get('tagid',None),
                           seriesid=kwargs.get('seriesid',None),
                           offset=kwargs.get('offset', 0))

        if want_mobile:
            return self.mobile()

        return self.static('index.html')


    @expose
    def get(self, what, id):
        'Serves files, covers, thumbnails from the calibre database'
        try:
            id = int(id)
        except ValueError:
            id = id.rpartition('_')[-1].partition('.')[0]
            match = re.search(r'\d+', id)
            if not match:
                raise cherrypy.HTTPError(400, 'id:%s not an integer'%id)
            id = int(match.group())
        if not self.db.has_id(id):
            raise cherrypy.HTTPError(400, 'id:%d does not exist in database'%id)
        if what == 'thumb':
            return self.get_cover(id, thumbnail=True)
        if what == 'cover':
            return self.get_cover(id)
        return self.get_format(id, what)

    @expose
    def static(self, name):
        'Serves static content'
        name = name.lower()
        cherrypy.response.headers['Content-Type'] = {
                     'js'   : 'text/javascript',
                     'css'  : 'text/css',
                     'png'  : 'image/png',
                     'gif'  : 'image/gif',
                     'html' : 'text/html',
                     ''      : 'application/octet-stream',
                     }[name.rpartition('.')[-1].lower()]
        cherrypy.response.headers['Last-Modified'] = self.last_modified(self.build_time)
        path = P('content_server/'+name)
        if not os.path.exists(path):
            raise cherrypy.HTTPError(404, '%s not found'%name)
        if self.opts.develop:
            lm = datetime.fromtimestamp(os.stat(path).st_mtime)
            cherrypy.response.headers['Last-Modified'] = self.last_modified(lm)
        return open(path, 'rb').read()

def start_threaded_server(db, opts):
    server = LibraryServer(db, opts, embedded=True)
    server.thread = Thread(target=server.start)
    server.thread.setDaemon(True)
    server.thread.start()
    return server

def stop_threaded_server(server):
    server.exit()
    server.thread = None

def option_parser():
    return config().option_parser('%prog '+ _('[options]\n\nStart the calibre content server.'))

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    cherrypy.log.screen = True
    from calibre.utils.config import prefs
    db = LibraryDatabase2(prefs['library_path'])
    server = LibraryServer(db, opts)
    server.start()
    return 0

if __name__ == '__main__':
    sys.exit(main())
