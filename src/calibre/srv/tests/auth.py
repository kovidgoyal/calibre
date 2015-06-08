#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import httplib, base64, urllib2

from calibre.srv.tests.base import BaseTest, TestServer
from calibre.srv.routes import endpoint, Router

REALM = 'calibre-test'

@endpoint('/open')
def noauth(ctx, data):
    return 'open'

@endpoint('/closed', auth_required=True)
def auth(ctx, data):
    return 'closed'

@endpoint('/android', auth_required=True, android_workaround=True)
def android(ctx, data):
    return '/android'

def router(prefer_basic_auth=False):
    from calibre.srv.auth import AuthController
    return Router(globals().itervalues(), auth_controller=AuthController(
        {'testuser':'testpw', '!@#$%^&*()-=_+':'!@#$%^&*()-=_+'},
        prefer_basic_auth=prefer_basic_auth, realm=REALM, max_age_seconds=1))

def urlopen(server, path='/closed', un='testuser', pw='testpw', method='digest'):
    auth_handler = urllib2.HTTPBasicAuthHandler() if method == 'basic' else urllib2.HTTPDigestAuthHandler()
    url = 'http://localhost:%d%s' % (server.address[1], path)
    auth_handler.add_password(realm=REALM, uri=url, user=un, passwd=pw)
    return urllib2.build_opener(auth_handler).open(url)

class TestAuth(BaseTest):

    def test_basic_auth(self):
        'Test HTTP Basic auth'
        r = router(prefer_basic_auth=True)
        with TestServer(r.dispatch) as server:
            r.auth_controller.log = server.log
            conn = server.connect()
            conn.request('GET', '/open')
            r = conn.getresponse()
            self.ae(r.status, httplib.OK)
            self.ae(r.read(), b'open')

            conn.request('GET', '/closed')
            r = conn.getresponse()
            self.ae(r.status, httplib.UNAUTHORIZED)
            self.ae(r.getheader('WWW-Authenticate'), b'Basic realm="%s"' % bytes(REALM))
            self.assertFalse(r.read())
            conn.request('GET', '/closed', headers={'Authorization': b'Basic ' + base64.standard_b64encode(b'testuser:testpw')})
            r = conn.getresponse()
            self.ae(r.read(), b'closed')
            self.ae(r.status, httplib.OK)
            self.ae(b'closed', urlopen(server, method='basic').read())
            self.ae(b'closed', urlopen(server, un='!@#$%^&*()-=_+', pw='!@#$%^&*()-=_+', method='basic').read())

            def request(un='testuser', pw='testpw'):
                conn.request('GET', '/closed', headers={'Authorization': b'Basic ' + base64.standard_b64encode(bytes('%s:%s' % (un, pw)))})
                r = conn.getresponse()
                return r.status, r.read()

            warnings = []
            server.loop.log.warn = lambda *args, **kwargs: warnings.append(' '.join(args))
            self.ae((httplib.OK, b'closed'), request())
            self.ae((httplib.UNAUTHORIZED, b''), request('x', 'y'))
            self.ae(1, len(warnings))
            self.ae((httplib.UNAUTHORIZED, b''), request('testuser', 'y'))
            self.ae((httplib.UNAUTHORIZED, b''), request('asf', 'testpw'))

    def test_digest_auth(self):
        'Test HTTP Digest auth'
        from calibre.srv.http_request import normalize_header_name
        from calibre.srv.utils import parse_http_dict
        r = router()
        with TestServer(r.dispatch) as server:
            r.auth_controller.log = server.log
            def test(conn, path, headers={}, status=httplib.OK, body=b'', request_body=b''):
                conn.request('GET', path, request_body, headers)
                r = conn.getresponse()
                self.ae(r.status, status)
                self.ae(r.read(), body)
                return {normalize_header_name(k):v for k, v in r.getheaders()}
            conn = server.connect()
            test(conn, '/open', body=b'open')
            auth = parse_http_dict(test(conn, '/closed', status=httplib.UNAUTHORIZED)['WWW-Authenticate'])
            self.ae(auth[b'Digest realm'], bytes(REALM)), self.ae(auth[b'algorithm'], b'MD5'), self.ae(auth[b'qop'], b'auth')
            self.assertNotIn('stale', auth)
            self.ae(urlopen(server).read(), b'closed')
