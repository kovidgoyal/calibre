#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import httplib, ssl, os
from unittest import skipIf

try:
    from calibre.utils.certgen import create_server_cert
except ImportError:
    create_server_cert = None

from calibre.srv.tests.base import BaseTest, TestServer
from calibre.ptempfile import TemporaryDirectory

HOST = 'localhost.test'

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
