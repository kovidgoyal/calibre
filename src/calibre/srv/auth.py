#!/usr/bin/env python2
# vim:fileencoding=utf-8
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__ = 'GPL v3'
__copyright__ = '2015, Kovid Goyal <kovid at kovidgoyal.net>'

import binascii, os, random, struct, base64, httplib
from hashlib import md5, sha256
from itertools import permutations
from threading import Lock

from calibre.srv.errors import HTTPAuthRequired, HTTPSimpleResponse
from calibre.srv.http_request import parse_uri
from calibre.srv.utils import parse_http_dict, encode_path
from calibre.utils.monotonic import monotonic

MAX_AGE_SECONDS = 3600
nonce_counter, nonce_counter_lock = 0, Lock()


def as_bytestring(x):
    if not isinstance(x, bytes):
        x = x.encode('utf-8')
    return x


def md5_hex(s):
    return md5(as_bytestring(s)).hexdigest().decode('ascii')


def sha256_hex(s):
    return sha256(as_bytestring(s)).hexdigest().decode('ascii')


def base64_decode(s):
    return base64.standard_b64decode(as_bytestring(s)).decode('utf-8')


def synthesize_nonce(key_order, realm, secret, timestamp=None):
    '''
    Create a nonce. Can be used for either digest or cookie based auth.
    The nonce is of the form timestamp:hash with hash being a hash of the
    timestamp, server secret and realm. This allows the timestamp to be
    validated and stale nonce's to be rejected.
    '''
    if timestamp is None:
        global nonce_counter
        with nonce_counter_lock:
            nonce_counter = (nonce_counter + 1) % 65535
            # The resolution of monotonic() on windows is very low (10s of
            # milliseconds) so to ensure nonce values are not re-used, we have a
            # global counter
            timestamp = binascii.hexlify(struct.pack(b'!dH', float(monotonic()), nonce_counter))
    h = sha256_hex(key_order.format(timestamp, realm, secret))
    nonce = ':'.join((timestamp, h))
    return nonce


def validate_nonce(key_order, nonce, realm, secret):
    timestamp, hashpart = nonce.partition(':')[::2]
    s_nonce = synthesize_nonce(key_order, realm, secret, timestamp)
    return s_nonce == nonce


def is_nonce_stale(nonce, max_age_seconds=MAX_AGE_SECONDS):
    try:
        timestamp = struct.unpack(b'!dH', binascii.unhexlify(as_bytestring(nonce.partition(':')[0])))[0]
        return timestamp + max_age_seconds < monotonic()
    except Exception:
        pass
    return True


class DigestAuth(object):  # {{{

    valid_algorithms = {'MD5', 'MD5-SESS'}
    valid_qops = {'auth', 'auth-int'}

    def __init__(self, header_val):
        data = parse_http_dict(header_val)
        self.realm = data.get('realm')
        self.username = data.get('username')
        self.nonce = data.get('nonce')
        self.uri = data.get('uri')
        self.method = data.get('method')
        self.response = data.get('response')
        self.algorithm = data.get('algorithm', 'MD5').upper()
        self.cnonce = data.get('cnonce')
        self.opaque = data.get('opaque')
        self.qop = data.get('qop', '').lower()
        self.nonce_count = data.get('nc')

        if self.algorithm not in self.valid_algorithms:
            raise HTTPSimpleResponse(httplib.BAD_REQUEST, 'Unsupported digest algorithm')

        if not (self.username and self.realm and self.nonce and self.uri and self.response):
            raise HTTPSimpleResponse(httplib.BAD_REQUEST, 'Digest algorithm required fields missing')

        if self.qop:
            if self.qop not in self.valid_qops:
                raise HTTPSimpleResponse(httplib.BAD_REQUEST, 'Unsupported digest qop')
            if not (self.cnonce and self.nonce_count):
                raise HTTPSimpleResponse(httplib.BAD_REQUEST, 'qop present, but cnonce and nonce_count absent')
        else:
            if self.cnonce or self.nonce_count:
                raise HTTPSimpleResponse(httplib.BAD_REQUEST, 'qop missing')

    def H(self, val):
        return md5_hex(val)

    def H_A2(self, data):
        """Returns the H(A2) string. See :rfc:`2617` section 3.2.2.3."""
        # RFC 2617 3.2.2.3
        # If the "qop" directive's value is "auth" or is unspecified,
        # then A2 is:
        #    A2 = method ":" digest-uri-value
        #
        # If the "qop" value is "auth-int", then A2 is:
        #    A2 = method ":" digest-uri-value ":" H(entity-body)
        if self.qop == "auth-int":
            a2 = "%s:%s:%s" % (data.method, self.uri, self.H(data.peek()))
        else:
            a2 = '%s:%s' % (data.method, self.uri)
        return self.H(a2)

    def request_digest(self, pw, data):
        ha1 = self.H(':'.join((self.username, self.realm, pw)))
        ha2 = self.H_A2(data)
        # Request-Digest -- RFC 2617 3.2.2.1
        if self.qop:
            req = "%s:%s:%s:%s:%s" % (
                self.nonce, self.nonce_count, self.cnonce, self.qop, ha2)
        else:
            req = "%s:%s" % (self.nonce, ha2)

        # RFC 2617 3.2.2.2
        #
        # If the "algorithm" directive's value is "MD5" or is unspecified,
        # then A1 is:
        #    A1 = unq(username-value) ":" unq(realm-value) ":" passwd
        #
        # If the "algorithm" directive's value is "MD5-sess", then A1 is
        # calculated only once - on the first request by the client following
        # receipt of a WWW-Authenticate challenge from the server.
        # A1 = H( unq(username-value) ":" unq(realm-value) ":" passwd )
        #         ":" unq(nonce-value) ":" unq(cnonce-value)
        if self.algorithm == 'MD5-SESS':
            ha1 = self.H('%s:%s:%s' % (ha1, self.nonce, self.cnonce))

        return self.H('%s:%s' % (ha1, req))

    def validate_request(self, pw, data, log=None):
        # We should also be checking for replay attacks by using nonce_count,
        # however, various HTTP clients, most prominently Firefox dont
        # implement nonce-counts correctly, so we cannot do the check.
        # https://bugzil.la/114451
        path = parse_uri(self.uri.encode('utf-8'))[1]
        if path != data.path:
            if log is not None:
                log.warn('Authorization URI mismatch: %s != %s from client: %s' % (
                    data.path, path, data.remote_addr))
            raise HTTPSimpleResponse(httplib.BAD_REQUEST, 'The uri in the Request Line and the Authorization header do not match')
        return self.response is not None and data.path == path and self.request_digest(pw, data) == self.response
# }}}


class AuthController(object):

    '''
    Implement Basic/Digest authentication for the Content server. Android browsers
    cannot handle HTTP AUTH when downloading files, as the download is handed
    off to a separate process. So we use a cookie based authentication scheme
    for some endpoints (/get) to allow downloads to work on android. Apparently,
    cookies are passed to the download process. The cookie expires after
    MAX_AGE_SECONDS.

    The android browser appears to send a GET request to the server and only if
    that request succeeds is the download handed off to the download process.
    We could reduce MAX_AGE_SECONDS, but we leave it high as the download
    process might have downloads queued and therefore not start the download
    immediately.

    Note that this makes the server vulnerable to session-hijacking (i.e. some
    one can sniff the traffic and create their own requests to /get with the
    appropriate cookie, for an hour). The fix is to use https, but since this
    is usually run as a private server, that cannot be done. If you care about
    this vulnerability, run the server behind a reverse proxy that uses HTTPS.

    Also, note that digest auth is itself vulnerable to partial session
    hijacking, since we have to ignore repeated nc values, because Firefox does
    not implement the digest auth spec properly (it sends out of order nc
    values).
    '''
    ANDROID_COOKIE = 'android_workaround'

    def __init__(self, user_credentials=None, prefer_basic_auth=False, realm='calibre', max_age_seconds=MAX_AGE_SECONDS, log=None):
        self.user_credentials, self.prefer_basic_auth = user_credentials, prefer_basic_auth
        self.log = log
        self.secret = binascii.hexlify(os.urandom(random.randint(20, 30))).decode('ascii')
        self.max_age_seconds = max_age_seconds
        self.key_order = '{%d}:{%d}:{%d}' % random.choice(tuple(permutations((0,1,2))))
        self.realm = realm
        if '"' in realm:
            raise ValueError('Double-quotes are not allowed in the authentication realm')

    def check(self, un, pw):
        return pw and self.user_credentials.get(un) == pw

    def __call__(self, data, endpoint):
        path = encode_path(*data.path)
        http_auth_needed = not (endpoint.android_workaround and self.validate_android_cookie(path, data.cookies.get(self.ANDROID_COOKIE)))
        if http_auth_needed:
            self.do_http_auth(data, endpoint)
            if endpoint.android_workaround:
                data.outcookie[self.ANDROID_COOKIE] = synthesize_nonce(self.key_order, path, self.secret)
                data.outcookie[self.ANDROID_COOKIE]['path'] = path

    def validate_android_cookie(self, path, cookie):
        return cookie and validate_nonce(self.key_order, cookie, path, self.secret) and not is_nonce_stale(cookie, self.max_age_seconds)

    def do_http_auth(self, data, endpoint):
        auth = data.inheaders.get('Authorization')
        nonce_is_stale = False
        log_msg = None
        data.username = None

        if auth:
            scheme, rest = auth.partition(' ')[::2]
            scheme = scheme.lower()
            if scheme == 'digest':
                da = DigestAuth(rest.strip())
                if validate_nonce(self.key_order, da.nonce, self.realm, self.secret):
                    pw = self.user_credentials.get(da.username)
                    if pw and da.validate_request(pw, data, self.log):
                        nonce_is_stale = is_nonce_stale(da.nonce, self.max_age_seconds)
                        if not nonce_is_stale:
                            data.username = da.username
                            return
                log_msg = 'Failed login attempt from: %s' % data.remote_addr
            elif self.prefer_basic_auth and scheme == 'basic':
                try:
                    un, pw = base64_decode(rest.strip()).partition(':')[::2]
                except ValueError:
                    raise HTTPSimpleResponse(httplib.BAD_REQUEST, 'The username or password contained non-UTF8 encoded characters')
                if not un or not pw:
                    raise HTTPSimpleResponse(httplib.BAD_REQUEST, 'The username or password was empty')
                if self.check(un, pw):
                    data.username = un
                    return
                log_msg = 'Failed login attempt from: %s' % data.remote_addr
            else:
                raise HTTPSimpleResponse(httplib.BAD_REQUEST, 'Unsupported authentication method')

        if self.prefer_basic_auth:
            raise HTTPAuthRequired('Basic realm="%s"' % self.realm, log=log_msg)

        s = 'Digest realm="%s", nonce="%s", algorithm="MD5", qop="auth"' % (
            self.realm, synthesize_nonce(self.key_order, self.realm, self.secret))
        if nonce_is_stale:
            s += ', stale="true"'
        raise HTTPAuthRequired(s, log=log_msg)
