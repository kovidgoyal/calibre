"""Functions for builtin CherryPy tools."""

import logging
import md5
import re

import cherrypy
from cherrypy.lib import http as _http


#                     Conditional HTTP request support                     #

def validate_etags(autotags=False):
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
    See http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.24
    """
    response = cherrypy.response
    
    # Guard against being run twice.
    if hasattr(response, "ETag"):
        return
    
    status, reason, msg = _http.valid_status(response.status)
    
    etag = response.headers.get('ETag')
    
    # Automatic ETag generation. See warning in docstring.
    if (not etag) and autotags:
        if status == 200:
            etag = response.collapse_body()
            etag = '"%s"' % md5.new(etag).hexdigest()
            response.headers['ETag'] = etag
    
    response.ETag = etag
    
    # "If the request would, without the If-Match header field, result in
    # anything other than a 2xx or 412 status, then the If-Match header
    # MUST be ignored."
    if status >= 200 and status <= 299:
        request = cherrypy.request
        
        conditions = request.headers.elements('If-Match') or []
        conditions = [str(x) for x in conditions]
        if conditions and not (conditions == ["*"] or etag in conditions):
            raise cherrypy.HTTPError(412, "If-Match failed: ETag %r did "
                                     "not match %r" % (etag, conditions))
        
        conditions = request.headers.elements('If-None-Match') or []
        conditions = [str(x) for x in conditions]
        if conditions == ["*"] or etag in conditions:
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
    response = cherrypy.response
    lastmod = response.headers.get('Last-Modified')
    if lastmod:
        status, reason, msg = _http.valid_status(response.status)
        
        request = cherrypy.request
        
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

def proxy(base=None, local='X-Forwarded-Host', remote='X-Forwarded-For',
          scheme='X-Forwarded-Proto'):
    """Change the base URL (scheme://host[:port][/path]).
    
    For running a CP server behind Apache, lighttpd, or other HTTP server.
    
    If you want the new request.base to include path info (not just the host),
    you must explicitly set base to the full base path, and ALSO set 'local'
    to '', so that the X-Forwarded-Host request header (which never includes
    path info) does not override it.
    
    cherrypy.request.remote.ip (the IP address of the client) will be
    rewritten if the header specified by the 'remote' arg is valid.
    By default, 'remote' is set to 'X-Forwarded-For'. If you do not
    want to rewrite remote.ip, set the 'remote' arg to an empty string.
    """
    
    request = cherrypy.request
    
    if scheme:
        s = request.headers.get(scheme, None)
        if s == 'on' and 'ssl' in scheme.lower():
            # This handles e.g. webfaction's 'X-Forwarded-Ssl: on' header
            scheme = 'https'
        else:
            # This is for lighttpd/pound/Mongrel's 'X-Forwarded-Proto: https'
            scheme = s
    if not scheme:
        scheme = request.base[:request.base.find("://")]
    
    if local:
        base = request.headers.get(local, base)
    if not base:
        port = cherrypy.request.local.port
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
        if xff:
            if remote == 'X-Forwarded-For':
                # See http://bob.pythonmac.org/archives/2005/09/23/apache-x-forwarded-for-caveat/
                xff = xff.split(',')[-1].strip()
            request.remote.ip = xff


def ignore_headers(headers=('Range',)):
    """Delete request headers whose field names are included in 'headers'.
    
    This is a useful tool for working behind certain HTTP servers;
    for example, Apache duplicates the work that CP does for 'Range'
    headers, and will doubly-truncate the response.
    """
    request = cherrypy.request
    for name in headers:
        if name in request.headers:
            del request.headers[name]


def response_headers(headers=None):
    """Set headers on the response."""
    for name, value in (headers or []):
        cherrypy.response.headers[name] = value
response_headers.failsafe = True


def referer(pattern, accept=True, accept_missing=False, error=403,
            message='Forbidden Referer header.'):
    """Raise HTTPError if Referer header does/does not match the given pattern.
    
    pattern: a regular expression pattern to test against the Referer.
    accept: if True, the Referer must match the pattern; if False,
        the Referer must NOT match the pattern.
    accept_missing: if True, permit requests with no Referer header.
    error: the HTTP error code to return to the client on failure.
    message: a string to include in the response body on failure.
    """
    try:
        match = bool(re.match(pattern, cherrypy.request.headers['Referer']))
        if accept == match:
            return
    except KeyError:
        if accept_missing:
            return
    
    raise cherrypy.HTTPError(error, message)


class SessionAuth(object):
    """Assert that the user is logged in."""
    
    session_key = "username"
    
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
    
    def login_screen(self, from_page='..', username='', error_msg=''):
        return """<html><body>
Message: %(error_msg)s
<form method="post" action="do_login">
    Login: <input type="text" name="username" value="%(username)s" size="10" /><br />
    Password: <input type="password" name="password" size="10" /><br />
    <input type="hidden" name="from_page" value="%(from_page)s" /><br />
    <input type="submit" />
</form>
</body></html>""" % {'from_page': from_page, 'username': username,
                     'error_msg': error_msg}
    
    def do_login(self, username, password, from_page='..'):
        """Login. May raise redirect, or return True if request handled."""
        error_msg = self.check_username_and_password(username, password)
        if error_msg:
            body = self.login_screen(from_page, username, error_msg)
            cherrypy.response.body = body
            if cherrypy.response.headers.has_key("Content-Length"):
                # Delete Content-Length header so finalize() recalcs it.
                del cherrypy.response.headers["Content-Length"]
            return True
        else:
            cherrypy.session[self.session_key] = cherrypy.request.login = username
            self.on_login(username)
            raise cherrypy.HTTPRedirect(from_page or "/")
    
    def do_logout(self, from_page='..'):
        """Logout. May raise redirect, or return True if request handled."""
        sess = cherrypy.session
        username = sess.get(self.session_key)
        sess[self.session_key] = None
        if username:
            cherrypy.request.login = None
            self.on_logout(username)
        raise cherrypy.HTTPRedirect(from_page)
    
    def do_check(self):
        """Assert username. May raise redirect, or return True if request handled."""
        sess = cherrypy.session
        request = cherrypy.request
        
        username = sess.get(self.session_key)
        if not username:
            sess[self.session_key] = username = self.anonymous()
        if not username:
            cherrypy.response.body = self.login_screen(cherrypy.url(qs=request.query_string))
            if cherrypy.response.headers.has_key("Content-Length"):
                # Delete Content-Length header so finalize() recalcs it.
                del cherrypy.response.headers["Content-Length"]
            return True
        cherrypy.request.login = username
        self.on_check(username)
    
    def run(self):
        request = cherrypy.request
        path = request.path_info
        if path.endswith('login_screen'):
            return self.login_screen(**request.params)
        elif path.endswith('do_login'):
            return self.do_login(**request.params)
        elif path.endswith('do_logout'):
            return self.do_logout(**request.params)
        else:
            return self.do_check()


def session_auth(**kwargs):
    sa = SessionAuth()
    for k, v in kwargs.iteritems():
        setattr(sa, k, v)
    return sa.run()
session_auth.__doc__ = """Session authentication hook.

Any attribute of the SessionAuth class may be overridden via a keyword arg
to this function:

""" + "\n".join(["%s: %s" % (k, type(getattr(SessionAuth, k)).__name__)
                 for k in dir(SessionAuth) if not k.startswith("__")])


def log_traceback(severity=logging.DEBUG):
    """Write the last error's traceback to the cherrypy error log."""
    cherrypy.log("", "HTTP", severity=severity, traceback=True)

def log_request_headers():
    """Write request headers to the cherrypy error log."""
    h = ["  %s: %s" % (k, v) for k, v in cherrypy.request.header_list]
    cherrypy.log('\nRequest Headers:\n' + '\n'.join(h), "HTTP")

def log_hooks():
    """Write request.hooks to the cherrypy error log."""
    msg = []
    # Sort by the standard points if possible.
    from cherrypy import _cprequest
    points = _cprequest.hookpoints
    for k in cherrypy.request.hooks.keys():
        if k not in points:
            points.append(k)
    
    for k in points:
        msg.append("    %s:" % k)
        v = cherrypy.request.hooks.get(k, [])
        v.sort()
        for h in v:
            msg.append("        %r" % h)
    cherrypy.log('\nRequest Hooks for ' + cherrypy.url() +
                 ':\n' + '\n'.join(msg), "HTTP")

def redirect(url='', internal=True):
    """Raise InternalRedirect or HTTPRedirect to the given url."""
    if internal:
        raise cherrypy.InternalRedirect(url)
    else:
        raise cherrypy.HTTPRedirect(url)

def trailing_slash(missing=True, extra=False):
    """Redirect if path_info has (missing|extra) trailing slash."""
    request = cherrypy.request
    pi = request.path_info
    
    if request.is_index is True:
        if missing:
            if not pi.endswith('/'):
                new_url = cherrypy.url(pi + '/', request.query_string)
                raise cherrypy.HTTPRedirect(new_url)
    elif request.is_index is False:
        if extra:
            # If pi == '/', don't redirect to ''!
            if pi.endswith('/') and pi != '/':
                new_url = cherrypy.url(pi[:-1], request.query_string)
                raise cherrypy.HTTPRedirect(new_url)

def flatten():
    """Wrap response.body in a generator that recursively iterates over body.
    
    This allows cherrypy.response.body to consist of 'nested generators';
    that is, a set of generators that yield generators.
    """
    import types
    def flattener(input):
        for x in input:
            if not isinstance(x, types.GeneratorType):
                yield x
            else:
                for y in flattener(x):
                    yield y 
    response = cherrypy.response
    response.body = flattener(response.body)


def accept(media=None):
    """Return the client's preferred media-type (from the given Content-Types).
    
    If 'media' is None (the default), no test will be performed.
    
    If 'media' is provided, it should be the Content-Type value (as a string)
    or values (as a list or tuple of strings) which the current request
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
    
    # Parse the Accept request header, and try to match one
    # of the requested media-ranges (in order of preference).
    ranges = cherrypy.request.headers.elements('Accept')
    if not ranges:
        # Any media type is acceptable.
        return media[0]
    else:
        # Note that 'ranges' is sorted in order of preference
        for element in ranges:
            if element.qvalue > 0:
                if element.value == "*/*":
                    # Matches any type or subtype
                    return media[0]
                elif element.value.endswith("/*"):
                    # Matches any subtype
                    mtype = element.value[:-1]  # Keep the slash
                    for m in media:
                        if m.startswith(mtype):
                            return m
                else:
                    # Matches exact value
                    if element.value in media:
                        return element.value
    
    # No suitable media-range found.
    ah = cherrypy.request.headers.get('Accept')
    if ah is None:
        msg = "Your client did not send an Accept header."
    else:
        msg = "Your client sent this Accept header: %s." % ah
    msg += (" But this resource only emits these media types: %s." %
            ", ".join(media))
    raise cherrypy.HTTPError(406, msg)

