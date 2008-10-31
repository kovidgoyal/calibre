"""
httpauth modules defines functions to implement HTTP Digest Authentication (RFC 2617).
This has full compliance with 'Digest' and 'Basic' authentication methods. In
'Digest' it supports both MD5 and MD5-sess algorithms.

Usage:

    First use 'doAuth' to request the client authentication for a
    certain resource. You should send an httplib.UNAUTHORIZED response to the
    client so he knows he has to authenticate itself.
    
    Then use 'parseAuthorization' to retrieve the 'auth_map' used in
    'checkResponse'.

    To use 'checkResponse' you must have already verified the password associated
    with the 'username' key in 'auth_map' dict. Then you use the 'checkResponse'
    function to verify if the password matches the one sent by the client.

SUPPORTED_ALGORITHM - list of supported 'Digest' algorithms
SUPPORTED_QOP - list of supported 'Digest' 'qop'.
"""
__version__ = 1, 0, 1
__author__ = "Tiago Cogumbreiro <cogumbreiro@users.sf.net>"
__credits__ = """
    Peter van Kampen for its recipe which implement most of Digest authentication:
    http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/302378
"""

__license__ = """
Copyright (c) 2005, Tiago Cogumbreiro <cogumbreiro@users.sf.net>
All rights reserved.

Redistribution and use in source and binary forms, with or without modification, 
are permitted provided that the following conditions are met:

    * Redistributions of source code must retain the above copyright notice, 
      this list of conditions and the following disclaimer.
    * Redistributions in binary form must reproduce the above copyright notice, 
      this list of conditions and the following disclaimer in the documentation 
      and/or other materials provided with the distribution.
    * Neither the name of Sylvain Hellegouarch nor the names of his contributors 
      may be used to endorse or promote products derived from this software 
      without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND 
ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED 
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE 
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE 
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL 
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR 
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER 
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, 
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE 
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

__all__ = ("digestAuth", "basicAuth", "doAuth", "checkResponse",
           "parseAuthorization", "SUPPORTED_ALGORITHM", "md5SessionKey",
           "calculateNonce", "SUPPORTED_QOP")

################################################################################
import md5
import time
import base64
import urllib2

MD5 = "MD5"
MD5_SESS = "MD5-sess"
AUTH = "auth"
AUTH_INT = "auth-int"

SUPPORTED_ALGORITHM = (MD5, MD5_SESS)
SUPPORTED_QOP = (AUTH, AUTH_INT)

################################################################################
# doAuth
#
DIGEST_AUTH_ENCODERS = {
    MD5: lambda val: md5.new (val).hexdigest (),
    MD5_SESS: lambda val: md5.new (val).hexdigest (),
#    SHA: lambda val: sha.new (val).hexdigest (),
}

def calculateNonce (realm, algorithm = MD5):
    """This is an auxaliary function that calculates 'nonce' value. It is used
    to handle sessions."""

    global SUPPORTED_ALGORITHM, DIGEST_AUTH_ENCODERS
    assert algorithm in SUPPORTED_ALGORITHM

    try:
        encoder = DIGEST_AUTH_ENCODERS[algorithm]
    except KeyError:
        raise NotImplementedError ("The chosen algorithm (%s) does not have "\
                                   "an implementation yet" % algorithm)

    return encoder ("%d:%s" % (time.time(), realm))

def digestAuth (realm, algorithm = MD5, nonce = None, qop = AUTH):
    """Challenges the client for a Digest authentication."""
    global SUPPORTED_ALGORITHM, DIGEST_AUTH_ENCODERS, SUPPORTED_QOP
    assert algorithm in SUPPORTED_ALGORITHM
    assert qop in SUPPORTED_QOP

    if nonce is None:
        nonce = calculateNonce (realm, algorithm)

    return 'Digest realm="%s", nonce="%s", algorithm="%s", qop="%s"' % (
        realm, nonce, algorithm, qop
    )

def basicAuth (realm):
    """Challengenes the client for a Basic authentication."""
    assert '"' not in realm, "Realms cannot contain the \" (quote) character."

    return 'Basic realm="%s"' % realm

def doAuth (realm):
    """'doAuth' function returns the challenge string b giving priority over
    Digest and fallback to Basic authentication when the browser doesn't
    support the first one.
    
    This should be set in the HTTP header under the key 'WWW-Authenticate'."""

    return digestAuth (realm) + " " + basicAuth (realm)


################################################################################
# Parse authorization parameters
#
def _parseDigestAuthorization (auth_params):
    # Convert the auth params to a dict
    items = urllib2.parse_http_list (auth_params)
    params = urllib2.parse_keqv_list (items)

    # Now validate the params

    # Check for required parameters
    required = ["username", "realm", "nonce", "uri", "response"]
    for k in required:
        if not params.has_key(k):
            return None

    # If qop is sent then cnonce and nc MUST be present
    if params.has_key("qop") and not (params.has_key("cnonce") \
                                      and params.has_key("nc")):
        return None

    # If qop is not sent, neither cnonce nor nc can be present
    if (params.has_key("cnonce") or params.has_key("nc")) and \
       not params.has_key("qop"):
        return None

    return params


def _parseBasicAuthorization (auth_params):
    username, password = base64.decodestring (auth_params).split (":", 1)
    return {"username": username, "password": password}

AUTH_SCHEMES = {
    "basic": _parseBasicAuthorization,
    "digest": _parseDigestAuthorization,
}

def parseAuthorization (credentials):
    """parseAuthorization will convert the value of the 'Authorization' key in
    the HTTP header to a map itself. If the parsing fails 'None' is returned.
    """

    global AUTH_SCHEMES

    auth_scheme, auth_params  = credentials.split(" ", 1)
    auth_scheme = auth_scheme.lower ()

    parser = AUTH_SCHEMES[auth_scheme]
    params = parser (auth_params)

    if params is None:
        return

    assert "auth_scheme" not in params
    params["auth_scheme"] = auth_scheme
    return params


################################################################################
# Check provided response for a valid password
#
def md5SessionKey (params, password):
    """
    If the "algorithm" directive's value is "MD5-sess", then A1 
    [the session key] is calculated only once - on the first request by the
    client following receipt of a WWW-Authenticate challenge from the server.

    This creates a 'session key' for the authentication of subsequent
    requests and responses which is different for each "authentication
    session", thus limiting the amount of material hashed with any one
    key.

    Because the server need only use the hash of the user
    credentials in order to create the A1 value, this construction could
    be used in conjunction with a third party authentication service so
    that the web server would not need the actual password value.  The
    specification of such a protocol is beyond the scope of this
    specification.
"""

    keys = ("username", "realm", "nonce", "cnonce")
    params_copy = {}
    for key in keys:
        params_copy[key] = params[key]

    params_copy["algorithm"] = MD5_SESS
    return _A1 (params_copy, password)

def _A1(params, password):
    algorithm = params.get ("algorithm", MD5)
    H = DIGEST_AUTH_ENCODERS[algorithm]

    if algorithm == MD5:
        # If the "algorithm" directive's value is "MD5" or is
        # unspecified, then A1 is:
        # A1 = unq(username-value) ":" unq(realm-value) ":" passwd
        return "%s:%s:%s" % (params["username"], params["realm"], password)

    elif algorithm == MD5_SESS:

        # This is A1 if qop is set
        # A1 = H( unq(username-value) ":" unq(realm-value) ":" passwd )
        #         ":" unq(nonce-value) ":" unq(cnonce-value)
        h_a1 = H ("%s:%s:%s" % (params["username"], params["realm"], password))
        return "%s:%s:%s" % (h_a1, params["nonce"], params["cnonce"])


def _A2(params, method, kwargs):
    # If the "qop" directive's value is "auth" or is unspecified, then A2 is:
    # A2 = Method ":" digest-uri-value

    qop = params.get ("qop", "auth")
    if qop == "auth":
        return method + ":" + params["uri"]
    elif qop == "auth-int":
        # If the "qop" value is "auth-int", then A2 is:
        # A2 = Method ":" digest-uri-value ":" H(entity-body)
        entity_body = kwargs.get ("entity_body", "")
        H = kwargs["H"]

        return "%s:%s:%s" % (
            method,
            params["uri"],
            H(entity_body)
        )

    else:
        raise NotImplementedError ("The 'qop' method is unknown: %s" % qop)

def _computeDigestResponse(auth_map, password, method = "GET", A1 = None,**kwargs):
    """
    Generates a response respecting the algorithm defined in RFC 2617
    """
    params = auth_map

    algorithm = params.get ("algorithm", MD5)

    H = DIGEST_AUTH_ENCODERS[algorithm]
    KD = lambda secret, data: H(secret + ":" + data)

    qop = params.get ("qop", None)

    H_A2 = H(_A2(params, method, kwargs))

    if algorithm == MD5_SESS and A1 is not None:
        H_A1 = H(A1)
    else:
        H_A1 = H(_A1(params, password))

    if qop == "auth" or aop == "auth-int":
        # If the "qop" value is "auth" or "auth-int":
        # request-digest  = <"> < KD ( H(A1),     unq(nonce-value)
        #                              ":" nc-value
        #                              ":" unq(cnonce-value)
        #                              ":" unq(qop-value)
        #                              ":" H(A2)
        #                      ) <">
        request = "%s:%s:%s:%s:%s" % (
            params["nonce"],
            params["nc"],
            params["cnonce"],
            params["qop"],
            H_A2,
        )

    elif qop is None:
        # If the "qop" directive is not present (this construction is
        # for compatibility with RFC 2069):
        # request-digest  =
        #         <"> < KD ( H(A1), unq(nonce-value) ":" H(A2) ) > <">
        request = "%s:%s" % (params["nonce"], H_A2)

    return KD(H_A1, request)

def _checkDigestResponse(auth_map, password, method = "GET", A1 = None, **kwargs):
    """This function is used to verify the response given by the client when
    he tries to authenticate.
    Optional arguments:
     entity_body - when 'qop' is set to 'auth-int' you MUST provide the
                   raw data you are going to send to the client (usually the
                   HTML page.
     request_uri - the uri from the request line compared with the 'uri'
                   directive of the authorization map. They must represent
                   the same resource (unused at this time).
    """

    if auth_map['realm'] != kwargs.get('realm', None):
        return False

    response =  _computeDigestResponse(auth_map, password, method, A1,**kwargs)

    return response == auth_map["response"]

def _checkBasicResponse (auth_map, password, method='GET', encrypt=None, **kwargs):
    # Note that the Basic response doesn't provide the realm value so we cannot
    # test it
    try:
        return encrypt(auth_map["password"], auth_map["username"]) == password
    except TypeError:
        return encrypt(auth_map["password"]) == password

AUTH_RESPONSES = {
    "basic": _checkBasicResponse,
    "digest": _checkDigestResponse,
}

def checkResponse (auth_map, password, method = "GET", encrypt=None, **kwargs):
    """'checkResponse' compares the auth_map with the password and optionally
    other arguments that each implementation might need.
    
    If the response is of type 'Basic' then the function has the following
    signature:
    
    checkBasicResponse (auth_map, password) -> bool
    
    If the response is of type 'Digest' then the function has the following
    signature:
    
    checkDigestResponse (auth_map, password, method = 'GET', A1 = None) -> bool
    
    The 'A1' argument is only used in MD5_SESS algorithm based responses.
    Check md5SessionKey() for more info.
    """
    global AUTH_RESPONSES
    checker = AUTH_RESPONSES[auth_map["auth_scheme"]]
    return checker (auth_map, password, method=method, encrypt=encrypt, **kwargs)
 



