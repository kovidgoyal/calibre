#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import httplib, base64, urllib2, subprocess, os, cookielib, time
from collections import namedtuple
try:
    from distutils.spawn import find_executable
except ImportError:  # windows
    find_executable = lambda x: None

from calibre.ptempfile import TemporaryDirectory
from calibre.srv.errors import HTTPForbidden
from calibre.srv.tests.base import BaseTest, TestServer
from calibre.srv.routes import endpoint, Router

REALM = 'calibre-test'


@endpoint('/open', auth_required=False)
def noauth(ctx, data):
    return 'open'


@endpoint('/closed', auth_required=True)
def auth(ctx, data):
    return 'closed'


@endpoint('/android', auth_required=True, android_workaround=True)
def android(ctx, data):
    return 'android'


@endpoint('/android2', auth_required=True, android_workaround=True)
def android2(ctx, data):
    return 'android2'


def router(prefer_basic_auth=False, ban_for=0, ban_after=5):
    from calibre.srv.auth import AuthController
    return Router(globals().itervalues(), auth_controller=AuthController(
        {'testuser':'testpw', '!@#$%^&*()-=_+':'!@#$%^&*()-=_+'},
        ban_time_in_minutes=ban_for, ban_after=ban_after,
        prefer_basic_auth=prefer_basic_auth, realm=REALM, max_age_seconds=1))


def urlopen(server, path='/closed', un='testuser', pw='testpw', method='digest'):
    auth_handler = urllib2.HTTPBasicAuthHandler() if method == 'basic' else urllib2.HTTPDigestAuthHandler()
    url = 'http://localhost:%d%s' % (server.address[1], path)
    auth_handler.add_password(realm=REALM, uri=url, user=un, passwd=pw)
    return urllib2.build_opener(auth_handler).open(url)


def digest(un, pw, nonce=None, uri=None, method='GET', nc=1, qop='auth', realm=REALM, cnonce=None, algorithm='MD5', body=b'', modify=lambda x:None):
    'Create the payload for a digest based Authorization header'
    from calibre.srv.auth import DigestAuth
    templ = ('username="{un}", realm="{realm}", qop={qop}, method="{method}",'
    ' nonce="{nonce}", uri="{uri}", nc={nc}, algorithm="{algorithm}", cnonce="{cnonce}", response="{response}"')
    h = templ.format(un=un, realm=realm, qop=qop, uri=uri, method=method, nonce=nonce, nc=nc, cnonce=cnonce, algorithm=algorithm, response=None)
    da = DigestAuth(h)
    modify(da)
    pw = getattr(da, 'pw', pw)

    class Data(object):

        def __init__(self):
            self.method = method

        def peek(self):
            return body
    response = da.request_digest(pw, Data())
    return ('Digest ' + templ.format(
        un=un, realm=realm, qop=qop, uri=uri, method=method, nonce=nonce, nc=nc, cnonce=cnonce, algorithm=algorithm, response=response)).encode('ascii')


class TestAuth(BaseTest):

    def test_basic_auth(self):  # {{{
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
            self.ae((httplib.BAD_REQUEST, b'The username or password was empty'), request('', ''))
            self.ae(1, len(warnings))
            self.ae((httplib.UNAUTHORIZED, b''), request('testuser', 'y'))
            self.ae((httplib.BAD_REQUEST, b'The username or password was empty'), request('testuser', ''))
            self.ae((httplib.BAD_REQUEST, b'The username or password was empty'), request(''))
            self.ae((httplib.UNAUTHORIZED, b''), request('asf', 'testpw'))
    # }}}

    def test_library_restrictions(self):  # {{{
        from calibre.srv.opts import Options
        from calibre.srv.handler import Handler
        from calibre.db.legacy import create_backend
        opts = Options(userdb=':memory:')
        Data = namedtuple('Data', 'username')
        with TemporaryDirectory() as base:
            l1, l2, l3 = map(lambda x: os.path.join(base, 'l' + x), '123')
            for l in (l1, l2, l3):
                create_backend(l).close()
            ctx = Handler((l1, l2, l3), opts).router.ctx
            um = ctx.user_manager

            def get_library(username=None, library_id=None):
                ans = ctx.get_library(Data(username), library_id=library_id)
                return os.path.basename(ans.backend.library_path)

            def library_info(username=None):
                lmap, defaultlib = ctx.library_info(Data(username))
                lmap = {k:os.path.basename(v) for k, v in lmap.iteritems()}
                return lmap, defaultlib

            self.assertEqual(get_library(), 'l1')
            self.assertEqual(library_info()[0], {'l%d'%i:'l%d'%i for i in range(1, 4)})
            self.assertEqual(library_info()[1], 'l1')
            self.assertRaises(HTTPForbidden, get_library, 'xxx')
            um.add_user('a', 'a')
            self.assertEqual(library_info('a')[0], {'l%d'%i:'l%d'%i for i in range(1, 4)})
            um.update_user_restrictions('a', {'blocked_library_names': ['L2']})
            self.assertEqual(library_info('a')[0], {'l%d'%i:'l%d'%i for i in range(1, 4) if i != 2})
            um.update_user_restrictions('a', {'allowed_library_names': ['l3']})
            self.assertEqual(library_info('a')[0], {'l%d'%i:'l%d'%i for i in range(1, 4) if i == 3})
            self.assertEqual(library_info('a')[1], 'l3')
            self.assertRaises(HTTPForbidden, get_library, 'a', 'l1')
            self.assertRaises(HTTPForbidden, get_library, 'xxx')

    # }}}

    def test_digest_auth(self):  # {{{
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
            auth = parse_http_dict(test(conn, '/closed', status=httplib.UNAUTHORIZED)['WWW-Authenticate'].partition(b' ')[2])
            nonce = auth['nonce']
            auth = parse_http_dict(test(conn, '/closed', status=httplib.UNAUTHORIZED)['WWW-Authenticate'].partition(b' ')[2])
            self.assertNotEqual(nonce, auth['nonce'], 'nonce was re-used')
            self.ae(auth[b'realm'], bytes(REALM)), self.ae(auth[b'algorithm'], b'MD5'), self.ae(auth[b'qop'], b'auth')
            self.assertNotIn('stale', auth)
            args = auth.copy()
            args['un'], args['pw'], args['uri'] = 'testuser', 'testpw', '/closed'

            def ok_test(conn, dh, **args):
                args['body'] = args.get('body', b'closed')
                return test(conn, '/closed', headers={'Authorization':dh}, **args)

            ok_test(conn, digest(**args))
            # Check that server ignores repeated nc values
            ok_test(conn, digest(**args))

            warnings = []
            server.loop.log.warn = lambda *args, **kwargs: warnings.append(' '.join(args))
            # Check stale nonces
            orig, r.auth_controller.max_age_seconds = r.auth_controller.max_age_seconds, -1
            auth = parse_http_dict(test(conn, '/closed', headers={
                'Authorization':digest(**args)},status=httplib.UNAUTHORIZED)['WWW-Authenticate'].partition(b' ')[2])
            self.assertIn('stale', auth)
            r.auth_controller.max_age_seconds = orig
            ok_test(conn, digest(**args))

            def fail_test(conn, modify, **kw):
                kw['body'] = kw.get('body', b'')
                kw['status'] = kw.get('status', httplib.UNAUTHORIZED)
                args['modify'] = modify
                return test(conn, '/closed', headers={'Authorization':digest(**args)}, **kw)

            # Check modified nonce fails
            fail_test(conn, lambda da:setattr(da, 'nonce', 'xyz'))
            fail_test(conn, lambda da:setattr(da, 'nonce', 'x' + da.nonce))

            # Check mismatched uri fails
            fail_test(conn, lambda da:setattr(da, 'uri', '/'))
            fail_test(conn, lambda da:setattr(da, 'uri', '/closed2'))
            fail_test(conn, lambda da:setattr(da, 'uri', '/closed/2'))

            # Check that incorrect user/password fails
            fail_test(conn, lambda da:setattr(da, 'pw', '/'))
            fail_test(conn, lambda da:setattr(da, 'username', '/'))
            fail_test(conn, lambda da:setattr(da, 'username', ''))
            fail_test(conn, lambda da:setattr(da, 'pw', ''))
            fail_test(conn, lambda da:(setattr(da, 'pw', ''), setattr(da, 'username', '')))

            # Check against python's stdlib
            self.ae(urlopen(server).read(), b'closed')

            # Check using curl
            curl = find_executable('curl')
            if curl:
                def docurl(data, *args):
                    cmd = [curl] + list(args) + ['http://localhost:%d/closed' % server.address[1]]
                    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=open(os.devnull, 'wb'))
                    x = p.stdout.read()
                    p.wait()
                    self.ae(x, data)
                docurl(b'')
                docurl(b'', '--digest', '--user', 'xxxx:testpw')
                docurl(b'', '--digest', '--user', 'testuser:xtestpw')
                docurl(b'closed', '--digest', '--user', 'testuser:testpw')
    # }}}

    def test_fail_ban(self):  # {{{
        ban_for = 0.5/60.0
        r = router(prefer_basic_auth=True, ban_for=ban_for, ban_after=2)
        with TestServer(r.dispatch) as server:
            r.auth_controller.log = server.log
            conn = server.connect()

            def request(un='testuser', pw='testpw'):
                conn.request('GET', '/closed', headers={'Authorization': b'Basic ' + base64.standard_b64encode(bytes('%s:%s' % (un, pw)))})
                r = conn.getresponse()
                return r.status, r.read()

            warnings = []
            server.loop.log.warn = lambda *args, **kwargs: warnings.append(' '.join(args))
            self.ae((httplib.OK, b'closed'), request())
            self.ae((httplib.UNAUTHORIZED, b''), request('x', 'y'))
            self.ae((httplib.UNAUTHORIZED, b''), request('x', 'y'))
            self.ae(httplib.FORBIDDEN, request('x', 'y')[0])
            self.ae(httplib.FORBIDDEN, request()[0])
            time.sleep(ban_for * 60 + 0.01)
            self.ae((httplib.OK, b'closed'), request())
    # }}}

    def test_android_auth_workaround(self):  # {{{
        'Test authentication workaround for Android'
        r = router()
        with TestServer(r.dispatch) as server:
            r.auth_controller.log = server.log
            conn = server.connect()

            # First check that unauth access fails
            conn.request('GET', '/android')
            r = conn.getresponse()
            self.ae(r.status, httplib.UNAUTHORIZED)

            auth_handler = urllib2.HTTPDigestAuthHandler()
            url = 'http://localhost:%d%s' % (server.address[1], '/android')
            auth_handler.add_password(realm=REALM, uri=url, user='testuser', passwd='testpw')
            cj = cookielib.CookieJar()
            cookie_handler = urllib2.HTTPCookieProcessor(cj)
            r = urllib2.build_opener(auth_handler, cookie_handler).open(url)
            self.ae(r.getcode(), httplib.OK)
            cookies = tuple(cj)
            self.ae(len(cookies), 1)
            cookie = cookies[0]
            self.assertIn(b':', cookie.value)
            self.ae(cookie.path, b'/android')
            r = urllib2.build_opener(cookie_handler).open(url)
            self.ae(r.getcode(), httplib.OK)
            self.ae(r.read(), b'android')
            # Test that a replay attack against a different URL does not work
            try:
                urllib2.build_opener(cookie_handler).open(url+'2')
                assert ('Replay attack succeeded')
            except urllib2.HTTPError as e:
                self.ae(e.code, httplib.UNAUTHORIZED)

    # }}}
