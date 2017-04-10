#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2011, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'''
Utilities to help with developing coffeescript based apps.
A coffeescript compiler and a simple web server that automatically serves
coffeescript files as javascript.
'''
import sys, traceback, io
if sys.version_info.major > 2:
    print('This script is not Python 3 compatible. Run it with Python 2',
            file=sys.stderr)
    raise SystemExit(1)

import time, BaseHTTPServer, os, sys, re, SocketServer
from threading import Lock, local
from SimpleHTTPServer import SimpleHTTPRequestHandler

# Compiler {{{

tls = local()


def compiler():
    ans = getattr(tls, 'compiler', None)
    if ans is None:
        from duktape import Context
        c = tls.compiler = Context()
        c.eval(P('coffee-script.js', data=True).decode('utf-8'))
    return tls.compiler


def compile_coffeescript(raw, filename=None):
    from duktape import JSError
    jc = compiler()
    jc.g.src = raw
    try:
        ans = compiler().eval('CoffeeScript.compile(src)')
    except JSError as e:
        return u'', (e.message,)
    return ans, ()

# }}}


def check_coffeescript(filename):
    with open(filename, 'rb') as f:
        raw = f.read()
    cs, errs = compile_coffeescript(raw, filename)
    if errs:
        print('\n'.join(errs))
        raise Exception('Compilation failed')


class HTTPRequestHandler(SimpleHTTPRequestHandler):  # {{{

    '''
    Handle Range headers, as browsers insist on using range for <video> tags.
    Note: Range header is ignored when listing directories.
    '''

    server_version = "TestHTTP/1"
    protocol_version = 'HTTP/1.1'
    extensions_map = SimpleHTTPRequestHandler.extensions_map.copy()
    extensions_map.update({
        '': 'application/octet-stream',  # Default
        '.py': 'text/plain',
        '.c': 'text/plain',
        '.h': 'text/plain',
        '.mp4' : 'video/mp4',
        '.ogg' : 'video/ogg',
        '.webm': 'video/webm',
    })
    # FAVICON {{{
    FAVICON = b'\x00\x00\x01\x00\x01\x00\x10\x10\x00\x00\x00\x00\x00\x00h\x05\x00\x00\x16\x00\x00\x00(\x00\x00\x00\x10\x00\x00\x00 \x00\x00\x00\x01\x00\x08\x00\x00\x00\x00\x00@\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff\xff\x00(4\xdd\x00RWX\x00\x00\x00w\x00\x05N[\x00a`\xf1\x00.|\x8a\x00\x03\x03\xb7\x00\x1c)-\x00-,`\x00\x03\x02F\x00  \xbb\x00\x13\x13\x92\x00\x16\x16\xdc\x00\x08\x07!\x00\x17\x12d\x00:GJ\x00@?k\x00% w\x00\x01\x01\x9b\x00\x07\x03\xd2\x00\x01\x00[\x00\x12\x17\x18\x00\x11\x111\x00,,\xcb\x007M`\x00\x0e\x0e\xa4\x00\n\n\x83\x00#+R\x00"!\xe1\x00\x1f\x1aX\x00\x14\x14\xb2\x00\x0b\rO\x00\n\nq\x00\x08\x08\x92\x0032\xd6\x00))\xbc\x00\x08\x08<\x00\x11+2\x00\x02\x02\x86\x00%#l\x001E[\x00#"\xc5\x00\x15\x15\x9c\x00\r\r\x99\x00\x0f\x0f<\x00#"\\\x00\x1c\x1b\xe1\x00\n\t)\x00\x14\x1d\xd8\x00\x1f\x1fp\x00\x07\x07x\x00\x02\x02N\x00\x17.5\x00\x05\x05Y\x00\x01\x00T\x00\x1f\x1ew\x00\x06\x06~\x00\x0b\x0b\x1e\x00\x00\x00\xb3\x00\x08\tL\x00\x01\x01r\x00\x0b\x109\x00&&\xbe\x00\x04\x04\x89\x00\n\x05\xd2\x00\x08\x08\x81\x00\x03\x03\x9c\x00\x02\x02\xb5\x00\x02\x02[\x00\r\r\xa3\x00\x02\x02\x85\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x007\x0b\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x16F58\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x0f\x04(H>1\x00\x00\x00\x00\x00\x00\x00\x00\x009A<E\x08\x14C3\x00\x00\x00\x00\x00\x00\x00\x00@4&D:;\x1c%\x00\x00\x00\x00\x00\x00\x00\x00+".\x1b\r\x18#\x0c\x00\x00\x00\x00\x00\x00\x00\x00/G\x1e\x19$\x0e-)\x00\x00\x00\x00\x00\x00\x00\x00\x1f \x06\x12\n0,\x13\x00\x00\x00\x00\x00\x00\x00\x00\x10\x15\x02\x1a*2B\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00!\x1d\x11\t?=\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x07\x03\x17\x05\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x006\'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xff\x00\x00\xfe\x7f\x00\x00\xfc?\x00\x00\xf8\x1f\x00\x00\xf0\x0f\x00\x00\xf0\x0f\x00\x00\xf0\x0f\x00\x00\xf0\x0f\x00\x00\xf0\x0f\x00\x00\xf0\x1f\x00\x00\xf8\x1f\x00\x00\xfc?\x00\x00\xfe\x7f\x00\x00\xff\xff\x00\x00\xff\xff\x00\x00\xff\xff\x00\x00'  # noqa
    # }}}

    def parse_range_header(self, size):
        start_range = 0
        end_range = -1
        rtype = 206 if 'Range' in self.headers else 200

        if "Range" in self.headers:
            s, e = self.headers['range'][6:].split('-', 1)
            sl = len(s)
            el = len(e)
            if sl > 0:
                start_range = int(s)
                if el > 0:
                    end_range = int(e) + 1
            elif el > 0:
                ei = int(e)
                if ei < size:
                    start_range = size - ei
        return rtype, start_range, end_range

    def send_file(self, f, mimetype, mtime):
        f.seek(0, 2)
        size = f.tell()
        f.seek(0)
        rtype, start_range, end_range = self.parse_range_header(size)

        if end_range <= start_range:
            end_range = size
        self.send_response(rtype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", 'bytes ' +
                         str(start_range) + '-' + str(end_range - 1) + '/' + str(size))
        self.send_header("Content-Type", str(mimetype))
        self.send_header("Content-Length", str(end_range - start_range))
        self.send_header("Last-Modified", self.date_time_string(int(mtime)))
        self.end_headers()
        return f, start_range, end_range

    def send_bytes(self, raw, mimetype, mtime):
        return self.send_file(io.BytesIO(raw), mimetype, mtime)

    def do_GET(self):
        f, start_range, end_range = self.send_head()
        if f:
            with f:
                f.seek(start_range, 0)
                chunk = 0x1000
                total = 0
                while True:
                    if start_range + chunk > end_range:
                        chunk = end_range - start_range
                    if chunk < 1:
                        break
                    try:
                        self.wfile.write(f.read(chunk))
                    except:
                        break
                    total += chunk
                    start_range += chunk

    def do_HEAD(self):
        f, start_range, end_range = self.send_head()
        if f:
            f.close()

    def send_head(self):
        if self.path == '/favicon.ico':
            return self.send_bytes(self.FAVICON, 'image/x-icon', 1326214111.485359)

        path = self.translate_path(self.path)
        if os.path.isdir(path):
            if not self.path.endswith('/'):
                # redirect browser - doing basically what apache does
                self.send_response(301)
                self.send_header("Location", self.path + "/")
                self.end_headers()
                return (None, 0, 0)
            for index in "index.html", "index.htm":
                index = os.path.join(path, index)
                if os.path.exists(index):
                    path = index
                    break
            else:
                f = self.list_directory(path)
                f.seek(0, 2)
                sz = f.tell()
                f.seek(0)
                return (f, 0, sz)

        ctype = self.guess_type(path)
        try:
            f = open(path, 'rb')
        except IOError:
            self.send_error(404, "File not found")
            return (None, 0, 0)
        fs = os.fstat(f.fileno())
        return self.send_file(f, ctype, fs.st_mtime)
# }}}


class Handler(HTTPRequestHandler):  # {{{

    class NoCoffee(Exception):

        def __init__(self, src):
            Exception.__init__(self, src)
            self.src = src

    '''Server that dynamically compiles coffeescript to javascript and that can
    handle aliased resources.'''

    special_resources = {}
    compiled_cs = {}
    coffee_lock = Lock()

    def send_head(self):
        path = self.path
        if path.endswith('.coffee'):
            path = path[1:] if path.startswith('/') else path
            path = self.special_resources.get(path, path)
            try:
                raw, mtime = self.compile_coffeescript(path)
            except Handler.NoCoffee as e:
                self.send_error(404, "File not found: %s"%e.src)
                return (None, 0, 0)

            return self.send_bytes(raw, 'text/javascript', mtime)
        if path == '/favicon.ico':
            return self.send_bytes(self.FAVICON, 'image/x-icon', 1000.0)

        return HTTPRequestHandler.send_head(self)

    def translate_path(self, path):
        path = self.special_resources.get(path, path)
        if path.endswith('/jquery.js'):
            return P('viewer/jquery.js')

        return HTTPRequestHandler.translate_path(self, path)

    def newer(self, src, dest):
        try:
            sstat = os.stat(src)
        except:
            time.sleep(0.01)
            try:
                sstat = os.stat(src)
            except:
                raise Handler.NoCoffee(src)
        return sstat.st_mtime > dest

    def compile_coffeescript(self, src):
        with self.coffee_lock:
            raw, mtime = self.compiled_cs.get(src, (None, 0))
        if self.newer(src, mtime):
            mtime = time.time()
            with open(src, 'rb') as f:
                raw = f.read()
            cs, errors = self.compiler(raw, src)
            for line in errors:
                print(line, file=sys.stderr)
            if not cs:
                print('Compilation of %s failed'%src)
                cs = '''
                // Compilation of coffeescript failed
                alert("Compilation of %s failed");
                '''%src

            raw = cs.encode('utf-8')
            with self.coffee_lock:
                self.compiled_cs[src] = (raw, mtime)
        return raw, mtime

# }}}


class Server(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):  # {{{
    daemon_threads = True

    def handle_error(self, request, client_address):
        """Handle an error gracefully.  May be overridden.

        The default is to print a traceback and continue.

        """
        print ('-'*40)
        print ('Exception happened during processing of request', request)
        traceback.print_exc()  # XXX But this goes to stderr!
        print ('-'*40)
# }}}


def serve(resources={}, port=8000, host='0.0.0.0'):
    Handler.special_resources = resources
    Handler.compiler = compile_coffeescript
    httpd = Server((host, port), Handler)
    print('serving %s at %s:%d with PID=%d'%(os.getcwdu(), host, port, os.getpid()))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        raise SystemExit(0)


# CLI {{{
def main():
    import argparse
    ver = re.search(r'CoffeeScript Compiler v(.+)', open(P('coffee-script.js'), 'rb').read(500)).group(1)
    epilog='Copyright Kovid Goyal 2012'
    parser = argparse.ArgumentParser(description='''
            Serve up files under the current directory via HTTP, automatically
            compiling .coffee files to javascript. Can also be used as a
            simple coffeescript compiler.
            '''
            , epilog=epilog
    )
    parser.add_argument('--version', action='version',
            version='Using coffeescript compiler version: '+ver)
    subparsers = parser.add_subparsers(help='Compile or serve', dest='which',
            title='Compile or Serve', description='Compile or serve')
    cc = subparsers.add_parser('compile', help='Compile coffeescript',
            epilog=epilog)
    cs = subparsers.add_parser('serve', help='Serve files under the current '
            'directory, automatically compiling .coffee files to javascript',
            epilog=epilog)

    cc.add_argument('src', type=argparse.FileType('rb'),
            metavar='path/to/script.coffee', help='The coffee script to compile. Use '
            ' - for stdin')
    cc.add_argument('--highlight', default=False, action='store_true',
            help='Syntax highlight the output (requires Pygments)')

    cs.add_argument('--port', type=int, default=8000, help='The port on which to serve. Default: %default')
    cs.add_argument('--host', default='0.0.0.0', help='The IP address on which to listen. Default is to listen on all'
            ' IPv4 addresses (0.0.0.0)')
    args = parser.parse_args()
    if args.which == 'compile':
        ans, errors = compile_coffeescript(args.src.read(), filename=args.src.name)
        for line in errors:
            print(line, file=sys.stderr)
        if ans:
            if args.highlight:
                from pygments.lexers import JavascriptLexer
                from pygments.formatters import TerminalFormatter
                from pygments import highlight
                print (highlight(ans, JavascriptLexer(), TerminalFormatter()))
            else:
                print (ans.encode(sys.stdout.encoding or 'utf-8'))
    else:
        serve(port=args.port, host=args.host)


if __name__ == '__main__':
    main()
# }}}
