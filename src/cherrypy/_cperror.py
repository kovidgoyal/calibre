"""Error classes for CherryPy."""

from cgi import escape as _escape
from sys import exc_info as _exc_info
from traceback import format_exception as _format_exception
from urlparse import urljoin as _urljoin
from cherrypy.lib import http as _http


class CherryPyException(Exception):
    pass


class TimeoutError(CherryPyException):
    """Exception raised when Response.timed_out is detected."""
    pass


class InternalRedirect(CherryPyException):
    """Exception raised to switch to the handler for a different URL.
    
    Any request.params must be supplied in a query string.
    """
    
    def __init__(self, path):
        import cherrypy
        request = cherrypy.request
        
        self.query_string = ""
        if "?" in path:
            # Separate any params included in the path
            path, self.query_string = path.split("?", 1)
        
        # Note that urljoin will "do the right thing" whether url is:
        #  1. a URL relative to root (e.g. "/dummy")
        #  2. a URL relative to the current path
        # Note that any query string will be discarded.
        path = _urljoin(request.path_info, path)
        
        # Set a 'path' member attribute so that code which traps this
        # error can have access to it.
        self.path = path
        
        CherryPyException.__init__(self, path, self.query_string)


class HTTPRedirect(CherryPyException):
    """Exception raised when the request should be redirected.
    
    The new URL must be passed as the first argument to the Exception,
    e.g., HTTPRedirect(newUrl). Multiple URLs are allowed. If a URL is
    absolute, it will be used as-is. If it is relative, it is assumed
    to be relative to the current cherrypy.request.path_info.
    """
    
    def __init__(self, urls, status=None):
        import cherrypy
        request = cherrypy.request
        
        if isinstance(urls, basestring):
            urls = [urls]
        
        abs_urls = []
        for url in urls:
            # Note that urljoin will "do the right thing" whether url is:
            #  1. a complete URL with host (e.g. "http://www.example.com/test")
            #  2. a URL relative to root (e.g. "/dummy")
            #  3. a URL relative to the current path
            # Note that any query string in cherrypy.request is discarded.
            url = _urljoin(cherrypy.url(), url)
            abs_urls.append(url)
        self.urls = abs_urls
        
        # RFC 2616 indicates a 301 response code fits our goal; however,
        # browser support for 301 is quite messy. Do 302/303 instead. See
        # http://ppewww.ph.gla.ac.uk/~flavell/www/post-redirect.html
        if status is None:
            if request.protocol >= (1, 1):
                status = 303
            else:
                status = 302
        else:
            status = int(status)
            if status < 300 or status > 399:
                raise ValueError("status must be between 300 and 399.")
        
        self.status = status
        CherryPyException.__init__(self, abs_urls, status)
    
    def set_response(self):
        """Modify cherrypy.response status, headers, and body to represent self.
        
        CherryPy uses this internally, but you can also use it to create an
        HTTPRedirect object and set its output without *raising* the exception.
        """
        import cherrypy
        response = cherrypy.response
        response.status = status = self.status
        
        if status in (300, 301, 302, 303, 307):
            response.headers['Content-Type'] = "text/html"
            # "The ... URI SHOULD be given by the Location field
            # in the response."
            response.headers['Location'] = self.urls[0]
            
            # "Unless the request method was HEAD, the entity of the response
            # SHOULD contain a short hypertext note with a hyperlink to the
            # new URI(s)."
            msg = {300: "This resource can be found at <a href='%s'>%s</a>.",
                   301: "This resource has permanently moved to <a href='%s'>%s</a>.",
                   302: "This resource resides temporarily at <a href='%s'>%s</a>.",
                   303: "This resource can be found at <a href='%s'>%s</a>.",
                   307: "This resource has moved temporarily to <a href='%s'>%s</a>.",
                   }[status]
            response.body = "<br />\n".join([msg % (u, u) for u in self.urls])
            # Previous code may have set C-L, so we have to reset it
            # (allow finalize to set it).
            response.headers.pop('Content-Length', None)
        elif status == 304:
            # Not Modified.
            # "The response MUST include the following header fields:
            # Date, unless its omission is required by section 14.18.1"
            # The "Date" header should have been set in Response.__init__
            
            # "...the response SHOULD NOT include other entity-headers."
            for key in ('Allow', 'Content-Encoding', 'Content-Language',
                        'Content-Length', 'Content-Location', 'Content-MD5',
                        'Content-Range', 'Content-Type', 'Expires',
                        'Last-Modified'):
                if key in response.headers:
                    del response.headers[key]
            
            # "The 304 response MUST NOT contain a message-body."
            response.body = None
            # Previous code may have set C-L, so we have to reset it.
            response.headers.pop('Content-Length', None)
        elif status == 305:
            # Use Proxy.
            # self.urls[0] should be the URI of the proxy.
            response.headers['Location'] = self.urls[0]
            response.body = None
            # Previous code may have set C-L, so we have to reset it.
            response.headers.pop('Content-Length', None)
        else:
            raise ValueError("The %s status code is unknown." % status)
    
    def __call__(self):
        """Use this exception as a request.handler (raise self)."""
        raise self


def clean_headers(status):
    """Remove any headers which should not apply to an error response."""
    import cherrypy
    
    response = cherrypy.response
    
    # Remove headers which applied to the original content,
    # but do not apply to the error page.
    respheaders = response.headers
    for key in ["Accept-Ranges", "Age", "ETag", "Location", "Retry-After",
                "Vary", "Content-Encoding", "Content-Length", "Expires",
                "Content-Location", "Content-MD5", "Last-Modified"]:
        if respheaders.has_key(key):
            del respheaders[key]
    
    if status != 416:
        # A server sending a response with status code 416 (Requested
        # range not satisfiable) SHOULD include a Content-Range field
        # with a byte-range-resp-spec of "*". The instance-length
        # specifies the current length of the selected resource.
        # A response with status code 206 (Partial Content) MUST NOT
        # include a Content-Range field with a byte-range- resp-spec of "*".
        if respheaders.has_key("Content-Range"):
            del respheaders["Content-Range"]


class HTTPError(CherryPyException):
    """ Exception used to return an HTTP error code (4xx-5xx) to the client.
        This exception will automatically set the response status and body.
        
        A custom message (a long description to display in the browser)
        can be provided in place of the default.
    """
    
    def __init__(self, status=500, message=None):
        self.status = status = int(status)
        if status < 400 or status > 599:
            raise ValueError("status must be between 400 and 599.")
        # See http://www.python.org/dev/peps/pep-0352/
        # self.message = message
        self._message = message
        CherryPyException.__init__(self, status, message)
    
    def set_response(self):
        """Modify cherrypy.response status, headers, and body to represent self.
        
        CherryPy uses this internally, but you can also use it to create an
        HTTPError object and set its output without *raising* the exception.
        """
        import cherrypy
        
        response = cherrypy.response
        
        clean_headers(self.status)
        
        # In all cases, finalize will be called after this method,
        # so don't bother cleaning up response values here.
        response.status = self.status
        tb = None
        if cherrypy.request.show_tracebacks:
            tb = format_exc()
        response.headers['Content-Type'] = "text/html"
        
        content = self.get_error_page(self.status, traceback=tb,
                                      message=self._message)
        response.body = content
        response.headers['Content-Length'] = len(content)
        
        _be_ie_unfriendly(self.status)
    
    def get_error_page(self, *args, **kwargs):
        return get_error_page(*args, **kwargs)
    
    def __call__(self):
        """Use this exception as a request.handler (raise self)."""
        raise self


class NotFound(HTTPError):
    """Exception raised when a URL could not be mapped to any handler (404)."""
    
    def __init__(self, path=None):
        if path is None:
            import cherrypy
            path = cherrypy.request.script_name + cherrypy.request.path_info
        self.args = (path,)
        HTTPError.__init__(self, 404, "The path %r was not found." % path)


_HTTPErrorTemplate = '''<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html>
<head>
    <meta http-equiv="Content-Type" content="text/html; charset=utf-8"></meta>
    <title>%(status)s</title>
    <style type="text/css">
    #powered_by {
        margin-top: 20px;
        border-top: 2px solid black;
        font-style: italic;
    }

    #traceback {
        color: red;
    }
    </style>
</head>
    <body>
        <h2>%(status)s</h2>
        <p>%(message)s</p>
        <pre id="traceback">%(traceback)s</pre>
    <div id="powered_by">
    <span>Powered by <a href="http://www.cherrypy.org">CherryPy %(version)s</a></span>
    </div>
    </body>
</html>
'''

def get_error_page(status, **kwargs):
    """Return an HTML page, containing a pretty error response.
    
    status should be an int or a str.
    kwargs will be interpolated into the page template.
    """
    import cherrypy
    
    try:
        code, reason, message = _http.valid_status(status)
    except ValueError, x:
        raise cherrypy.HTTPError(500, x.args[0])
    
    # We can't use setdefault here, because some
    # callers send None for kwarg values.
    if kwargs.get('status') is None:
        kwargs['status'] = "%s %s" % (code, reason)
    if kwargs.get('message') is None:
        kwargs['message'] = message
    if kwargs.get('traceback') is None:
        kwargs['traceback'] = ''
    if kwargs.get('version') is None:
        kwargs['version'] = cherrypy.__version__
    
    for k, v in kwargs.iteritems():
        if v is None:
            kwargs[k] = ""
        else:
            kwargs[k] = _escape(kwargs[k])
    
    # Use a custom template or callable for the error page?
    pages = cherrypy.request.error_page
    error_page = pages.get(code) or pages.get('default')
    if error_page:
        try:
            if callable(error_page):
                return error_page(**kwargs)
            else:
                return file(error_page, 'rb').read() % kwargs
        except:
            e = _format_exception(*_exc_info())[-1]
            m = kwargs['message']
            if m:
                m += "<br />"
            m += "In addition, the custom error page failed:\n<br />%s" % e
            kwargs['message'] = m
    
    return _HTTPErrorTemplate % kwargs


_ie_friendly_error_sizes = {
    400: 512, 403: 256, 404: 512, 405: 256,
    406: 512, 408: 512, 409: 512, 410: 256,
    500: 512, 501: 512, 505: 512,
    }


def _be_ie_unfriendly(status):
    import cherrypy
    response = cherrypy.response
    
    # For some statuses, Internet Explorer 5+ shows "friendly error
    # messages" instead of our response.body if the body is smaller
    # than a given size. Fix this by returning a body over that size
    # (by adding whitespace).
    # See http://support.microsoft.com/kb/q218155/
    s = _ie_friendly_error_sizes.get(status, 0)
    if s:
        s += 1
        # Since we are issuing an HTTP error status, we assume that
        # the entity is short, and we should just collapse it.
        content = response.collapse_body()
        l = len(content)
        if l and l < s:
            # IN ADDITION: the response must be written to IE
            # in one chunk or it will still get replaced! Bah.
            content = content + (" " * (s - l))
        response.body = content
        response.headers['Content-Length'] = len(content)


def format_exc(exc=None):
    """Return exc (or sys.exc_info if None), formatted."""
    if exc is None:
        exc = _exc_info()
    if exc == (None, None, None):
        return ""
    import traceback
    return "".join(traceback.format_exception(*exc))

def bare_error(extrabody=None):
    """Produce status, headers, body for a critical error.
    
    Returns a triple without calling any other questionable functions,
    so it should be as error-free as possible. Call it from an HTTP server
    if you get errors outside of the request.
    
    If extrabody is None, a friendly but rather unhelpful error message
    is set in the body. If extrabody is a string, it will be appended
    as-is to the body.
    """
    
    # The whole point of this function is to be a last line-of-defense
    # in handling errors. That is, it must not raise any errors itself;
    # it cannot be allowed to fail. Therefore, don't add to it!
    # In particular, don't call any other CP functions.
    
    body = "Unrecoverable error in the server."
    if extrabody is not None:
        body += "\n" + extrabody
    
    return ("500 Internal Server Error",
            [('Content-Type', 'text/plain'),
             ('Content-Length', str(len(body)))],
            [body])


