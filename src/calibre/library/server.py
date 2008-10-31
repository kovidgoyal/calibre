#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
HTTP server for remote access to the calibre database.
'''

import sys, logging, re, SocketServer, gzip, cStringIO
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

from calibre.constants import __version__
from calibre.utils.config import StringConfig, Config
from calibre import ColoredFormatter

class Server(SocketServer.ThreadingMixIn, HTTPServer):
    def __init__(self, opts, db):
        self.db = db
        HTTPServer.__init__(self, ('', opts.port), DBHandler)
    
    def serve_forever(self):
        logging.getLogger('calibre.server').info('calibre-server starting...')
        HTTPServer.serve_forever(self)
                            

class DBHandler(BaseHTTPRequestHandler):
    
    server_version = 'calibre/'+__version__
    protocol_version = 'HTTP/1.0'
    cover_request = re.compile(r'/(\d+)/cover', re.IGNORECASE)
    thumbnail_request = re.compile(r'/(\d+)/thumb', re.IGNORECASE)
    fmt_request   = re.compile(r'/(\d+)/([a-z0-9]+)', re.IGNORECASE)
      
    
    def __init__(self, request, client_address, server, *args, **kwargs):
        self.l = logging.getLogger('calibre.server')
        self.db = server.db
        BaseHTTPRequestHandler.__init__(self, request, client_address, server, *args, **kwargs)
        
    
    def log_message(self, fmt, *args):
        self.l.info("%s - - [%s] %s\n" %
                         (self.address_string(),
                          self.log_date_time_string(),
                          fmt%args))
        
    def log_error(self, fmt, *args):
        self.l.error("%s - - [%s] %s\n" %
                         (self.address_string(),
                          self.log_date_time_string(),
                          fmt%args))
        
    def do_GET(self):
        cover = self.cover_request.match(self.path)
        thumb = self.thumbnail_request.match(self.path)
        fmt   = self.fmt_request.match(self.path) 
        if self.path == '/':
            self.send_index()
        elif self.path == '/stanza.atom':
            self.send_stanza_index()
        elif self.path == '/library':
            self.send_library()
        elif thumb:
            self.send_cover(int(thumb.group(1)), thumbnail=True) 
        elif cover:
            self.send_cover(int(cover.group(1)))
        elif fmt:
            self.send_format(int(fmt.group(1)), fmt.group(2).upper())
        elif self.path == '/help':
            self.send_help()
            
        self.send_error(400, 'Bad request. Try /help for usage.')
        
    def compress(buf):
        zbuf = cStringIO.StringIO()
        zfile = gzip.GzipFile(mode = 'wb',  fileobj = zbuf, compresslevel = 9)
        zfile.write(buf)
        zfile.close()
        return zbuf.getvalue()

    
    def send_help(self):
        self.send_error(501, 'Not Implemented')
    
    def send_index(self):
        self.send_error(501, 'Not Implemented')
        
    def send_stanza_index(self):
        self.send_error(501, 'Not Implemented')
        
    def send_library(self):
        self.send_error(501, 'Not Implemented')
    
    def send_cover(self, id, thumbnail=False):
        self.send_error(501, 'Not Implemented')
        
    def send_format(self, id, fmt):
        self.send_error(501, 'Not Implemented')
    
def config(defaults=None):
    desc=_('Settings to control the calibre content server')
    c = Config('server', desc) if defaults is None else StringConfig(defaults, desc)
    
    c.add_opt('port', ['-p', '--port'], default=8080, 
              help=_('The port on which to listen. Default is %default'))
    c.add_opt('debug', ['--debug'], default=False,
              help=_('Detailed logging'))
    return c

def option_parser():
    return config().option_parser('%prog '+ _('[options]\n\nStart the calibre content server.'))

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    l = logging.getLogger('calibre.server')
    l.setLevel(logging.DEBUG if opts.debug else logging.INFO)
    l.addHandler(logging.StreamHandler(sys.stdout))
    l.handlers[-1].setLevel(logging.DEBUG if opts.debug else logging.INFO)
    formatter = ColoredFormatter('%(levelname)s: %(message)s')
    l.handlers[-1].setFormatter(formatter)
    
    from calibre.utils.config import prefs
    from calibre.library.database2 import LibraryDatabase2
    db = LibraryDatabase2(prefs['library_path'])
    try:
        print 'Starting server...'
        s = Server(opts, db)
        s.serve_forever()
    except KeyboardInterrupt:
        print 'Server interrupted'
        s.socket.close()
    return 0

if __name__ == '__main__':
    sys.exit(main())