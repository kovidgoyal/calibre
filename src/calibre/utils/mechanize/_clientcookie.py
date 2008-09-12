"""HTTP cookie handling for web clients.

This module originally developed from my port of Gisle Aas' Perl module
HTTP::Cookies, from the libwww-perl library.

Docstrings, comments and debug strings in this code refer to the
attributes of the HTTP cookie system as cookie-attributes, to distinguish
them clearly from Python attributes.

                        CookieJar____
                        /     \      \
            FileCookieJar      \      \
             /    |   \         \      \
 MozillaCookieJar | LWPCookieJar \      \
                  |               |      \
                  |   ---MSIEBase |       \
                  |  /      |     |        \
                  | /   MSIEDBCookieJar BSDDBCookieJar
                  |/    
               MSIECookieJar

Comments to John J Lee <jjl@pobox.com>.


Copyright 2002-2006 John J Lee <jjl@pobox.com>
Copyright 1997-1999 Gisle Aas (original libwww-perl code)
Copyright 2002-2003 Johnny Lee (original MSIE Perl code)

This code is free software; you can redistribute it and/or modify it
under the terms of the BSD or ZPL 2.1 licenses (see the file
COPYING.txt included with the distribution).

"""

import sys, re, copy, time, struct, urllib, types, logging
try:
    import threading
    _threading = threading; del threading
except ImportError:
    import dummy_threading
    _threading = dummy_threading; del dummy_threading
import httplib  # only for the default HTTP port

MISSING_FILENAME_TEXT = ("a filename was not supplied (nor was the CookieJar "
                         "instance initialised with one)")
DEFAULT_HTTP_PORT = str(httplib.HTTP_PORT)

from _headersutil import split_header_words, parse_ns_headers
from _util import isstringlike
import _rfc3986

debug = logging.getLogger("mechanize.cookies").debug


def reraise_unmasked_exceptions(unmasked=()):
    # There are a few catch-all except: statements in this module, for
    # catching input that's bad in unexpected ways.
    # This function re-raises some exceptions we don't want to trap.
    import mechanize, warnings
    if not mechanize.USE_BARE_EXCEPT:
        raise
    unmasked = unmasked + (KeyboardInterrupt, SystemExit, MemoryError)
    etype = sys.exc_info()[0]
    if issubclass(etype, unmasked):
        raise
    # swallowed an exception
    import traceback, StringIO
    f = StringIO.StringIO()
    traceback.print_exc(None, f)
    msg = f.getvalue()
    warnings.warn("mechanize bug!\n%s" % msg, stacklevel=2)


IPV4_RE = re.compile(r"\.\d+$")
def is_HDN(text):
    """Return True if text is a host domain name."""
    # XXX
    # This may well be wrong.  Which RFC is HDN defined in, if any (for
    #  the purposes of RFC 2965)?
    # For the current implementation, what about IPv6?  Remember to look
    #  at other uses of IPV4_RE also, if change this.
    return not (IPV4_RE.search(text) or
                text == "" or
                text[0] == "." or text[-1] == ".")

def domain_match(A, B):
    """Return True if domain A domain-matches domain B, according to RFC 2965.

    A and B may be host domain names or IP addresses.

    RFC 2965, section 1:

    Host names can be specified either as an IP address or a HDN string.
    Sometimes we compare one host name with another.  (Such comparisons SHALL
    be case-insensitive.)  Host A's name domain-matches host B's if

         *  their host name strings string-compare equal; or

         * A is a HDN string and has the form NB, where N is a non-empty
            name string, B has the form .B', and B' is a HDN string.  (So,
            x.y.com domain-matches .Y.com but not Y.com.)

    Note that domain-match is not a commutative operation: a.b.c.com
    domain-matches .c.com, but not the reverse.

    """
    # Note that, if A or B are IP addresses, the only relevant part of the
    # definition of the domain-match algorithm is the direct string-compare.
    A = A.lower()
    B = B.lower()
    if A == B:
        return True
    if not is_HDN(A):
        return False
    i = A.rfind(B)
    has_form_nb = not (i == -1 or i == 0)
    return (
        has_form_nb and
        B.startswith(".") and
        is_HDN(B[1:])
        )

def liberal_is_HDN(text):
    """Return True if text is a sort-of-like a host domain name.

    For accepting/blocking domains.

    """
    return not IPV4_RE.search(text)

def user_domain_match(A, B):
    """For blocking/accepting domains.

    A and B may be host domain names or IP addresses.

    """
    A = A.lower()
    B = B.lower()
    if not (liberal_is_HDN(A) and liberal_is_HDN(B)):
        if A == B:
            # equal IP addresses
            return True
        return False
    initial_dot = B.startswith(".")
    if initial_dot and A.endswith(B):
        return True
    if not initial_dot and A == B:
        return True
    return False

cut_port_re = re.compile(r":\d+$")
def request_host(request):
    """Return request-host, as defined by RFC 2965.

    Variation from RFC: returned value is lowercased, for convenient
    comparison.

    """
    url = request.get_full_url()
    host = _rfc3986.urlsplit(url)[1]
    if host is None:
        host = request.get_header("Host", "")

    # remove port, if present
    host = cut_port_re.sub("", host, 1)
    return host.lower()

def eff_request_host(request):
    """Return a tuple (request-host, effective request-host name).

    As defined by RFC 2965, except both are lowercased.

    """
    erhn = req_host = request_host(request)
    if req_host.find(".") == -1 and not IPV4_RE.search(req_host):
        erhn = req_host + ".local"
    return req_host, erhn

def request_path(request):
    """request-URI, as defined by RFC 2965."""
    url = request.get_full_url()
    path, query, frag = _rfc3986.urlsplit(url)[2:]
    path = escape_path(path)
    req_path = _rfc3986.urlunsplit((None, None, path, query, frag))
    if not req_path.startswith("/"):
        req_path = "/"+req_path
    return req_path

def request_port(request):
    host = request.get_host()
    i = host.find(':')
    if i >= 0:
        port = host[i+1:]
        try:
            int(port)
        except ValueError:
            debug("nonnumeric port: '%s'", port)
            return None
    else:
        port = DEFAULT_HTTP_PORT
    return port

# Characters in addition to A-Z, a-z, 0-9, '_', '.', and '-' that don't
# need to be escaped to form a valid HTTP URL (RFCs 2396 and 1738).
HTTP_PATH_SAFE = "%/;:@&=+$,!~*'()"
ESCAPED_CHAR_RE = re.compile(r"%([0-9a-fA-F][0-9a-fA-F])")
def uppercase_escaped_char(match):
    return "%%%s" % match.group(1).upper()
def escape_path(path):
    """Escape any invalid characters in HTTP URL, and uppercase all escapes."""
    # There's no knowing what character encoding was used to create URLs
    # containing %-escapes, but since we have to pick one to escape invalid
    # path characters, we pick UTF-8, as recommended in the HTML 4.0
    # specification:
    # http://www.w3.org/TR/REC-html40/appendix/notes.html#h-B.2.1
    # And here, kind of: draft-fielding-uri-rfc2396bis-03
    # (And in draft IRI specification: draft-duerst-iri-05)
    # (And here, for new URI schemes: RFC 2718)
    if isinstance(path, types.UnicodeType):
        path = path.encode("utf-8")
    path = urllib.quote(path, HTTP_PATH_SAFE)
    path = ESCAPED_CHAR_RE.sub(uppercase_escaped_char, path)
    return path

def reach(h):
    """Return reach of host h, as defined by RFC 2965, section 1.

    The reach R of a host name H is defined as follows:

       *  If

          -  H is the host domain name of a host; and,

          -  H has the form A.B; and

          -  A has no embedded (that is, interior) dots; and

          -  B has at least one embedded dot, or B is the string "local".
             then the reach of H is .B.

       *  Otherwise, the reach of H is H.

    >>> reach("www.acme.com")
    '.acme.com'
    >>> reach("acme.com")
    'acme.com'
    >>> reach("acme.local")
    '.local'

    """
    i = h.find(".")
    if i >= 0:
        #a = h[:i]  # this line is only here to show what a is
        b = h[i+1:]
        i = b.find(".")
        if is_HDN(h) and (i >= 0 or b == "local"):
            return "."+b
    return h

def is_third_party(request):
    """

    RFC 2965, section 3.3.6:

        An unverifiable transaction is to a third-party host if its request-
        host U does not domain-match the reach R of the request-host O in the
        origin transaction.

    """
    req_host = request_host(request)
    # the origin request's request-host was stuffed into request by
    # _urllib2_support.AbstractHTTPHandler
    return not domain_match(req_host, reach(request.origin_req_host))


class Cookie:
    """HTTP Cookie.

    This class represents both Netscape and RFC 2965 cookies.

    This is deliberately a very simple class.  It just holds attributes.  It's
    possible to construct Cookie instances that don't comply with the cookie
    standards.  CookieJar.make_cookies is the factory function for Cookie
    objects -- it deals with cookie parsing, supplying defaults, and
    normalising to the representation used in this class.  CookiePolicy is
    responsible for checking them to see whether they should be accepted from
    and returned to the server.

    version: integer;
    name: string;
    value: string (may be None);
    port: string; None indicates no attribute was supplied (eg. "Port", rather
     than eg. "Port=80"); otherwise, a port string (eg. "80") or a port list
     string (eg. "80,8080")
    port_specified: boolean; true if a value was supplied with the Port
     cookie-attribute
    domain: string;
    domain_specified: boolean; true if Domain was explicitly set
    domain_initial_dot: boolean; true if Domain as set in HTTP header by server
     started with a dot (yes, this really is necessary!)
    path: string;
    path_specified: boolean; true if Path was explicitly set
    secure:  boolean; true if should only be returned over secure connection
    expires: integer; seconds since epoch (RFC 2965 cookies should calculate
     this value from the Max-Age attribute)
    discard: boolean, true if this is a session cookie; (if no expires value,
     this should be true)
    comment: string;
    comment_url: string;
    rfc2109: boolean; true if cookie arrived in a Set-Cookie: (not
     Set-Cookie2:) header, but had a version cookie-attribute of 1
    rest: mapping of other cookie-attributes

    Note that the port may be present in the headers, but unspecified ("Port"
    rather than"Port=80", for example); if this is the case, port is None.

    """

    def __init__(self, version, name, value,
                 port, port_specified,
                 domain, domain_specified, domain_initial_dot,
                 path, path_specified,
                 secure,
                 expires,
                 discard,
                 comment,
                 comment_url,
                 rest,
                 rfc2109=False,
                 ):

        if version is not None: version = int(version)
        if expires is not None: expires = int(expires)
        if port is None and port_specified is True:
            raise ValueError("if port is None, port_specified must be false")

        self.version = version
        self.name = name
        self.value = value
        self.port = port
        self.port_specified = port_specified
        # normalise case, as per RFC 2965 section 3.3.3
        self.domain = domain.lower()
        self.domain_specified = domain_specified
        # Sigh.  We need to know whether the domain given in the
        # cookie-attribute had an initial dot, in order to follow RFC 2965
        # (as clarified in draft errata).  Needed for the returned $Domain
        # value.
        self.domain_initial_dot = domain_initial_dot
        self.path = path
        self.path_specified = path_specified
        self.secure = secure
        self.expires = expires
        self.discard = discard
        self.comment = comment
        self.comment_url = comment_url
        self.rfc2109 = rfc2109

        self._rest = copy.copy(rest)

    def has_nonstandard_attr(self, name):
        return self._rest.has_key(name)
    def get_nonstandard_attr(self, name, default=None):
        return self._rest.get(name, default)
    def set_nonstandard_attr(self, name, value):
        self._rest[name] = value
    def nonstandard_attr_keys(self):
        return self._rest.keys()

    def is_expired(self, now=None):
        if now is None: now = time.time()
        return (self.expires is not None) and (self.expires <= now)

    def __str__(self):
        if self.port is None: p = ""
        else: p = ":"+self.port
        limit = self.domain + p + self.path
        if self.value is not None:
            namevalue = "%s=%s" % (self.name, self.value)
        else:
            namevalue = self.name
        return "<Cookie %s for %s>" % (namevalue, limit)

    def __repr__(self):
        args = []
        for name in ["version", "name", "value",
                     "port", "port_specified",
                     "domain", "domain_specified", "domain_initial_dot",
                     "path", "path_specified",
                     "secure", "expires", "discard", "comment", "comment_url",
                     ]:
            attr = getattr(self, name)
            args.append("%s=%s" % (name, repr(attr)))
        args.append("rest=%s" % repr(self._rest))
        args.append("rfc2109=%s" % repr(self.rfc2109))
        return "Cookie(%s)" % ", ".join(args)


class CookiePolicy:
    """Defines which cookies get accepted from and returned to server.

    May also modify cookies.

    The subclass DefaultCookiePolicy defines the standard rules for Netscape
    and RFC 2965 cookies -- override that if you want a customised policy.

    As well as implementing set_ok and return_ok, implementations of this
    interface must also supply the following attributes, indicating which
    protocols should be used, and how.  These can be read and set at any time,
    though whether that makes complete sense from the protocol point of view is
    doubtful.

    Public attributes:

    netscape: implement netscape protocol
    rfc2965: implement RFC 2965 protocol
    rfc2109_as_netscape:
       WARNING: This argument will change or go away if is not accepted into
                the Python standard library in this form!
     If true, treat RFC 2109 cookies as though they were Netscape cookies.  The
     default is for this attribute to be None, which means treat 2109 cookies
     as RFC 2965 cookies unless RFC 2965 handling is switched off (which it is,
     by default), and as Netscape cookies otherwise.
    hide_cookie2: don't add Cookie2 header to requests (the presence of
     this header indicates to the server that we understand RFC 2965
     cookies)

    """
    def set_ok(self, cookie, request):
        """Return true if (and only if) cookie should be accepted from server.

        Currently, pre-expired cookies never get this far -- the CookieJar
        class deletes such cookies itself.

        cookie: mechanize.Cookie object
        request: object implementing the interface defined by
         CookieJar.extract_cookies.__doc__

        """
        raise NotImplementedError()

    def return_ok(self, cookie, request):
        """Return true if (and only if) cookie should be returned to server.

        cookie: mechanize.Cookie object
        request: object implementing the interface defined by
         CookieJar.add_cookie_header.__doc__

        """
        raise NotImplementedError()

    def domain_return_ok(self, domain, request):
        """Return false if cookies should not be returned, given cookie domain.

        This is here as an optimization, to remove the need for checking every
        cookie with a particular domain (which may involve reading many files).
        The default implementations of domain_return_ok and path_return_ok
        (return True) leave all the work to return_ok.

        If domain_return_ok returns true for the cookie domain, path_return_ok
        is called for the cookie path.  Otherwise, path_return_ok and return_ok
        are never called for that cookie domain.  If path_return_ok returns
        true, return_ok is called with the Cookie object itself for a full
        check.  Otherwise, return_ok is never called for that cookie path.

        Note that domain_return_ok is called for every *cookie* domain, not
        just for the *request* domain.  For example, the function might be
        called with both ".acme.com" and "www.acme.com" if the request domain is
        "www.acme.com".  The same goes for path_return_ok.

        For argument documentation, see the docstring for return_ok.

        """
        return True

    def path_return_ok(self, path, request):
        """Return false if cookies should not be returned, given cookie path.

        See the docstring for domain_return_ok.

        """
        return True


class DefaultCookiePolicy(CookiePolicy):
    """Implements the standard rules for accepting and returning cookies.

    Both RFC 2965 and Netscape cookies are covered.  RFC 2965 handling is
    switched off by default.

    The easiest way to provide your own policy is to override this class and
    call its methods in your overriden implementations before adding your own
    additional checks.

    import mechanize
    class MyCookiePolicy(mechanize.DefaultCookiePolicy):
        def set_ok(self, cookie, request):
            if not mechanize.DefaultCookiePolicy.set_ok(
                self, cookie, request):
                return False
            if i_dont_want_to_store_this_cookie():
                return False
            return True

    In addition to the features required to implement the CookiePolicy
    interface, this class allows you to block and allow domains from setting
    and receiving cookies.  There are also some strictness switches that allow
    you to tighten up the rather loose Netscape protocol rules a little bit (at
    the cost of blocking some benign cookies).

    A domain blacklist and whitelist is provided (both off by default).  Only
    domains not in the blacklist and present in the whitelist (if the whitelist
    is active) participate in cookie setting and returning.  Use the
    blocked_domains constructor argument, and blocked_domains and
    set_blocked_domains methods (and the corresponding argument and methods for
    allowed_domains).  If you set a whitelist, you can turn it off again by
    setting it to None.

    Domains in block or allow lists that do not start with a dot must
    string-compare equal.  For example, "acme.com" matches a blacklist entry of
    "acme.com", but "www.acme.com" does not.  Domains that do start with a dot
    are matched by more specific domains too.  For example, both "www.acme.com"
    and "www.munitions.acme.com" match ".acme.com" (but "acme.com" itself does
    not).  IP addresses are an exception, and must match exactly.  For example,
    if blocked_domains contains "192.168.1.2" and ".168.1.2" 192.168.1.2 is
    blocked, but 193.168.1.2 is not.

    Additional Public Attributes:

    General strictness switches

    strict_domain: don't allow sites to set two-component domains with
     country-code top-level domains like .co.uk, .gov.uk, .co.nz. etc.
     This is far from perfect and isn't guaranteed to work!

    RFC 2965 protocol strictness switches

    strict_rfc2965_unverifiable: follow RFC 2965 rules on unverifiable
     transactions (usually, an unverifiable transaction is one resulting from
     a redirect or an image hosted on another site); if this is false, cookies
     are NEVER blocked on the basis of verifiability

    Netscape protocol strictness switches

    strict_ns_unverifiable: apply RFC 2965 rules on unverifiable transactions
     even to Netscape cookies
    strict_ns_domain: flags indicating how strict to be with domain-matching
     rules for Netscape cookies:
      DomainStrictNoDots: when setting cookies, host prefix must not contain a
       dot (eg. www.foo.bar.com can't set a cookie for .bar.com, because
       www.foo contains a dot)
      DomainStrictNonDomain: cookies that did not explicitly specify a Domain
       cookie-attribute can only be returned to a domain that string-compares
       equal to the domain that set the cookie (eg. rockets.acme.com won't
       be returned cookies from acme.com that had no Domain cookie-attribute)
      DomainRFC2965Match: when setting cookies, require a full RFC 2965
       domain-match
      DomainLiberal and DomainStrict are the most useful combinations of the
       above flags, for convenience
    strict_ns_set_initial_dollar: ignore cookies in Set-Cookie: headers that
     have names starting with '$'
    strict_ns_set_path: don't allow setting cookies whose path doesn't
     path-match request URI

    """

    DomainStrictNoDots = 1
    DomainStrictNonDomain = 2
    DomainRFC2965Match = 4

    DomainLiberal = 0
    DomainStrict = DomainStrictNoDots|DomainStrictNonDomain

    def __init__(self,
                 blocked_domains=None, allowed_domains=None,
                 netscape=True, rfc2965=False,
                 # WARNING: this argument will change or go away if is not
                 # accepted into the Python standard library in this form!
                 # default, ie. treat 2109 as netscape iff not rfc2965
                 rfc2109_as_netscape=None,
                 hide_cookie2=False,
                 strict_domain=False,
                 strict_rfc2965_unverifiable=True,
                 strict_ns_unverifiable=False,
                 strict_ns_domain=DomainLiberal,
                 strict_ns_set_initial_dollar=False,
                 strict_ns_set_path=False,
                 ):
        """
        Constructor arguments should be used as keyword arguments only.

        blocked_domains: sequence of domain names that we never accept cookies
         from, nor return cookies to
        allowed_domains: if not None, this is a sequence of the only domains
         for which we accept and return cookies

        For other arguments, see CookiePolicy.__doc__ and
        DefaultCookiePolicy.__doc__..

        """
        self.netscape = netscape
        self.rfc2965 = rfc2965
        self.rfc2109_as_netscape = rfc2109_as_netscape
        self.hide_cookie2 = hide_cookie2
        self.strict_domain = strict_domain
        self.strict_rfc2965_unverifiable = strict_rfc2965_unverifiable
        self.strict_ns_unverifiable = strict_ns_unverifiable
        self.strict_ns_domain = strict_ns_domain
        self.strict_ns_set_initial_dollar = strict_ns_set_initial_dollar
        self.strict_ns_set_path = strict_ns_set_path

        if blocked_domains is not None:
            self._blocked_domains = tuple(blocked_domains)
        else:
            self._blocked_domains = ()

        if allowed_domains is not None:
            allowed_domains = tuple(allowed_domains)
        self._allowed_domains = allowed_domains

    def blocked_domains(self):
        """Return the sequence of blocked domains (as a tuple)."""
        return self._blocked_domains
    def set_blocked_domains(self, blocked_domains):
        """Set the sequence of blocked domains."""
        self._blocked_domains = tuple(blocked_domains)

    def is_blocked(self, domain):
        for blocked_domain in self._blocked_domains:
            if user_domain_match(domain, blocked_domain):
                return True
        return False

    def allowed_domains(self):
        """Return None, or the sequence of allowed domains (as a tuple)."""
        return self._allowed_domains
    def set_allowed_domains(self, allowed_domains):
        """Set the sequence of allowed domains, or None."""
        if allowed_domains is not None:
            allowed_domains = tuple(allowed_domains)
        self._allowed_domains = allowed_domains

    def is_not_allowed(self, domain):
        if self._allowed_domains is None:
            return False
        for allowed_domain in self._allowed_domains:
            if user_domain_match(domain, allowed_domain):
                return False
        return True

    def set_ok(self, cookie, request):
        """
        If you override set_ok, be sure to call this method.  If it returns
        false, so should your subclass (assuming your subclass wants to be more
        strict about which cookies to accept).

        """
        debug(" - checking cookie %s", cookie)

        assert cookie.name is not None

        for n in "version", "verifiability", "name", "path", "domain", "port":
            fn_name = "set_ok_"+n
            fn = getattr(self, fn_name)
            if not fn(cookie, request):
                return False

        return True

    def set_ok_version(self, cookie, request):
        if cookie.version is None:
            # Version is always set to 0 by parse_ns_headers if it's a Netscape
            # cookie, so this must be an invalid RFC 2965 cookie.
            debug("   Set-Cookie2 without version attribute (%s)", cookie)
            return False
        if cookie.version > 0 and not self.rfc2965:
            debug("   RFC 2965 cookies are switched off")
            return False
        elif cookie.version == 0 and not self.netscape:
            debug("   Netscape cookies are switched off")
            return False
        return True

    def set_ok_verifiability(self, cookie, request):
        if request.unverifiable and is_third_party(request):
            if cookie.version > 0 and self.strict_rfc2965_unverifiable:
                debug("   third-party RFC 2965 cookie during "
                             "unverifiable transaction")
                return False
            elif cookie.version == 0 and self.strict_ns_unverifiable:
                debug("   third-party Netscape cookie during "
                             "unverifiable transaction")
                return False
        return True

    def set_ok_name(self, cookie, request):
        # Try and stop servers setting V0 cookies designed to hack other
        # servers that know both V0 and V1 protocols.
        if (cookie.version == 0 and self.strict_ns_set_initial_dollar and
            cookie.name.startswith("$")):
            debug("   illegal name (starts with '$'): '%s'", cookie.name)
            return False
        return True

    def set_ok_path(self, cookie, request):
        if cookie.path_specified:
            req_path = request_path(request)
            if ((cookie.version > 0 or
                 (cookie.version == 0 and self.strict_ns_set_path)) and
                not req_path.startswith(cookie.path)):
                debug("   path attribute %s is not a prefix of request "
                      "path %s", cookie.path, req_path)
                return False
        return True

    def set_ok_countrycode_domain(self, cookie, request):
        """Return False if explicit cookie domain is not acceptable.

        Called by set_ok_domain, for convenience of overriding by
        subclasses.

        """
        if cookie.domain_specified and self.strict_domain:
            domain = cookie.domain
            # since domain was specified, we know that:
            assert domain.startswith(".")
            if domain.count(".") == 2:
                # domain like .foo.bar
                i = domain.rfind(".")
                tld = domain[i+1:]
                sld = domain[1:i]
                if (sld.lower() in [
                    "co", "ac",
                    "com", "edu", "org", "net", "gov", "mil", "int",
                    "aero", "biz", "cat", "coop", "info", "jobs", "mobi",
                    "museum", "name", "pro", "travel",
                    ] and
                    len(tld) == 2):
                    # domain like .co.uk
                    return False
        return True

    def set_ok_domain(self, cookie, request):
        if self.is_blocked(cookie.domain):
            debug("   domain %s is in user block-list", cookie.domain)
            return False
        if self.is_not_allowed(cookie.domain):
            debug("   domain %s is not in user allow-list", cookie.domain)
            return False
        if not self.set_ok_countrycode_domain(cookie, request):
            debug("   country-code second level domain %s", cookie.domain)
            return False
        if cookie.domain_specified:
            req_host, erhn = eff_request_host(request)
            domain = cookie.domain
            if domain.startswith("."):
                undotted_domain = domain[1:]
            else:
                undotted_domain = domain
            embedded_dots = (undotted_domain.find(".") >= 0)
            if not embedded_dots and domain != ".local":
                debug("   non-local domain %s contains no embedded dot",
                      domain)
                return False
            if cookie.version == 0:
                if (not erhn.endswith(domain) and
                    (not erhn.startswith(".") and
                     not ("."+erhn).endswith(domain))):
                    debug("   effective request-host %s (even with added "
                          "initial dot) does not end end with %s",
                          erhn, domain)
                    return False
            if (cookie.version > 0 or
                (self.strict_ns_domain & self.DomainRFC2965Match)):
                if not domain_match(erhn, domain):
                    debug("   effective request-host %s does not domain-match "
                          "%s", erhn, domain)
                    return False
            if (cookie.version > 0 or
                (self.strict_ns_domain & self.DomainStrictNoDots)):
                host_prefix = req_host[:-len(domain)]
                if (host_prefix.find(".") >= 0 and
                    not IPV4_RE.search(req_host)):
                    debug("   host prefix %s for domain %s contains a dot",
                          host_prefix, domain)
                    return False
        return True

    def set_ok_port(self, cookie, request):
        if cookie.port_specified:
            req_port = request_port(request)
            if req_port is None:
                req_port = "80"
            else:
                req_port = str(req_port)
            for p in cookie.port.split(","):
                try:
                    int(p)
                except ValueError:
                    debug("   bad port %s (not numeric)", p)
                    return False
                if p == req_port:
                    break
            else:
                debug("   request port (%s) not found in %s",
                      req_port, cookie.port)
                return False
        return True

    def return_ok(self, cookie, request):
        """
        If you override return_ok, be sure to call this method.  If it returns
        false, so should your subclass (assuming your subclass wants to be more
        strict about which cookies to return).

        """
        # Path has already been checked by path_return_ok, and domain blocking
        # done by domain_return_ok.
        debug(" - checking cookie %s", cookie)

        for n in "version", "verifiability", "secure", "expires", "port", "domain":
            fn_name = "return_ok_"+n
            fn = getattr(self, fn_name)
            if not fn(cookie, request):
                return False
        return True

    def return_ok_version(self, cookie, request):
        if cookie.version > 0 and not self.rfc2965:
            debug("   RFC 2965 cookies are switched off")
            return False
        elif cookie.version == 0 and not self.netscape:
            debug("   Netscape cookies are switched off")
            return False
        return True

    def return_ok_verifiability(self, cookie, request):
        if request.unverifiable and is_third_party(request):
            if cookie.version > 0 and self.strict_rfc2965_unverifiable:
                debug("   third-party RFC 2965 cookie during unverifiable "
                      "transaction")
                return False
            elif cookie.version == 0 and self.strict_ns_unverifiable:
                debug("   third-party Netscape cookie during unverifiable "
                      "transaction")
                return False
        return True

    def return_ok_secure(self, cookie, request):
        if cookie.secure and request.get_type() != "https":
            debug("   secure cookie with non-secure request")
            return False
        return True

    def return_ok_expires(self, cookie, request):
        if cookie.is_expired(self._now):
            debug("   cookie expired")
            return False
        return True

    def return_ok_port(self, cookie, request):
        if cookie.port:
            req_port = request_port(request)
            if req_port is None:
                req_port = "80"
            for p in cookie.port.split(","):
                if p == req_port:
                    break
            else:
                debug("   request port %s does not match cookie port %s",
                      req_port, cookie.port)
                return False
        return True

    def return_ok_domain(self, cookie, request):
        req_host, erhn = eff_request_host(request)
        domain = cookie.domain

        # strict check of non-domain cookies: Mozilla does this, MSIE5 doesn't
        if (cookie.version == 0 and
            (self.strict_ns_domain & self.DomainStrictNonDomain) and
            not cookie.domain_specified and domain != erhn):
            debug("   cookie with unspecified domain does not string-compare "
                  "equal to request domain")
            return False

        if cookie.version > 0 and not domain_match(erhn, domain):
            debug("   effective request-host name %s does not domain-match "
                  "RFC 2965 cookie domain %s", erhn, domain)
            return False
        if cookie.version == 0 and not ("."+erhn).endswith(domain):
            debug("   request-host %s does not match Netscape cookie domain "
                  "%s", req_host, domain)
            return False
        return True

    def domain_return_ok(self, domain, request):
        # Liberal check of domain.  This is here as an optimization to avoid
        # having to load lots of MSIE cookie files unless necessary.

        # Munge req_host and erhn to always start with a dot, so as to err on
        # the side of letting cookies through.
        dotted_req_host, dotted_erhn = eff_request_host(request)
        if not dotted_req_host.startswith("."):
            dotted_req_host = "."+dotted_req_host
        if not dotted_erhn.startswith("."):
            dotted_erhn = "."+dotted_erhn
        if not (dotted_req_host.endswith(domain) or
                dotted_erhn.endswith(domain)):
            #debug("   request domain %s does not match cookie domain %s",
            #      req_host, domain)
            return False

        if self.is_blocked(domain):
            debug("   domain %s is in user block-list", domain)
            return False
        if self.is_not_allowed(domain):
            debug("   domain %s is not in user allow-list", domain)
            return False

        return True

    def path_return_ok(self, path, request):
        debug("- checking cookie path=%s", path)
        req_path = request_path(request)
        if not req_path.startswith(path):
            debug("  %s does not path-match %s", req_path, path)
            return False
        return True


def vals_sorted_by_key(adict):
    keys = adict.keys()
    keys.sort()
    return map(adict.get, keys)

class MappingIterator:
    """Iterates over nested mapping, depth-first, in sorted order by key."""
    def __init__(self, mapping):
        self._s = [(vals_sorted_by_key(mapping), 0, None)]  # LIFO stack

    def __iter__(self): return self

    def next(self):
        # this is hairy because of lack of generators
        while 1:
            try:
                vals, i, prev_item = self._s.pop()
            except IndexError:
                raise StopIteration()
            if i < len(vals):
                item = vals[i]
                i = i + 1
                self._s.append((vals, i, prev_item))
                try:
                    item.items
                except AttributeError:
                    # non-mapping
                    break
                else:
                    # mapping
                    self._s.append((vals_sorted_by_key(item), 0, item))
                    continue
        return item


# Used as second parameter to dict.get method, to distinguish absent
# dict key from one with a None value.
class Absent: pass

class CookieJar:
    """Collection of HTTP cookies.

    You may not need to know about this class: try mechanize.urlopen().

    The major methods are extract_cookies and add_cookie_header; these are all
    you are likely to need.

    CookieJar supports the iterator protocol:

    for cookie in cookiejar:
        # do something with cookie

    Methods:

    add_cookie_header(request)
    extract_cookies(response, request)
    make_cookies(response, request)
    set_cookie_if_ok(cookie, request)
    set_cookie(cookie)
    clear_session_cookies()
    clear_expired_cookies()
    clear(domain=None, path=None, name=None)

    Public attributes

    policy: CookiePolicy object

    """

    non_word_re = re.compile(r"\W")
    quote_re = re.compile(r"([\"\\])")
    strict_domain_re = re.compile(r"\.?[^.]*")
    domain_re = re.compile(r"[^.]*")
    dots_re = re.compile(r"^\.+")

    def __init__(self, policy=None):
        """
        See CookieJar.__doc__ for argument documentation.

        """
        if policy is None:
            policy = DefaultCookiePolicy()
        self._policy = policy

        self._cookies = {}

        # for __getitem__ iteration in pre-2.2 Pythons
        self._prev_getitem_index = 0

    def set_policy(self, policy):
        self._policy = policy

    def _cookies_for_domain(self, domain, request):
        cookies = []
        if not self._policy.domain_return_ok(domain, request):
            return []
        debug("Checking %s for cookies to return", domain)
        cookies_by_path = self._cookies[domain]
        for path in cookies_by_path.keys():
            if not self._policy.path_return_ok(path, request):
                continue
            cookies_by_name = cookies_by_path[path]
            for cookie in cookies_by_name.values():
                if not self._policy.return_ok(cookie, request):
                    debug("   not returning cookie")
                    continue
                debug("   it's a match")
                cookies.append(cookie)
        return cookies

    def _cookies_for_request(self, request):
        """Return a list of cookies to be returned to server."""
        cookies = []
        for domain in self._cookies.keys():
            cookies.extend(self._cookies_for_domain(domain, request))
        return cookies

    def _cookie_attrs(self, cookies):
        """Return a list of cookie-attributes to be returned to server.

        like ['foo="bar"; $Path="/"', ...]

        The $Version attribute is also added when appropriate (currently only
        once per request).

        """
        # add cookies in order of most specific (ie. longest) path first
        def decreasing_size(a, b): return cmp(len(b.path), len(a.path))
        cookies.sort(decreasing_size)

        version_set = False

        attrs = []
        for cookie in cookies:
            # set version of Cookie header
            # XXX
            # What should it be if multiple matching Set-Cookie headers have
            #  different versions themselves?
            # Answer: there is no answer; was supposed to be settled by
            #  RFC 2965 errata, but that may never appear...
            version = cookie.version
            if not version_set:
                version_set = True
                if version > 0:
                    attrs.append("$Version=%s" % version)

            # quote cookie value if necessary
            # (not for Netscape protocol, which already has any quotes
            #  intact, due to the poorly-specified Netscape Cookie: syntax)
            if ((cookie.value is not None) and
                self.non_word_re.search(cookie.value) and version > 0):
                value = self.quote_re.sub(r"\\\1", cookie.value)
            else:
                value = cookie.value

            # add cookie-attributes to be returned in Cookie header
            if cookie.value is None:
                attrs.append(cookie.name)
            else:
                attrs.append("%s=%s" % (cookie.name, value))
            if version > 0:
                if cookie.path_specified:
                    attrs.append('$Path="%s"' % cookie.path)
                if cookie.domain.startswith("."):
                    domain = cookie.domain
                    if (not cookie.domain_initial_dot and
                        domain.startswith(".")):
                        domain = domain[1:]
                    attrs.append('$Domain="%s"' % domain)
                if cookie.port is not None:
                    p = "$Port"
                    if cookie.port_specified:
                        p = p + ('="%s"' % cookie.port)
                    attrs.append(p)

        return attrs

    def add_cookie_header(self, request):
        """Add correct Cookie: header to request (urllib2.Request object).

        The Cookie2 header is also added unless policy.hide_cookie2 is true.

        The request object (usually a urllib2.Request instance) must support
        the methods get_full_url, get_host, get_type, has_header, get_header,
        header_items and add_unredirected_header, as documented by urllib2, and
        the port attribute (the port number).  Actually,
        RequestUpgradeProcessor will automatically upgrade your Request object
        to one with has_header, get_header, header_items and
        add_unredirected_header, if it lacks those methods, for compatibility
        with pre-2.4 versions of urllib2.

        """
        debug("add_cookie_header")
        self._policy._now = self._now = int(time.time())

        req_host, erhn = eff_request_host(request)
        strict_non_domain = (
            self._policy.strict_ns_domain & self._policy.DomainStrictNonDomain)

        cookies = self._cookies_for_request(request)

        attrs = self._cookie_attrs(cookies)
        if attrs:
            if not request.has_header("Cookie"):
                request.add_unredirected_header("Cookie", "; ".join(attrs))

        # if necessary, advertise that we know RFC 2965
        if self._policy.rfc2965 and not self._policy.hide_cookie2:
            for cookie in cookies:
                if cookie.version != 1 and not request.has_header("Cookie2"):
                    request.add_unredirected_header("Cookie2", '$Version="1"')
                    break

        self.clear_expired_cookies()

    def _normalized_cookie_tuples(self, attrs_set):
        """Return list of tuples containing normalised cookie information.

        attrs_set is the list of lists of key,value pairs extracted from
        the Set-Cookie or Set-Cookie2 headers.

        Tuples are name, value, standard, rest, where name and value are the
        cookie name and value, standard is a dictionary containing the standard
        cookie-attributes (discard, secure, version, expires or max-age,
        domain, path and port) and rest is a dictionary containing the rest of
        the cookie-attributes.

        """
        cookie_tuples = []

        boolean_attrs = "discard", "secure"
        value_attrs = ("version",
                       "expires", "max-age",
                       "domain", "path", "port",
                       "comment", "commenturl")

        for cookie_attrs in attrs_set:
            name, value = cookie_attrs[0]

            # Build dictionary of standard cookie-attributes (standard) and
            # dictionary of other cookie-attributes (rest).

            # Note: expiry time is normalised to seconds since epoch.  V0
            # cookies should have the Expires cookie-attribute, and V1 cookies
            # should have Max-Age, but since V1 includes RFC 2109 cookies (and
            # since V0 cookies may be a mish-mash of Netscape and RFC 2109), we
            # accept either (but prefer Max-Age).
            max_age_set = False

            bad_cookie = False

            standard = {}
            rest = {}
            for k, v in cookie_attrs[1:]:
                lc = k.lower()
                # don't lose case distinction for unknown fields
                if lc in value_attrs or lc in boolean_attrs:
                    k = lc
                if k in boolean_attrs and v is None:
                    # boolean cookie-attribute is present, but has no value
                    # (like "discard", rather than "port=80")
                    v = True
                if standard.has_key(k):
                    # only first value is significant
                    continue
                if k == "domain":
                    if v is None:
                        debug("   missing value for domain attribute")
                        bad_cookie = True
                        break
                    # RFC 2965 section 3.3.3
                    v = v.lower()
                if k == "expires":
                    if max_age_set:
                        # Prefer max-age to expires (like Mozilla)
                        continue
                    if v is None:
                        debug("   missing or invalid value for expires "
                              "attribute: treating as session cookie")
                        continue
                if k == "max-age":
                    max_age_set = True
                    try:
                        v = int(v)
                    except ValueError:
                        debug("   missing or invalid (non-numeric) value for "
                              "max-age attribute")
                        bad_cookie = True
                        break
                    # convert RFC 2965 Max-Age to seconds since epoch
                    # XXX Strictly you're supposed to follow RFC 2616
                    #   age-calculation rules.  Remember that zero Max-Age is a
                    #   is a request to discard (old and new) cookie, though.
                    k = "expires"
                    v = self._now + v
                if (k in value_attrs) or (k in boolean_attrs):
                    if (v is None and
                        k not in ["port", "comment", "commenturl"]):
                        debug("   missing value for %s attribute" % k)
                        bad_cookie = True
                        break
                    standard[k] = v
                else:
                    rest[k] = v

            if bad_cookie:
                continue

            cookie_tuples.append((name, value, standard, rest))

        return cookie_tuples

    def _cookie_from_cookie_tuple(self, tup, request):
        # standard is dict of standard cookie-attributes, rest is dict of the
        # rest of them
        name, value, standard, rest = tup

        domain = standard.get("domain", Absent)
        path = standard.get("path", Absent)
        port = standard.get("port", Absent)
        expires = standard.get("expires", Absent)

        # set the easy defaults
        version = standard.get("version", None)
        if version is not None: version = int(version)
        secure = standard.get("secure", False)
        # (discard is also set if expires is Absent)
        discard = standard.get("discard", False)
        comment = standard.get("comment", None)
        comment_url = standard.get("commenturl", None)

        # set default path
        if path is not Absent and path != "":
            path_specified = True
            path = escape_path(path)
        else:
            path_specified = False
            path = request_path(request)
            i = path.rfind("/")
            if i != -1:
                if version == 0:
                    # Netscape spec parts company from reality here
                    path = path[:i]
                else:
                    path = path[:i+1]
            if len(path) == 0: path = "/"

        # set default domain
        domain_specified = domain is not Absent
        # but first we have to remember whether it starts with a dot
        domain_initial_dot = False
        if domain_specified:
            domain_initial_dot = bool(domain.startswith("."))
        if domain is Absent:
            req_host, erhn = eff_request_host(request)
            domain = erhn
        elif not domain.startswith("."):
            domain = "."+domain

        # set default port
        port_specified = False
        if port is not Absent:
            if port is None:
                # Port attr present, but has no value: default to request port.
                # Cookie should then only be sent back on that port.
                port = request_port(request)
            else:
                port_specified = True
                port = re.sub(r"\s+", "", port)
        else:
            # No port attr present.  Cookie can be sent back on any port.
            port = None

        # set default expires and discard
        if expires is Absent:
            expires = None
            discard = True
        elif expires <= self._now:
            # Expiry date in past is request to delete cookie.  This can't be
            # in DefaultCookiePolicy, because can't delete cookies there.
            try:
                self.clear(domain, path, name)
            except KeyError:
                pass
            debug("Expiring cookie, domain='%s', path='%s', name='%s'",
                  domain, path, name)
            return None

        return Cookie(version,
                      name, value,
                      port, port_specified,
                      domain, domain_specified, domain_initial_dot,
                      path, path_specified,
                      secure,
                      expires,
                      discard,
                      comment,
                      comment_url,
                      rest)

    def _cookies_from_attrs_set(self, attrs_set, request):
        cookie_tuples = self._normalized_cookie_tuples(attrs_set)

        cookies = []
        for tup in cookie_tuples:
            cookie = self._cookie_from_cookie_tuple(tup, request)
            if cookie: cookies.append(cookie)
        return cookies

    def _process_rfc2109_cookies(self, cookies):
        if self._policy.rfc2109_as_netscape is None:
            rfc2109_as_netscape = not self._policy.rfc2965
        else:
            rfc2109_as_netscape = self._policy.rfc2109_as_netscape
        for cookie in cookies:
            if cookie.version == 1:
                cookie.rfc2109 = True
                if rfc2109_as_netscape: 
                    # treat 2109 cookies as Netscape cookies rather than
                    # as RFC2965 cookies
                    cookie.version = 0

    def make_cookies(self, response, request):
        """Return sequence of Cookie objects extracted from response object.

        See extract_cookies.__doc__ for the interfaces required of the
        response and request arguments.

        """
        # get cookie-attributes for RFC 2965 and Netscape protocols
        headers = response.info()
        rfc2965_hdrs = headers.getheaders("Set-Cookie2")
        ns_hdrs = headers.getheaders("Set-Cookie")

        rfc2965 = self._policy.rfc2965
        netscape = self._policy.netscape

        if ((not rfc2965_hdrs and not ns_hdrs) or
            (not ns_hdrs and not rfc2965) or
            (not rfc2965_hdrs and not netscape) or
            (not netscape and not rfc2965)):
            return []  # no relevant cookie headers: quick exit

        try:
            cookies = self._cookies_from_attrs_set(
                split_header_words(rfc2965_hdrs), request)
        except:
            reraise_unmasked_exceptions()
            cookies = []

        if ns_hdrs and netscape:
            try:
                # RFC 2109 and Netscape cookies
                ns_cookies = self._cookies_from_attrs_set(
                    parse_ns_headers(ns_hdrs), request)
            except:
                reraise_unmasked_exceptions()
                ns_cookies = []
            self._process_rfc2109_cookies(ns_cookies)

            # Look for Netscape cookies (from Set-Cookie headers) that match
            # corresponding RFC 2965 cookies (from Set-Cookie2 headers).
            # For each match, keep the RFC 2965 cookie and ignore the Netscape
            # cookie (RFC 2965 section 9.1).  Actually, RFC 2109 cookies are
            # bundled in with the Netscape cookies for this purpose, which is
            # reasonable behaviour.
            if rfc2965:
                lookup = {}
                for cookie in cookies:
                    lookup[(cookie.domain, cookie.path, cookie.name)] = None

                def no_matching_rfc2965(ns_cookie, lookup=lookup):
                    key = ns_cookie.domain, ns_cookie.path, ns_cookie.name
                    return not lookup.has_key(key)
                ns_cookies = filter(no_matching_rfc2965, ns_cookies)

            if ns_cookies:
                cookies.extend(ns_cookies)

        return cookies

    def set_cookie_if_ok(self, cookie, request):
        """Set a cookie if policy says it's OK to do so.

        cookie: mechanize.Cookie instance
        request: see extract_cookies.__doc__ for the required interface

        """
        self._policy._now = self._now = int(time.time())

        if self._policy.set_ok(cookie, request):
            self.set_cookie(cookie)

    def set_cookie(self, cookie):
        """Set a cookie, without checking whether or not it should be set.

        cookie: mechanize.Cookie instance
        """
        c = self._cookies
        if not c.has_key(cookie.domain): c[cookie.domain] = {}
        c2 = c[cookie.domain]
        if not c2.has_key(cookie.path): c2[cookie.path] = {}
        c3 = c2[cookie.path]
        c3[cookie.name] = cookie

    def extract_cookies(self, response, request):
        """Extract cookies from response, where allowable given the request.

        Look for allowable Set-Cookie: and Set-Cookie2: headers in the response
        object passed as argument.  Any of these headers that are found are
        used to update the state of the object (subject to the policy.set_ok
        method's approval).

        The response object (usually be the result of a call to
        mechanize.urlopen, or similar) should support an info method, which
        returns a mimetools.Message object (in fact, the 'mimetools.Message
        object' may be any object that provides a getallmatchingheaders
        method).

        The request object (usually a urllib2.Request instance) must support
        the methods get_full_url and get_host, as documented by urllib2, and
        the port attribute (the port number).  The request is used to set
        default values for cookie-attributes as well as for checking that the
        cookie is OK to be set.

        """
        debug("extract_cookies: %s", response.info())
        self._policy._now = self._now = int(time.time())

        for cookie in self.make_cookies(response, request):
            if self._policy.set_ok(cookie, request):
                debug(" setting cookie: %s", cookie)
                self.set_cookie(cookie)

    def clear(self, domain=None, path=None, name=None):
        """Clear some cookies.

        Invoking this method without arguments will clear all cookies.  If
        given a single argument, only cookies belonging to that domain will be
        removed.  If given two arguments, cookies belonging to the specified
        path within that domain are removed.  If given three arguments, then
        the cookie with the specified name, path and domain is removed.

        Raises KeyError if no matching cookie exists.

        """
        if name is not None:
            if (domain is None) or (path is None):
                raise ValueError(
                    "domain and path must be given to remove a cookie by name")
            del self._cookies[domain][path][name]
        elif path is not None:
            if domain is None:
                raise ValueError(
                    "domain must be given to remove cookies by path")
            del self._cookies[domain][path]
        elif domain is not None:
            del self._cookies[domain]
        else:
            self._cookies = {}

    def clear_session_cookies(self):
        """Discard all session cookies.

        Discards all cookies held by object which had either no Max-Age or
        Expires cookie-attribute or an explicit Discard cookie-attribute, or
        which otherwise have ended up with a true discard attribute.  For
        interactive browsers, the end of a session usually corresponds to
        closing the browser window.

        Note that the save method won't save session cookies anyway, unless you
        ask otherwise by passing a true ignore_discard argument.

        """
        for cookie in self:
            if cookie.discard:
                self.clear(cookie.domain, cookie.path, cookie.name)

    def clear_expired_cookies(self):
        """Discard all expired cookies.

        You probably don't need to call this method: expired cookies are never
        sent back to the server (provided you're using DefaultCookiePolicy),
        this method is called by CookieJar itself every so often, and the save
        method won't save expired cookies anyway (unless you ask otherwise by
        passing a true ignore_expires argument).

        """
        now = time.time()
        for cookie in self:
            if cookie.is_expired(now):
                self.clear(cookie.domain, cookie.path, cookie.name)

    def __getitem__(self, i):
        if i == 0:
            self._getitem_iterator = self.__iter__()
        elif self._prev_getitem_index != i-1: raise IndexError(
            "CookieJar.__getitem__ only supports sequential iteration")
        self._prev_getitem_index = i
        try:
            return self._getitem_iterator.next()
        except StopIteration:
            raise IndexError()

    def __iter__(self):
        return MappingIterator(self._cookies)

    def __len__(self):
        """Return number of contained cookies."""
        i = 0
        for cookie in self: i = i + 1
        return i

    def __repr__(self):
        r = []
        for cookie in self: r.append(repr(cookie))
        return "<%s[%s]>" % (self.__class__, ", ".join(r))

    def __str__(self):
        r = []
        for cookie in self: r.append(str(cookie))
        return "<%s[%s]>" % (self.__class__, ", ".join(r))


class LoadError(Exception): pass

class FileCookieJar(CookieJar):
    """CookieJar that can be loaded from and saved to a file.

    Additional methods

    save(filename=None, ignore_discard=False, ignore_expires=False)
    load(filename=None, ignore_discard=False, ignore_expires=False)
    revert(filename=None, ignore_discard=False, ignore_expires=False)

    Additional public attributes

    filename: filename for loading and saving cookies

    Additional public readable attributes

    delayload: request that cookies are lazily loaded from disk; this is only
     a hint since this only affects performance, not behaviour (unless the
     cookies on disk are changing); a CookieJar object may ignore it (in fact,
     only MSIECookieJar lazily loads cookies at the moment)

    """

    def __init__(self, filename=None, delayload=False, policy=None):
        """
        See FileCookieJar.__doc__ for argument documentation.

        Cookies are NOT loaded from the named file until either the load or
        revert method is called.

        """
        CookieJar.__init__(self, policy)
        if filename is not None and not isstringlike(filename):
            raise ValueError("filename must be string-like")
        self.filename = filename
        self.delayload = bool(delayload)

    def save(self, filename=None, ignore_discard=False, ignore_expires=False):
        """Save cookies to a file.

        filename: name of file in which to save cookies
        ignore_discard: save even cookies set to be discarded
        ignore_expires: save even cookies that have expired

        The file is overwritten if it already exists, thus wiping all its
        cookies.  Saved cookies can be restored later using the load or revert
        methods.  If filename is not specified, self.filename is used; if
        self.filename is None, ValueError is raised.

        """
        raise NotImplementedError()

    def load(self, filename=None, ignore_discard=False, ignore_expires=False):
        """Load cookies from a file.

        Old cookies are kept unless overwritten by newly loaded ones.

        Arguments are as for .save().

        If filename is not specified, self.filename is used; if self.filename
        is None, ValueError is raised.  The named file must be in the format
        understood by the class, or LoadError will be raised.  This format will
        be identical to that written by the save method, unless the load format
        is not sufficiently well understood (as is the case for MSIECookieJar).

        """
        if filename is None:
            if self.filename is not None: filename = self.filename
            else: raise ValueError(MISSING_FILENAME_TEXT)

        f = open(filename)
        try:
            self._really_load(f, filename, ignore_discard, ignore_expires)
        finally:
            f.close()

    def revert(self, filename=None,
               ignore_discard=False, ignore_expires=False):
        """Clear all cookies and reload cookies from a saved file.

        Raises LoadError (or IOError) if reversion is not successful; the
        object's state will not be altered if this happens.

        """
        if filename is None:
            if self.filename is not None: filename = self.filename
            else: raise ValueError(MISSING_FILENAME_TEXT)

        old_state = copy.deepcopy(self._cookies)
        self._cookies = {}
        try:
            self.load(filename, ignore_discard, ignore_expires)
        except (LoadError, IOError):
            self._cookies = old_state
            raise
