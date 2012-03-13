# This file is part of CherryPy <http://www.cherrypy.org/>
# -*- coding: utf-8 -*-
# vim:ts=4:sw=4:expandtab:fileencoding=utf-8

__doc__ = """An implementation of the server-side of HTTP Digest Access
Authentication, which is described in :rfc:`2617`.

Example usage, using the built-in get_ha1_dict_plain function which uses a dict
of plaintext passwords as the credentials store::

    userpassdict = {'alice' : '4x5istwelve'}
    get_ha1 = cherrypy.lib.auth_digest.get_ha1_dict_plain(userpassdict)
    digest_auth = {'tools.auth_digest.on': True,
                   'tools.auth_digest.realm': 'wonderland',
                   'tools.auth_digest.get_ha1': get_ha1,
                   'tools.auth_digest.key': 'a565c27146791cfb',
    }
    app_config = { '/' : digest_auth }
"""

__author__ = 'visteya'
__date__ = 'April 2009'


import time
from cherrypy._cpcompat import parse_http_list, parse_keqv_list

import cherrypy
from cherrypy._cpcompat import md5, ntob
md5_hex = lambda s: md5(ntob(s)).hexdigest()

qop_auth = 'auth'
qop_auth_int = 'auth-int'
valid_qops = (qop_auth, qop_auth_int)

valid_algorithms = ('MD5', 'MD5-sess')


def TRACE(msg):
    cherrypy.log(msg, context='TOOLS.AUTH_DIGEST')

# Three helper functions for users of the tool, providing three variants
# of get_ha1() functions for three different kinds of credential stores.
def get_ha1_dict_plain(user_password_dict):
    """Returns a get_ha1 function which obtains a plaintext password from a
    dictionary of the form: {username : password}.

    If you want a simple dictionary-based authentication scheme, with plaintext
    passwords, use get_ha1_dict_plain(my_userpass_dict) as the value for the
    get_ha1 argument to digest_auth().
    """
    def get_ha1(realm, username):
        password = user_password_dict.get(username)
        if password:
            return md5_hex('%s:%s:%s' % (username, realm, password))
        return None

    return get_ha1

def get_ha1_dict(user_ha1_dict):
    """Returns a get_ha1 function which obtains a HA1 password hash from a
    dictionary of the form: {username : HA1}.

    If you want a dictionary-based authentication scheme, but with
    pre-computed HA1 hashes instead of plain-text passwords, use
    get_ha1_dict(my_userha1_dict) as the value for the get_ha1
    argument to digest_auth().
    """
    def get_ha1(realm, username):
        return user_ha1_dict.get(user)

    return get_ha1

def get_ha1_file_htdigest(filename):
    """Returns a get_ha1 function which obtains a HA1 password hash from a
    flat file with lines of the same format as that produced by the Apache
    htdigest utility. For example, for realm 'wonderland', username 'alice',
    and password '4x5istwelve', the htdigest line would be::

        alice:wonderland:3238cdfe91a8b2ed8e39646921a02d4c

    If you want to use an Apache htdigest file as the credentials store,
    then use get_ha1_file_htdigest(my_htdigest_file) as the value for the
    get_ha1 argument to digest_auth().  It is recommended that the filename
    argument be an absolute path, to avoid problems.
    """
    def get_ha1(realm, username):
        result = None
        f = open(filename, 'r')
        for line in f:
            u, r, ha1 = line.rstrip().split(':')
            if u == username and r == realm:
                result = ha1
                break
        f.close()
        return result

    return get_ha1


def synthesize_nonce(s, key, timestamp=None):
    """Synthesize a nonce value which resists spoofing and can be checked for staleness.
    Returns a string suitable as the value for 'nonce' in the www-authenticate header.

    s
        A string related to the resource, such as the hostname of the server.

    key
        A secret string known only to the server.
    
    timestamp
        An integer seconds-since-the-epoch timestamp
    
    """
    if timestamp is None:
        timestamp = int(time.time())
    h = md5_hex('%s:%s:%s' % (timestamp, s, key))
    nonce = '%s:%s' % (timestamp, h)
    return nonce


def H(s):
    """The hash function H"""
    return md5_hex(s)


class HttpDigestAuthorization (object):
    """Class to parse a Digest Authorization header and perform re-calculation
    of the digest.
    """

    def errmsg(self, s):
        return 'Digest Authorization header: %s' % s

    def __init__(self, auth_header, http_method, debug=False):
        self.http_method = http_method
        self.debug = debug
        scheme, params  = auth_header.split(" ", 1)
        self.scheme = scheme.lower()
        if self.scheme != 'digest':
            raise ValueError('Authorization scheme is not "Digest"')

        self.auth_header = auth_header

        # make a dict of the params
        items = parse_http_list(params)
        paramsd = parse_keqv_list(items)

        self.realm = paramsd.get('realm')
        self.username = paramsd.get('username')
        self.nonce = paramsd.get('nonce')
        self.uri = paramsd.get('uri')
        self.method = paramsd.get('method')
        self.response = paramsd.get('response') # the response digest
        self.algorithm = paramsd.get('algorithm', 'MD5')
        self.cnonce = paramsd.get('cnonce')
        self.opaque = paramsd.get('opaque')
        self.qop = paramsd.get('qop') # qop
        self.nc = paramsd.get('nc') # nonce count

        # perform some correctness checks
        if self.algorithm not in valid_algorithms:
            raise ValueError(self.errmsg("Unsupported value for algorithm: '%s'" % self.algorithm))

        has_reqd = self.username and \
                   self.realm and \
                   self.nonce and \
                   self.uri and \
                   self.response
        if not has_reqd:
            raise ValueError(self.errmsg("Not all required parameters are present."))

        if self.qop:
            if self.qop not in valid_qops:
                raise ValueError(self.errmsg("Unsupported value for qop: '%s'" % self.qop))
            if not (self.cnonce and self.nc):
                raise ValueError(self.errmsg("If qop is sent then cnonce and nc MUST be present"))
        else:
            if self.cnonce or self.nc:
                raise ValueError(self.errmsg("If qop is not sent, neither cnonce nor nc can be present"))


    def __str__(self):
        return 'authorization : %s' % self.auth_header

    def validate_nonce(self, s, key):
        """Validate the nonce.
        Returns True if nonce was generated by synthesize_nonce() and the timestamp
        is not spoofed, else returns False.

        s
            A string related to the resource, such as the hostname of the server.
            
        key
            A secret string known only to the server.
        
        Both s and key must be the same values which were used to synthesize the nonce
        we are trying to validate.
        """
        try:
            timestamp, hashpart = self.nonce.split(':', 1)
            s_timestamp, s_hashpart = synthesize_nonce(s, key, timestamp).split(':', 1)
            is_valid = s_hashpart == hashpart
            if self.debug:
                TRACE('validate_nonce: %s' % is_valid)
            return is_valid
        except ValueError: # split() error
            pass
        return False


    def is_nonce_stale(self, max_age_seconds=600):
        """Returns True if a validated nonce is stale. The nonce contains a
        timestamp in plaintext and also a secure hash of the timestamp. You should
        first validate the nonce to ensure the plaintext timestamp is not spoofed.
        """
        try:
            timestamp, hashpart = self.nonce.split(':', 1)
            if int(timestamp) + max_age_seconds > int(time.time()):
                return False
        except ValueError: # int() error
            pass
        if self.debug:
            TRACE("nonce is stale")
        return True


    def HA2(self, entity_body=''):
        """Returns the H(A2) string. See :rfc:`2617` section 3.2.2.3."""
        # RFC 2617 3.2.2.3
        # If the "qop" directive's value is "auth" or is unspecified, then A2 is:
        #    A2 = method ":" digest-uri-value
        #
        # If the "qop" value is "auth-int", then A2 is:
        #    A2 = method ":" digest-uri-value ":" H(entity-body)
        if self.qop is None or self.qop == "auth":
            a2 = '%s:%s' % (self.http_method, self.uri)
        elif self.qop == "auth-int":
            a2 = "%s:%s:%s" % (self.http_method, self.uri, H(entity_body))
        else:
            # in theory, this should never happen, since I validate qop in __init__()
            raise ValueError(self.errmsg("Unrecognized value for qop!"))
        return H(a2)


    def request_digest(self, ha1, entity_body=''):
        """Calculates the Request-Digest. See :rfc:`2617` section 3.2.2.1.

        ha1
            The HA1 string obtained from the credentials store.

        entity_body
            If 'qop' is set to 'auth-int', then A2 includes a hash
            of the "entity body".  The entity body is the part of the
            message which follows the HTTP headers. See :rfc:`2617` section
            4.3.  This refers to the entity the user agent sent in the request which
            has the Authorization header. Typically GET requests don't have an entity,
            and POST requests do.
        
        """
        ha2 = self.HA2(entity_body)
        # Request-Digest -- RFC 2617 3.2.2.1
        if self.qop:
            req = "%s:%s:%s:%s:%s" % (self.nonce, self.nc, self.cnonce, self.qop, ha2)
        else:
            req = "%s:%s" % (self.nonce, ha2)

        # RFC 2617 3.2.2.2
        #
        # If the "algorithm" directive's value is "MD5" or is unspecified, then A1 is:
        # A1 = unq(username-value) ":" unq(realm-value) ":" passwd
        #
        # If the "algorithm" directive's value is "MD5-sess", then A1 is
        # calculated only once - on the first request by the client following
        # receipt of a WWW-Authenticate challenge from the server.
        # A1 = H( unq(username-value) ":" unq(realm-value) ":" passwd )
        #         ":" unq(nonce-value) ":" unq(cnonce-value)
        if self.algorithm == 'MD5-sess':
            ha1 = H('%s:%s:%s' % (ha1, self.nonce, self.cnonce))

        digest = H('%s:%s' % (ha1, req))
        return digest



def www_authenticate(realm, key, algorithm='MD5', nonce=None, qop=qop_auth, stale=False):
    """Constructs a WWW-Authenticate header for Digest authentication."""
    if qop not in valid_qops:
        raise ValueError("Unsupported value for qop: '%s'" % qop)
    if algorithm not in valid_algorithms:
        raise ValueError("Unsupported value for algorithm: '%s'" % algorithm)

    if nonce is None:
        nonce = synthesize_nonce(realm, key)
    s = 'Digest realm="%s", nonce="%s", algorithm="%s", qop="%s"' % (
                realm, nonce, algorithm, qop)
    if stale:
        s += ', stale="true"'
    return s


def digest_auth(realm, get_ha1, key, debug=False):
    """A CherryPy tool which hooks at before_handler to perform
    HTTP Digest Access Authentication, as specified in :rfc:`2617`.
    
    If the request has an 'authorization' header with a 'Digest' scheme, this
    tool authenticates the credentials supplied in that header.  If
    the request has no 'authorization' header, or if it does but the scheme is
    not "Digest", or if authentication fails, the tool sends a 401 response with
    a 'WWW-Authenticate' Digest header.
    
    realm
        A string containing the authentication realm.
    
    get_ha1
        A callable which looks up a username in a credentials store
        and returns the HA1 string, which is defined in the RFC to be
        MD5(username : realm : password).  The function's signature is:
        ``get_ha1(realm, username)``
        where username is obtained from the request's 'authorization' header.
        If username is not found in the credentials store, get_ha1() returns
        None.
    
    key
        A secret string known only to the server, used in the synthesis of nonces.
    
    """
    request = cherrypy.serving.request
    
    auth_header = request.headers.get('authorization')
    nonce_is_stale = False
    if auth_header is not None:
        try:
            auth = HttpDigestAuthorization(auth_header, request.method, debug=debug)
        except ValueError:
            raise cherrypy.HTTPError(400, "The Authorization header could not be parsed.")
        
        if debug:
            TRACE(str(auth))
        
        if auth.validate_nonce(realm, key):
            ha1 = get_ha1(realm, auth.username)
            if ha1 is not None:
                # note that for request.body to be available we need to hook in at
                # before_handler, not on_start_resource like 3.1.x digest_auth does.
                digest = auth.request_digest(ha1, entity_body=request.body)
                if digest == auth.response: # authenticated
                    if debug:
                        TRACE("digest matches auth.response")
                    # Now check if nonce is stale.
                    # The choice of ten minutes' lifetime for nonce is somewhat arbitrary
                    nonce_is_stale = auth.is_nonce_stale(max_age_seconds=600)
                    if not nonce_is_stale:
                        request.login = auth.username
                        if debug:
                            TRACE("authentication of %s successful" % auth.username)
                        return
    
    # Respond with 401 status and a WWW-Authenticate header
    header = www_authenticate(realm, key, stale=nonce_is_stale)
    if debug:
        TRACE(header)
    cherrypy.serving.response.headers['WWW-Authenticate'] = header
    raise cherrypy.HTTPError(401, "You are not authorized to access that resource")

