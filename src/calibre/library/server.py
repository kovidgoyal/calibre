#!/usr/bin/env  python
__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal kovid@kovidgoyal.net'
__docformat__ = 'restructuredtext en'

'''
HTTP server for remote access to the calibre database.
'''

import sys
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler

from calibre.constants import __version__

class Server(HTTPServer):
    pass

class DBHandler(BaseHTTPRequestHandler):
    
    server_version = 'calibre/'+__version__
    
    def set_db(self, db):
        self.db = db
        
    
def server(db, port=80):
    server = Server(('', port), DBHandler)

def main(args=sys.argv):
    from calibre.utils.config import prefs
    from calibre.library.database2 import LibraryDatabase2
    db = LibraryDatabase2(prefs['library_path'])
    try:
        print 'Starting server...'
        s = server()
        s.server_forever()
    except KeyboardInterrupt:
        print 'Server interrupted'
        s.socket.close()
    return 0

if __name__ == '__main__':
    sys.exit(main())