"""HTTP Authentication and Proxy support.

All but HTTPProxyPasswordMgr come from Python 2.5.


Copyright 2006 John J. Lee <jjl@pobox.com>

This code is free software; you can redistribute it and/or modify it under
the terms of the BSD or ZPL 2.1 licenses (see the file COPYING.txt
included with the distribution).

"""

import re, base64, urlparse, posixpath, md5, sha, sys, copy

from urllib2 import BaseHandler
from urllib import getproxies, unquote, splittype, splituser, splitpasswd, \
     splitport


def _parse_proxy(proxy):
    """Return (scheme, user, password, host/port) given a URL or an authority.

    If a URL is supplied, it must have an authority (host:port) component.
    According to RFC 3986, having an authority component means the URL must
    have two slashes after the scheme:

    >>> _parse_proxy('file:/ftp.example.com/')
    Traceback (most recent call last):
    ValueError: proxy URL with no authority: 'file:/ftp.example.com/'

    The first three items of the returned tuple may be None.

    Examples of authority parsing:

    >>> _parse_proxy('proxy.example.com')
    (None, None, None, 'proxy.example.com')
    >>> _parse_proxy('proxy.example.com:3128')
    (None, None, None, 'proxy.example.com:3128')

    The authority component may optionally include userinfo (assumed to be
    username:password):

    >>> _parse_proxy('joe:password@proxy.example.com')
    (None, 'joe', 'password', 'proxy.example.com')
    >>> _parse_proxy('joe:password@proxy.example.com:3128')
    (None, 'joe', 'password', 'proxy.example.com:3128')

    Same examples, but with URLs instead:

    >>> _parse_proxy('http://proxy.example.com/')
    ('http', None, None, 'proxy.example.com')
    >>> _parse_proxy('http://proxy.example.com:3128/')
    ('http', None, None, 'proxy.example.com:3128')
    >>> _parse_proxy('http://joe:password@proxy.example.com/')
    ('http', 'joe', 'password', 'proxy.example.com')
    >>> _parse_proxy('http://joe:password@proxy.example.com:3128')
    ('http', 'joe', 'password', 'proxy.example.com:3128')

    Everything after the authority is ignored:

    >>> _parse_proxy('ftp://joe:password@proxy.example.com/rubbish:3128')
    ('ftp', 'joe', 'password', 'proxy.example.com')

    Test for no trailing '/' case:

    >>> _parse_proxy('http://joe:password@proxy.example.com')
    ('http', 'joe', 'password', 'proxy.example.com')

    """
    scheme, r_scheme = splittype(proxy)
    if not r_scheme.startswith("/"):
        # authority
        scheme = None
        authority = proxy
    else:
        # URL
        if not r_scheme.startswith("//"):
            raise ValueError("proxy URL with no authority: %r" % proxy)
        # We have an authority, so for RFC 3986-compliant URLs (by ss 3.
        # and 3.3.), path is empty or starts with '/'
        end = r_scheme.find("/", 2)
        if end == -1:
            end = None
        authority = r_scheme[2:end]
    userinfo, hostport = splituser(authority)
    if userinfo is not None:
        user, password = splitpasswd(userinfo)
    else:
        user = password = None
    return scheme, user, password, hostport

class ProxyHandler(BaseHandler):
    # Proxies must be in front
    handler_order = 100

    def __init__(self, proxies=None):
        if proxies is None:
            proxies = getproxies()
        assert hasattr(proxies, 'has_key'), "proxies must be a mapping"
        self.proxies = proxies
        for type, url in proxies.items():
            setattr(self, '%s_open' % type,
                    lambda r, proxy=url, type=type, meth=self.proxy_open: \
                    meth(r, proxy, type))

    def proxy_open(self, req, proxy, type):
        orig_type = req.get_type()
        proxy_type, user, password, hostport = _parse_proxy(proxy)
        if proxy_type is None:
            proxy_type = orig_type
        if user and password:
            user_pass = '%s:%s' % (unquote(user), unquote(password))
            creds = base64.encodestring(user_pass).strip()
            req.add_header('Proxy-authorization', 'Basic ' + creds)
        hostport = unquote(hostport)
        req.set_proxy(hostport, proxy_type)
        if orig_type == proxy_type:
            # let other handlers take care of it
            return None
        else:
            # need to start over, because the other handlers don't
            # grok the proxy's URL type
            # e.g. if we have a constructor arg proxies like so:
            # {'http': 'ftp://proxy.example.com'}, we may end up turning
            # a request for http://acme.example.com/a into one for
            # ftp://proxy.example.com/a
            return self.parent.open(req)

class HTTPPasswordMgr:

    def __init__(self):
        self.passwd = {}

    def add_password(self, realm, uri, user, passwd):
        # uri could be a single URI or a sequence
        if isinstance(uri, basestring):
            uri = [uri]
        if not realm in self.passwd:
            self.passwd[realm] = {}
        for default_port in True, False:
            reduced_uri = tuple(
                [self.reduce_uri(u, default_port) for u in uri])
            self.passwd[realm][reduced_uri] = (user, passwd)

    def find_user_password(self, realm, authuri):
        domains = self.passwd.get(realm, {})
        for default_port in True, False:
            reduced_authuri = self.reduce_uri(authuri, default_port)
            for uris, authinfo in domains.iteritems():
                for uri in uris:
                    if self.is_suburi(uri, reduced_authuri):
                        return authinfo
        return None, None

    def reduce_uri(self, uri, default_port=True):
        """Accept authority or URI and extract only the authority and path."""
        # note HTTP URLs do not have a userinfo component
        parts = urlparse.urlsplit(uri)
        if parts[1]:
            # URI
            scheme = parts[0]
            authority = parts[1]
            path = parts[2] or '/'
        else:
            # host or host:port
            scheme = None
            authority = uri
            path = '/'
        host, port = splitport(authority)
        if default_port and port is None and scheme is not None:
            dport = {"http": 80,
                     "https": 443,
                     }.get(scheme)
            if dport is not None:
                authority = "%s:%d" % (host, dport)
        return authority, path

    def is_suburi(self, base, test):
        """Check if test is below base in a URI tree

        Both args must be URIs in reduced form.
        """
        if base == test:
            return True
        if base[0] != test[0]:
            return False
        common = posixpath.commonprefix((base[1], test[1]))
        if len(common) == len(base[1]):
            return True
        return False


class HTTPPasswordMgrWithDefaultRealm(HTTPPasswordMgr):

    def find_user_password(self, realm, authuri):
        user, password = HTTPPasswordMgr.find_user_password(self, realm,
                                                            authuri)
        if user is not None:
            return user, password
        return HTTPPasswordMgr.find_user_password(self, None, authuri)


class AbstractBasicAuthHandler:

    rx = re.compile('[ \t]*([^ \t]+)[ \t]+realm="([^"]*)"', re.I)

    # XXX there can actually be multiple auth-schemes in a
    # www-authenticate header.  should probably be a lot more careful
    # in parsing them to extract multiple alternatives

    def __init__(self, password_mgr=None):
        if password_mgr is None:
            password_mgr = HTTPPasswordMgr()
        self.passwd = password_mgr
        self.add_password = self.passwd.add_password

    def http_error_auth_reqed(self, authreq, host, req, headers):
        # host may be an authority (without userinfo) or a URL with an
        # authority
        # XXX could be multiple headers
        authreq = headers.get(authreq, None)
        if authreq:
            mo = AbstractBasicAuthHandler.rx.search(authreq)
            if mo:
                scheme, realm = mo.groups()
                if scheme.lower() == 'basic':
                    return self.retry_http_basic_auth(host, req, realm)

    def retry_http_basic_auth(self, host, req, realm):
        user, pw = self.passwd.find_user_password(realm, host)
        if pw is not None:
            raw = "%s:%s" % (user, pw)
            auth = 'Basic %s' % base64.encodestring(raw).strip()
            if req.headers.get(self.auth_header, None) == auth:
                return None
            newreq = copy.copy(req)
            newreq.add_header(self.auth_header, auth)
            newreq.visit = False
            return self.parent.open(newreq)
        else:
            return None


class HTTPBasicAuthHandler(AbstractBasicAuthHandler, BaseHandler):

    auth_header = 'Authorization'

    def http_error_401(self, req, fp, code, msg, headers):
        url = req.get_full_url()
        return self.http_error_auth_reqed('www-authenticate',
                                          url, req, headers)


class ProxyBasicAuthHandler(AbstractBasicAuthHandler, BaseHandler):

    auth_header = 'Proxy-authorization'

    def http_error_407(self, req, fp, code, msg, headers):
        # http_error_auth_reqed requires that there is no userinfo component in
        # authority.  Assume there isn't one, since urllib2 does not (and
        # should not, RFC 3986 s. 3.2.1) support requests for URLs containing
        # userinfo.
        authority = req.get_host()
        return self.http_error_auth_reqed('proxy-authenticate',
                                          authority, req, headers)


def randombytes(n):
    """Return n random bytes."""
    # Use /dev/urandom if it is available.  Fall back to random module
    # if not.  It might be worthwhile to extend this function to use
    # other platform-specific mechanisms for getting random bytes.
    if os.path.exists("/dev/urandom"):
        f = open("/dev/urandom")
        s = f.read(n)
        f.close()
        return s
    else:
        L = [chr(random.randrange(0, 256)) for i in range(n)]
        return "".join(L)

class AbstractDigestAuthHandler:
    # Digest authentication is specified in RFC 2617.

    # XXX The client does not inspect the Authentication-Info header
    # in a successful response.

    # XXX It should be possible to test this implementation against
    # a mock server that just generates a static set of challenges.

    # XXX qop="auth-int" supports is shaky

    def __init__(self, passwd=None):
        if passwd is None:
            passwd = HTTPPasswordMgr()
        self.passwd = passwd
        self.add_password = self.passwd.add_password
        self.retried = 0
        self.nonce_count = 0

    def reset_retry_count(self):
        self.retried = 0

    def http_error_auth_reqed(self, auth_header, host, req, headers):
        authreq = headers.get(auth_header, None)
        if self.retried > 5:
            # Don't fail endlessly - if we failed once, we'll probably
            # fail a second time. Hm. Unless the Password Manager is
            # prompting for the information. Crap. This isn't great
            # but it's better than the current 'repeat until recursion
            # depth exceeded' approach <wink>
            raise HTTPError(req.get_full_url(), 401, "digest auth failed",
                            headers, None)
        else:
            self.retried += 1
        if authreq:
            scheme = authreq.split()[0]
            if scheme.lower() == 'digest':
                return self.retry_http_digest_auth(req, authreq)

    def retry_http_digest_auth(self, req, auth):
        token, challenge = auth.split(' ', 1)
        chal = parse_keqv_list(parse_http_list(challenge))
        auth = self.get_authorization(req, chal)
        if auth:
            auth_val = 'Digest %s' % auth
            if req.headers.get(self.auth_header, None) == auth_val:
                return None
            newreq = copy.copy(req)
            newreq.add_unredirected_header(self.auth_header, auth_val)
            newreq.visit = False
            return self.parent.open(newreq)

    def get_cnonce(self, nonce):
        # The cnonce-value is an opaque
        # quoted string value provided by the client and used by both client
        # and server to avoid chosen plaintext attacks, to provide mutual
        # authentication, and to provide some message integrity protection.
        # This isn't a fabulous effort, but it's probably Good Enough.
        dig = sha.new("%s:%s:%s:%s" % (self.nonce_count, nonce, time.ctime(),
                                       randombytes(8))).hexdigest()
        return dig[:16]

    def get_authorization(self, req, chal):
        try:
            realm = chal['realm']
            nonce = chal['nonce']
            qop = chal.get('qop')
            algorithm = chal.get('algorithm', 'MD5')
            # mod_digest doesn't send an opaque, even though it isn't
            # supposed to be optional
            opaque = chal.get('opaque', None)
        except KeyError:
            return None

        H, KD = self.get_algorithm_impls(algorithm)
        if H is None:
            return None

        user, pw = self.passwd.find_user_password(realm, req.get_full_url())
        if user is None:
            return None

        # XXX not implemented yet
        if req.has_data():
            entdig = self.get_entity_digest(req.get_data(), chal)
        else:
            entdig = None

        A1 = "%s:%s:%s" % (user, realm, pw)
        A2 = "%s:%s" % (req.get_method(),
                        # XXX selector: what about proxies and full urls
                        req.get_selector())
        if qop == 'auth':
            self.nonce_count += 1
            ncvalue = '%08x' % self.nonce_count
            cnonce = self.get_cnonce(nonce)
            noncebit = "%s:%s:%s:%s:%s" % (nonce, ncvalue, cnonce, qop, H(A2))
            respdig = KD(H(A1), noncebit)
        elif qop is None:
            respdig = KD(H(A1), "%s:%s" % (nonce, H(A2)))
        else:
            # XXX handle auth-int.
            pass

        # XXX should the partial digests be encoded too?

        base = 'username="%s", realm="%s", nonce="%s", uri="%s", ' \
               'response="%s"' % (user, realm, nonce, req.get_selector(),
                                  respdig)
        if opaque:
            base += ', opaque="%s"' % opaque
        if entdig:
            base += ', digest="%s"' % entdig
        base += ', algorithm="%s"' % algorithm
        if qop:
            base += ', qop=auth, nc=%s, cnonce="%s"' % (ncvalue, cnonce)
        return base

    def get_algorithm_impls(self, algorithm):
        # lambdas assume digest modules are imported at the top level
        if algorithm == 'MD5':
            H = lambda x: md5.new(x).hexdigest()
        elif algorithm == 'SHA':
            H = lambda x: sha.new(x).hexdigest()
        # XXX MD5-sess
        KD = lambda s, d: H("%s:%s" % (s, d))
        return H, KD

    def get_entity_digest(self, data, chal):
        # XXX not implemented yet
        return None


class HTTPDigestAuthHandler(BaseHandler, AbstractDigestAuthHandler):
    """An authentication protocol defined by RFC 2069

    Digest authentication improves on basic authentication because it
    does not transmit passwords in the clear.
    """

    auth_header = 'Authorization'
    handler_order = 490

    def http_error_401(self, req, fp, code, msg, headers):
        host = urlparse.urlparse(req.get_full_url())[1]
        retry = self.http_error_auth_reqed('www-authenticate',
                                           host, req, headers)
        self.reset_retry_count()
        return retry


class ProxyDigestAuthHandler(BaseHandler, AbstractDigestAuthHandler):

    auth_header = 'Proxy-Authorization'
    handler_order = 490

    def http_error_407(self, req, fp, code, msg, headers):
        host = req.get_host()
        retry = self.http_error_auth_reqed('proxy-authenticate',
                                           host, req, headers)
        self.reset_retry_count()
        return retry


# XXX ugly implementation, should probably not bother deriving
class HTTPProxyPasswordMgr(HTTPPasswordMgr):
    # has default realm and host/port
    def add_password(self, realm, uri, user, passwd):
        # uri could be a single URI or a sequence
        if uri is None or isinstance(uri, basestring):
            uris = [uri]
        else:
            uris = uri
        passwd_by_domain = self.passwd.setdefault(realm, {})
        for uri in uris:
            for default_port in True, False:
                reduced_uri = self.reduce_uri(uri, default_port)
                passwd_by_domain[reduced_uri] = (user, passwd)

    def find_user_password(self, realm, authuri):
        attempts = [(realm, authuri), (None, authuri)]
        # bleh, want default realm to take precedence over default
        # URI/authority, hence this outer loop
        for default_uri in False, True:
            for realm, authuri in attempts:
                authinfo_by_domain = self.passwd.get(realm, {})
                for default_port in True, False:
                    reduced_authuri = self.reduce_uri(authuri, default_port)
                    for uri, authinfo in authinfo_by_domain.iteritems():
                        if uri is None and not default_uri:
                            continue
                        if self.is_suburi(uri, reduced_authuri):
                            return authinfo
                    user, password = None, None

                    if user is not None:
                        break
        return user, password

    def reduce_uri(self, uri, default_port=True):
        if uri is None:
            return None
        return HTTPPasswordMgr.reduce_uri(self, uri, default_port)

    def is_suburi(self, base, test):
        if base is None:
            # default to the proxy's host/port
            hostport, path = test
            base = (hostport, "/")
        return HTTPPasswordMgr.is_suburi(self, base, test)


class HTTPSClientCertMgr(HTTPPasswordMgr):
    # implementation inheritance: this is not a proper subclass
    def add_key_cert(self, uri, key_file, cert_file):
        self.add_password(None, uri, key_file, cert_file)
    def find_key_cert(self, authuri):
        return HTTPPasswordMgr.find_user_password(self, None, authuri)
