#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import httplib, ssl, os, subprocess, time, socket
from unittest import skipIf, skipUnless

from calibre.constants import islinux
try:
    from calibre.utils.certgen import create_server_cert
except ImportError:
    create_server_cert = None


from calibre.srv.tests.base import BaseTest, TestServer
from calibre.ptempfile import TemporaryDirectory

SYSTEMD = '/usr/lib/systemd/systemd-activate'

class LoopTest(BaseTest):

    @skipIf(create_server_cert is None, 'certgen module not available')
    def test_ssl(self):
        'Test serving over SSL'
        with TestServer(lambda data:(data.path[0] + data.read())) as server:
            address = server.address[0]
        with TemporaryDirectory('srv-test-ssl') as tdir:
            cert_file, key_file, ca_file = map(lambda x:os.path.join(tdir, x), 'cka')
            create_server_cert(address, ca_file, cert_file, key_file, key_size=1024)
            ctx = ssl.create_default_context(cafile=ca_file)
            with TestServer(lambda data:(data.path[0] + data.read()), ssl_certfile=cert_file, ssl_keyfile=key_file) as server:
                conn = httplib.HTTPSConnection(server.address[0], server.address[1], strict=True, context=ctx)
                conn.request('GET', '/test', 'body')
                r = conn.getresponse()
                self.ae(r.status, httplib.OK)
                self.ae(r.read(), b'testbody')
                cert = conn.sock.getpeercert()
                subject = dict(x[0] for x in cert['subject'])
                self.ae(subject['commonName'], address)

    @skipUnless(islinux and os.access(SYSTEMD, os.X_OK), 'systemd-activate not available')
    def test_systemd(self):
        'Test systemd socket activation'
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        s.bind(('localhost', 0))
        port = s.getsockname()[1]
        f = os.path.abspath(__file__).rstrip('c')
        s.close()
        p = subprocess.Popen([SYSTEMD, '-l', '127.0.0.1:%d' % port, 'calibre-debug', f], stdout=open(os.devnull, 'wb'), stderr=subprocess.STDOUT)
        try:
            conn = httplib.HTTPConnection('localhost', port, strict=True, timeout=1)
            conn.request('GET', '/test', 'body')
            r = conn.getresponse()
            self.ae(r.status, httplib.OK)
            self.ae(r.read(), b'testbody')
            conn.request('GET', '/quit')
            st = time.time()
            while p.poll() is None and time.time() - st < 2:
                time.sleep(0.01)
        finally:
            if p.poll() is None:
                p.kill()

if __name__ == '__main__':
    def handler(data):
        if data.path and data.path[0] == 'quit':
            raise SystemExit(0)
        return (data.path[0] + data.read()) if data.path else ''
    with TestServer(handler, allow_socket_preallocation=True) as server:
        server.join()
