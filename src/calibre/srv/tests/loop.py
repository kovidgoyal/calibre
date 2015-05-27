#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import httplib, ssl, os, socket
from unittest import skipIf

try:
    from calibre.utils.certgen import create_server_cert
except ImportError:
    create_server_cert = None


from calibre.srv.pre_activated import pre_activated_socket
from calibre.srv.tests.base import BaseTest, TestServer
from calibre.ptempfile import TemporaryDirectory

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

    @skipIf(pre_activated_socket is None, 'pre_activated_socket not available')
    def test_socket_activation(self):
        'Test socket activation'
        os.closerange(3, 4)  # Ensure the socket gets fileno == 3
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
        s.bind(('localhost', 0))
        port = s.getsockname()[1]
        self.ae(s.fileno(), 3)
        os.environ['LISTEN_PID'] = str(os.getpid())
        os.environ['LISTEN_FDS'] = '1'
        with TestServer(lambda data:(data.path[0] + data.read()), allow_socket_preallocation=True) as server:
            conn = server.connect()
            conn.request('GET', '/test', 'body')
            r = conn.getresponse()
            self.ae(r.status, httplib.OK)
            self.ae(r.read(), b'testbody')
            self.ae(server.loop.bound_address[1], port)
