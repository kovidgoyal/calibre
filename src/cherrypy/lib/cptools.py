"""Functions for builtin CherryPy tools."""

import logging
import re

import cherrypy
from cherrypy._cpcompat import basestring, ntob, md5, set
from cherrypy.lib import httputil as _httputil


#                     Conditional HTTP request support                     #

def validate_etags(autotags=False, debug=False):
    """Validate the current ETag against If-Match, If-None-Match headers.
    
    If autotags is True, an ETag response-header value will be provided
    from an MD5 hash of the response body (unless some other code has
    already provided an ETag header). If False (the default), the ETag
    will not be automatic.
    
    WARNING: the autotags feature is not designed for URL's which allow
    methods other than GET. For example, if a POST to the same URL returns
    no content, the automatic ETag will be incorrect, breaking a fundamental
    use for entity tags in a possibly destructive fashion. Likewise, if you
    raise 304 Not Modified, the response body will be empty, the ETag hash
    will be incorrect, and your application will break.
    See :rfc:`2616` Section 14.24.
    """
    response = cherrypy.serving.response
    
    # Guard against being run twice.
    if hasattr(response, "ETag"):
        return
    
    status, reason, msg = _httputil.valid_status(response.status)
    
    etag = response.headers.get('ETag')
    
    # Automatic ETag generation. See warning in docstring.
    if etag:
        if debug:
            cherrypy.log('ETag already set: %s' % etag, 'TOOLS.ETAGS')
    elif not autotags:
        if debug:
            cherrypy.log('Autotags off', 'TOOLS.ETAGS')
    elif status != 200:
        if debug:
            cherrypy.log('Status not 200', 'TOOLS.ETAGS')
    else:
        etag = response.collapse_body()
        etag = '"%s"' % md5(etag).hexdigest()
        if debug:
            cherrypy.log('Setting ETag: %s' % etag, 'TOOLS.ETAGS')
        response.headers['ETag'] = etag
    
    response.ETag = etag
    
    # "If the request would, without the If-Match header field, result in
    # anything other than a 2xx or 412 status, then the If-Match header
    # MUST be ignored."
    if debug:
        cherrypy.log('Status: %s' % status, 'TOOLS.ETAGS')
    if status >= 200 and status <= 299:
        request = cherrypy.serving.request
        
        conditions = request.headers.elements('If-Match') or []
        conditions = [str(x) for x in conditions]
        if debug:
            cherrypy.log('If-Match conditions: %s' % repr(conditions),
                         'TOOLS.ETAGS')
        if conditions and not (conditions == ["*"] or etag in conditions):
            raise cherrypy.HTTPError(412, "If-Match failed: ETag %r did "
                                     "not match %r" % (etag, conditions))
        
        conditions = request.headers.elements('If-None-Match') or []
        conditions = [str(x) for x in conditions]
        if debug:
            cherrypy.log('If-None-Match conditions: %s' % repr(conditions),
                         'TOOLS.ETAGS')
        if conditions == ["*"] or etag in conditions:
            if debug:
                cherrypy.log('request.method: %s' % request.method, 'TOOLS.ETAGS')
            if request.method in ("GET", "HEAD"):
                raise cherrypy.HTTPRedirect([], 304)
            else:
                raise cherrypy.HTTPError(412, "If-None-Match failed: ETag %r "
                                         "matched %r" % (etag, conditions))

def validate_since():
    """Validate the current Last-Modified against If-Modified-Since headers.
    
    If no code has set the Last-Modified response header, then no validation
    will be performed.
    """
    response = cherrypy.serving.response
    lastmod = response.headers.get('Last-Modified')
    if lastmod:
        status, reason, msg = _httputil.valid_status(response.status)
        
        request = cherrypy.serving.request
        
        since = request.headers.get('If-Unmodified-Since')
        if since and since != lastmod:
            if (status >= 200 and status <= 299) or status == 412:
                raise cherrypy.HTTPError(412)
        
        since = request.headers.get('If-Modified-Since')
        if since and since == lastmod:
            if (status >= 200 and status <= 299) or status == 304:
                if request.method in ("GET", "HEAD"):
                    raise cherrypy.HTTPRedirect([], 304)
                else:
                    raise cherrypy.HTTPError(412)


#                                Tool code                                #

def allow(methods=None, debug=False):
    """Raise 405 if request.method not in methods (default ['GET', 'HEAD']).
    
    The given methods are case-insensitive, and may be in any order.
    If only one method is allowed, you may supply a single string;
    if more than one, supply a list of strings.
    
    Regardless of whether the current method is allowed or not, this
    also emits an 'Allow' response header, containing the given methods.
    """
    if not isinstance(methods, (tuple, list)):
        methods = [methods]
    methods = [m.upper() for m in methods if m]
    if not methods:
        methods = ['GET', 'HEAD']
    elif 'GET' in methods and 'HEAD' not in methods:
        methods.append('HEAD')
    
    cherrypy.response.headers['Allow'] = ', '.join(methods)
    if cherrypy.request.method not in methods:
        if debug:
            cherrypy.log('request.method %r not in methods %r' %
                         (cherrypy.request.method, methods), 'TOOLS.ALLOW')
        raise cherrypy.HTTPError(405)
    else:
        if debug:
            cherrypy.log('request.method %r in methods %r' %
                         (cherrypy.request.method, methods), 'TOOLS.ALLOW')


def proxy(base=None, local='X-Forwarded-Host', remote='X-Forwarded-For',
          scheme='X-Forwarded-Proto', debug=False):
    """Change the base URL (scheme://host[:port][/path]).
    
    For running a CP server behind Apache, lighttpd, or other HTTP server.
    
    For Apache and lighttpd, you should leave the 'local' argument at the
    default value of 'X-Forwarded-Host'. For Squid, you probably want to set
    tools.proxy.local = 'Origin'.
    
    If you want the new request.base to include path info (not just the host),
    you must explicitly set base to the full base path, and ALSO set 'local'
    to '', so that the X-Forwarded-Host request header (which never includes
    path info) does not override it. Regardless, the value for 'base' MUST
    NOT end in a slash.
    
    cherrypy.request.remote.ip (the IP address of the client) will be
    rewritten if the header specified by the 'remote' arg is valid.
    By default, 'remote' is set to 'X-Forwarded-For'. If you do not
    want to rewrite remote.ip, set the 'remote' arg to an empty string.
    """
    
    request = cherrypy.serving.request
    
    if scheme:
        s = request.headers.get(scheme, None)
        if debug:
            cherrypy.log('Testing scheme %r:%r' % (scheme, s), 'TOOLS.PROXY')
        if s == 'on' and 'ssl' in scheme.lower():
            # This handles e.g. webfaction's 'X-Forwarded-Ssl: on' header
            scheme = 'https'
        else:
            # This is for lighttpd/pound/Mongrel's 'X-Forwarded-Proto: https'
            scheme = s
    if not scheme:
        scheme = request.base[:request.base.find("://")]
    
    if local:
        lbase = request.headers.get(local, None)
        if debug:
            cherrypy.log('Testing local %r:%r' % (local, lbase), 'TOOLS.PROXY')
        if lbase is not None:
            base = lbase.split(',')[0]
    if not base:
        port = request.local.port
        if port == 80:
            base = '127.0.0.1'
        else:
            base = '127.0.0.1:%s' % port
    
    if base.find("://") == -1:
        # add http:// or https:// if needed
        base = scheme + "://" + base
    
    request.base = base
    
    if remote:
        xff = request.headers.get(remote)
        if debug:
            cherrypy.log('Testing remote %r:%r' % (remote, xff), 'TOOLS.PROXY')
        if xff:
            if remote == 'X-Forwarded-For':
                # See http://bob.pythonmac.org/archives/2005/09/23/apache-x-forwarded-for-caveat/
                xff = xff.split(',')[-1].strip()
            request.remote.ip = xff


def ignore_headers(headers=('Range',), debug=False):
    """Delete request headers whose field names are included in 'headers'.
    
    This is a useful tool for working behind certain HTTP servers;
    for example, Apache duplicates the work that CP does for 'Range'
    headers, and will doubly-truncate the response.
    """
    request = cherrypy.serving.request
    for name in headers:
        if name in request.headers:
            if debug:
                cherrypy.log('Ignoring request header %r' % name,
                             'TOOLS.IGNORE_HEADERS')
            del request.headers[name]


def response_headers(headers=None, debug=False):
    """Set headers on the response."""
    if debug:
        cherrypy.log('Setting response headers: %s' % repr(headers),
                     'TOOLS.RESPONSE_HEADERS')
    for name, value in (headers or []):
        cherrypy.serving.response.headers[name] = value
response_headers.failsafe = True


def referer(pattern, accept=True, accept_missing=False, error=403,
            message='Forbidden Referer header.', debug=False):
    """Raise HTTPError if Referer header does/does not match the given pattern.
    
    pattern
        A regular expression pattern to test against the Referer.
        
    accept
        If True, the Referer must match the pattern; if False,
        the Referer must NOT match the pattern.

    accept_missing
        If True, permit requests with no Referer header.

    error
        The HTTP error code to return to the client on failure.
        
    message
        A string to include in the response body on failure.
    
    """
    try:
        ref = cherrypy.serving.request.headers['Referer']
        match = bool(re.match(pattern, ref))
        if debug:
            cherrypy.log('Referer %r matches %r' % (ref, pattern),
                         'TOOLS.REFERER')
        if accept == match:
            return
    except KeyError:
        if debug:
            cherrypy.log('No Referer header', 'TOOLS.REFERER')
        if accept_missing:
            return
    
    raise cherrypy.HTTPError(error, message)


class SessionAuth(object):
    """Assert that the user is logged in."""
    
    session_key = "username"
    debug = False
    
    def check_username_and_password(self, username, password):
        pass
    
    def anonymous(self):
        """Provide a temporary user name for anonymous users."""
        pass
    
    def on_login(self, username):
        pass
    
    def on_logout(self, username):
        pass
    
    def on_check(self, username):
        pass
    
    def login_screen(self, from_page='..', username='', error_msg='', **kwargs):
        return ntob("""<html><body>
Message: %(error_msg)s
<form method="post" action="do_login">
    Login: <input type="text" name="username" value="%(username)s" size="10" /><br />
    Password: <input type="password" name="password" size="10" /><br />
    <input type="hidden" name="from_page" value="%(from_page)s" /><br />
    <input type="submit" />
</form>
</body></html>""" % {'from_page': from_page, 'username': username,
                     'error_msg': error_msg}, "utf-8")
    
    def do_login(self, username, password, from_page='..', **kwargs):
        """Login. May raise redirect, or return True if request handled."""
        response = cherrypy.serving.response
        error_msg = self.check_username_and_password(username, password)
        if error_msg:
            body = self.login_screen(from_page, username, error_msg)
            response.body = body
            if "Content-Length" in response.headers:
                # Delete Content-Length header so finalize() recalcs it.
                del response.headers["Content-Length"]
            return True
        else:
            cherrypy.serving.request.login = username
            cherrypy.session[self.session_key] = username
            self.on_login(username)
            raise cherrypy.HTTPRedirect(from_page or "/")
    
    def do_logout(self, from_page='..', **kwargs):
        """Logout. May raise redirect, or return True if request handled."""
        sess = cherrypy.session
        username = sess.get(self.session_key)
        sess[self.session_key] = None
        if username:
            cherrypy.serving.request.login = None
            self.on_logout(username)
        raise cherrypy.HTTPRedirect(from_page)
    
    def do_check(self):
        """Assert username. May raise redirect, or return True if request handled."""
        sess = cherrypy.session
        request = cherrypy.serving.request
        response = cherrypy.serving.response
        
        username = sess.get(self.session_key)
        if not username:
            sess[self.session_key] = username = self.anonymous()
            if self.debug:
                cherrypy.log('No session[username], trying anonymous', 'TOOLS.SESSAUTH')
        if not username:
            url = cherrypy.url(qs=request.query_string)
            if self.debug:
                cherrypy.log('No username, routing to login_screen with '
                             'from_page %r' % url, 'TOOLS.SESSAUTH')
            response.body = self.login_screen(url)
            if "Content-Length" in response.headers:
                # Delete Content-Length header so finalize() recalcs it.
                del response.headers["Content-Length"]
            return True
        if self.debug:
            cherrypy.log('Setting request.login to %r' % username, 'TOOLS.SESSAUTH')
        request.login = username
        self.on_check(username)
    
    def run(self):
        request = cherrypy.serving.request
        response = cherrypy.serving.response
        
        path = request.path_info
        if path.endswith('login_screen'):
            if self.debug:
                cherrypy.log('routing %r to login_screen' % path, 'TOOLS.SESSAUTH')
            return self.login_screen(**request.params)
        elif path.endswith('do_login'):
            if request.method != 'POST':
                response.headers['Allow'] = "POST"
                if self.debug:
                    cherrypy.log('do_login requires POST', 'TOOLS.SESSAUTH')
                raise cherrypy.HTTPError(405)
            if self.debug:
                cherrypy.log('routing %r to do_login' % path, 'TOOLS.SESSAUTH')
            return self.do_login(**request.params)
        elif path.endswith('do_logout'):
            if request.method != 'POST':
                response.headers['Allow'] = "POST"
                raise cherrypy.HTTPError(405)
            if self.debug:
                cherrypy.log('routing %r to do_logout' % path, 'TOOLS.SESSAUTH')
            return self.do_logout(**request.params)
        else:
            if self.debug:
                cherrypy.log('No special path, running do_check', 'TOOLS.SESSAUTH')
            return self.do_check()


def session_auth(**kwargs):
    sa = SessionAuth()
    for k, v in kwargs.items():
        setattr(sa, k, v)
    return sa.run()
session_auth.__doc__ = """Session authentication hook.

Any attribute of the SessionAuth class may be overridden via a keyword arg
to this function:

""" + "\n".join(["%s: %s" % (k, type(getattr(SessionAuth, k)).__name__)
                 for k in dir(SessionAuth) if not k.startswith("__")])


def log_traceback(severity=logging.ERROR, debug=False):
    """Write the last error's traceback to the cherrypy error log."""
    cherrypy.log("", "HTTP", severity=severity, traceback=True)

def log_request_headers(debug=False):
    """Write request headers to the cherrypy error log."""
    h = ["  %s: %s" % (k, v) for k, v in cherrypy.serving.request.header_list]
    cherrypy.log('\nRequest Headers:\n' + '\n'.join(h), "HTTP")

def log_hooks(debug=False):
    """Write request.hooks to the cherrypy error log."""
    request = cherrypy.serving.request
    
    msg = []
    # Sort by the standard points if possible.
    from cherrypy import _cprequest
    points = _cprequest.hookpoints
    for k in request.hooks.keys():
        if k not in points:
            points.append(k)
    
    for k in points:
        msg.append("    %s:" % k)
        v = request.hooks.get(k, [])
        v.sort()
        for h in v:
            msg.append("        %r" % h)
    cherrypy.log('\nRequest Hooks for ' + cherrypy.url() +
                 ':\n' + '\n'.join(msg), "HTTP")

def redirect(url='', internal=True, debug=False):
    """Raise InternalRedirect or HTTPRedirect to the given url."""
    if debug:
        cherrypy.log('Redirecting %sto: %s' %
                     ({True: 'internal ', False: ''}[internal], url),
                     'TOOLS.REDIRECT')
    if internal:
        raise cherrypy.InternalRedirect(url)
    else:
        raise cherrypy.HTTPRedirect(url)

def trailing_slash(missing=True, extra=False, status=None, debug=False):
    """Redirect if path_info has (missing|extra) trailing slash."""
    request = cherrypy.serving.request
    pi = request.path_info
    
    if debug:
        cherrypy.log('is_index: %r, missing: %r, extra: %r, path_info: %r' %
                     (request.is_index, missing, extra, pi),
                     'TOOLS.TRAILING_SLASH')
    if request.is_index is True:
        if missing:
            if not pi.endswith('/'):
                new_url = cherrypy.url(pi + '/', request.query_string)
                raise cherrypy.HTTPRedirect(new_url, status=status or 301)
    elif request.is_index is False:
        if extra:
            # If pi == '/', don't redirect to ''!
            if pi.endswith('/') and pi != '/':
                new_url = cherrypy.url(pi[:-1], request.query_string)
                raise cherrypy.HTTPRedirect(new_url, status=status or 301)

def flatten(debug=False):
    """Wrap response.body in a generator that recursively iterates over body.
    
    This allows cherrypy.response.body to consist of 'nested generators';
    that is, a set of generators that yield generators.
    """
    import types
    def flattener(input):
        numchunks = 0
        for x in input:
            if not isinstance(x, types.GeneratorType):
                numchunks += 1
                yield x
            else:
                for y in flattener(x):
                    numchunks += 1
                    yield y
        if debug:
            cherrypy.log('Flattened %d chunks' % numchunks, 'TOOLS.FLATTEN')
    response = cherrypy.serving.response
    response.body = flattener(response.body)


def accept(media=None, debug=False):
    """Return the client's preferred media-type (from the given Content-Types).
    
    If 'media' is None (the default), no test will be performed.
    
    If 'media' is provided, it should be the Content-Type value (as a string)
    or values (as a list or tuple of strings) which the current resource
    can emit. The client's acceptable media ranges (as declared in the
    Accept request header) will be matched in order to these Content-Type
    values; the first such string is returned. That is, the return value
    will always be one of the strings provided in the 'media' arg (or None
    if 'media' is None).
    
    If no match is found, then HTTPError 406 (Not Acceptable) is raised.
    Note that most web browsers send */* as a (low-quality) acceptable
    media range, which should match any Content-Type. In addition, "...if
    no Accept header field is present, then it is assumed that the client
    accepts all media types."
    
    Matching types are checked in order of client preference first,
    and then in the order of the given 'media' values.
    
    Note that this function does not honor accept-params (other than "q").
    """
    if not media:
        return
    if isinstance(media, basestring):
        media = [media]
    request = cherrypy.serving.request
    
    # Parse the Accept request header, and try to match one
    # of the requested media-ranges (in order of preference).
    ranges = request.headers.elements('Accept')
    if not ranges:
        # Any media type is acceptable.
        if debug:
            cherrypy.log('No Accept header elements', 'TOOLS.ACCEPT')
        return media[0]
    else:
        # Note that 'ranges' is sorted in order of preference
        for element in ranges:
            if element.qvalue > 0:
                if element.value == "*/*":
                    # Matches any type or subtype
                    if debug:
                        cherrypy.log('Match due to */*', 'TOOLS.ACCEPT')
                    return media[0]
                elif element.value.endswith("/*"):
                    # Matches any subtype
                    mtype = element.value[:-1]  # Keep the slash
                    for m in media:
                        if m.startswith(mtype):
                            if debug:
                                cherrypy.log('Match due to %s' % element.value,
                                             'TOOLS.ACCEPT')
                            return m
                else:
                    # Matches exact value
                    if element.value in media:
                        if debug:
                            cherrypy.log('Match due to %s' % element.value,
                                         'TOOLS.ACCEPT')
                        return element.value
    
    # No suitable media-range found.
    ah = request.headers.get('Accept')
    if ah is None:
        msg = "Your client did not send an Accept header."
    else:
        msg = "Your client sent this Accept header: %s." % ah
    msg += (" But this resource only emits these media types: %s." %
            ", ".join(media))
    raise cherrypy.HTTPError(406, msg)


class MonitoredHeaderMap(_httputil.HeaderMap):
    
    def __init__(self):
        self.accessed_headers = set()
    
    def __getitem__(self, key):
        self.accessed_headers.add(key)
        return _httputil.HeaderMap.__getitem__(self, key)
    
    def __contains__(self, key):
        self.accessed_headers.add(key)
        return _httputil.HeaderMap.__contains__(self, key)
    
    def get(self, key, default=None):
        self.accessed_headers.add(key)
        return _httputil.HeaderMap.get(self, key, default=default)
    
    if hasattr({}, 'has_key'):
        # Python 2
        def has_key(self, key):
            self.accessed_headers.add(key)
            return _httputil.HeaderMap.has_key(self, key)


def autovary(ignore=None, debug=False):
    """Auto-populate the Vary response header based on request.header access."""
    request = cherrypy.serving.request
    
    req_h = request.headers
    request.headers = MonitoredHeaderMap()
    request.headers.update(req_h)
    if ignore is None:
        ignore = set(['Content-Disposition', 'Content-Length', 'Content-Type'])
    
    def set_response_header():
        resp_h = cherrypy.serving.response.headers
        v = set([e.value for e in resp_h.elements('Vary')])
        if debug:
            cherrypy.log('Accessed headers: %s' % request.headers.accessed_headers,
                         'TOOLS.AUTOVARY')
        v = v.union(request.headers.accessed_headers)
        v = v.difference(ignore)
        v = list(v)
        v.sort()
        resp_h['Vary'] = ', '.join(v)
    request.hooks.attach('before_finalize', set_response_header, 95)

