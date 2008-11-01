#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
HTTP server for remote access to the calibre database.
'''

import sys, textwrap, cStringIO, mimetypes
import cherrypy
from PIL import Image

from calibre.constants import __version__, __appname__
from calibre.utils.config import StringConfig, Config
from calibre.utils.genshi.template import MarkupTemplate
from calibre import fit_image

def expose(func):
    
    def do(self, *args, **kwargs):
        dict.update(cherrypy.response.headers, {'Server':self.server_name})
        return func(self, *args, **kwargs)
    
    return cherrypy.expose(do)

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
            timestamp="${timestamp.ctime()}" 
            size="${r[6]}" 
            isbn="${r[14] if r[14] else ''}"
            formats="${r[13] if r[13] else ''}"
            series = "${r[9] if r[9] else ''}"
            series_index="${r[10]}"
            tags="${r[7] if r[7] else ''}"
            publisher="${r[3] if r[3] else ''}">${r[8] if r[8] else ''}</book>
        ''')
    
    LIBRARY = MarkupTemplate(textwrap.dedent('''\
    <?xml version="1.0" encoding="utf-8"?>
    <library xmlns:py="http://genshi.edgewall.org/" size="${len(books)}">
    <py:for each="book in books">
    ${Markup(book)}
    </py:for>
    </library>
    '''))
    
    STANZA_ENTRY=MarkupTemplate(textwrap.dedent('''\
    <entry xmlns:py="http://genshi.edgewall.org/">
        <title>${record['title']}</title>
        <id>urn:calibre:${record['id']}</id>
        <author><name>${authors}</name></author>
        <updated>${record['timestamp'].strftime('%Y-%m-%dT%H:%M:%S+0000')}</updated>
        <link type="application/epub+zip" href="http://${server}:${port}/get/epub/${record['id']}" />
        <link rel="x-stanza-cover-image" type="image/jpeg" href="http://${server}:${port}/get/cover/${record['id']}" />
        <link rel="x-stanza-cover-image-thumbnail" type="image/jpeg" href="http://${server}:${port}/get/thumb/${record['id']}" />
        <content py:if="record['comments']" type="xhtml">
          <pre>${record['comments']}</pre>
        </content>
    </entry>
    '''))
    
    STANZA = MarkupTemplate(textwrap.dedent('''\
    <?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom" xmlns:py="http://genshi.edgewall.org/">
      <title>calibre Library</title>
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

    
    def __init__(self, db, opts):
        self.db = db
        for item in self.db:
            item
            break
        self.opts = opts
        cherrypy.config.update({
                                'server.socket_port': opts.port,
                                'server.socket_timeout': opts.timeout, #seconds
                                'server.thread_pool': opts.thread_pool, # number of threads
                               })
        self.config = textwrap.dedent('''\
        [global]
        engine.autoreload_on = %(autoreload)s
        tools.gzip.on = True
        tools.gzip.mime_types = ['text/html', 'text/plain', 'text/xml']
        ''')%dict(autoreload=opts.develop)
        
    def to_xml(self):
        books = []
        book = MarkupTemplate(self.BOOK)
        for record in iter(self.db):
            authors = ' & '.join([i.replace('|', ',') for i in record[2].split(',')])
            books.append(book.generate(r=record, authors=authors).render('xml').decode('utf-8'))
        return self.LIBRARY.generate(books=books).render('xml')
    
    def start(self):
        cherrypy.quickstart(self, config=cStringIO.StringIO(self.config))
    
    def get_cover(self, id, thumbnail=False):
        cover = self.db.cover(id, index_is_id=True, as_file=True)
        if cover is None:
            raise cherrypy.HTTPError(404, 'no cover available for id: %d'%id)
        cherrypy.response.headers['Content-Type'] = 'image/jpeg'
        if not thumbnail:
            return cover.read()
        try:
            im = Image.open(cover)
            width, height = im.size
            scaled, width, height = fit_image(width, height, 80, 60)
            if not scaled:
                return cover.read()
            im.thumbnail((width, height))
            o = cStringIO.StringIO()
            im.save(o, 'JPEG')
            return o.getvalue()
        except Exception, err:
            raise cherrypy.HTTPError(404, 'failed to generate thumbnail: %s'%err)
        
    def get_format(self, id, format):
        format = format.upper()
        fmt = self.db.format(id, format, index_is_id=True)
        if fmt is None:
            raise cherrypy.HTTPError(404, 'book: %d does not have format: %s'%(id, format))
        mt = mimetypes.guess_type('dummy.'+format.lower())[0]
        if mt is None:
            mt = 'application/octet-stream'
        cherrypy.response.headers['Content-Type'] = mt
        return fmt
        
    @expose
    def stanza(self):
        cherrypy.response.headers['Content-Type'] = 'text/xml'
        books = []
        for record in iter(self.db):
            authors = ' & '.join([i.replace('|', ',') for i in record[2].split(',')])
            books.append(self.STANZA_ENTRY.generate(authors=authors, 
                                                    record=record,
                                                    port=self.opts.port, 
                                                    server=self.opts.hostname,
                                                    ).render('xml').decode('utf8'))
        return self.STANZA.generate(subtitle='', data=books).render('xml')
    
    @expose
    def library(self):
        cherrypy.response.headers['Content-Type'] = 'text/xml'
        return self.to_xml()
    
    @expose
    def index(self):
        return 'Hello, World!'
    
    @expose
    def get(self, what, id):
        try:
            id = int(id)
        except ValueError:
            raise cherrypy.HTTPError(400, 'id:%s not an integer'%id)
        if not self.db.has_id(id):
            raise cherrypy.HTTPError(400, 'id:%d does not exist in database'%id)
        if what == 'thumb':
            return self.get_cover(id, thumbnail=True)
        if what == 'cover':
            return self.get_cover(id)
        return self.get_format(id, what)
    
def config(defaults=None):
    desc=_('Settings to control the calibre content server')
    c = Config('server', desc) if defaults is None else StringConfig(defaults, desc)
    
    c.add_opt('port', ['-p', '--port'], default=8080, 
              help=_('The port on which to listen. Default is %default'))
    c.add_opt('timeout', ['-t', '--timeout'], default=120, 
              help=_('The server timeout in seconds. Default is %default'))
    c.add_opt('thread_pool', ['--thread-pool'], default=30, 
              help=_('The max number of worker threads to use. Default is %default'))
    c.add_opt('hostname', ['--hostname'], default='localhost', 
              help=_('The hostname of the machine the server is running on. Used when generating the stanza feeds. Default is %default'))
    
    c.add_opt('develop', ['--develop'], default=False,
              help='Development mode. Server automatically restarts on file changes.')
    return c

def option_parser():
    return config().option_parser('%prog '+ _('[options]\n\nStart the calibre content server.'))

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    cherrypy.log.screen = True
    from calibre.utils.config import prefs
    from calibre.library.database2 import LibraryDatabase2
    db = LibraryDatabase2(prefs['library_path'], row_factory=True)
    server = LibraryServer(db, opts)
    server.start()
    return 0

if __name__ == '__main__':
    sys.exit(main())