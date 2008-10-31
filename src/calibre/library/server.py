#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
HTTP server for remote access to the calibre database.
'''

import sys, logging
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

from calibre.constants import __version__
from calibre.utils.config import StringConfig, Config

class Server(HTTPServer):
    pass

class DBHandler(BaseHTTPRequestHandler):
    
    server_version = 'calibre/'+__version__
    
    def set_db(self, db):
        self.db = db
        self.l  = logging.getLogger('calibre.server')
        self.l.info('calibre-server starting...') 
        
    
def server(db, opts):
    return  Server(('', opts.port), DBHandler)

def config(defaults=None):
    desc=_('Settings to control the calibre content server')
    c = Config('server', desc) if defaults is None else StringConfig(defaults, desc)
    
    c.add_opt('port', ['-p', '--port'], default=8080, 
              help=_('The port on which to listen. Default is %default'))
    return c

def option_parser():
    return config().option_parser('%prog '+ _('[options]\n\nStart the calibre content server.'))

def main(args=sys.argv):
    parser = option_parser()
    opts, args = parser.parse_args(args)
    
    from calibre.utils.config import prefs
    from calibre.library.database2 import LibraryDatabase2
    db = LibraryDatabase2(prefs['library_path'])
    try:
        print 'Starting server...'
        s = server(db, opts)
        s.serve_forever()
    except KeyboardInterrupt:
        print 'Server interrupted'
        s.socket.close()
    return 0

if __name__ == '__main__':
    sys.exit(main())