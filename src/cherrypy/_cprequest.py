
import os
import sys
import time
import warnings

import cherrypy
from cherrypy._cpcompat import basestring, copykeys, ntob, unicodestr
from cherrypy._cpcompat import SimpleCookie, CookieError, py3k
from cherrypy import _cpreqbody, _cpconfig
from cherrypy._cperror import format_exc, bare_error
from cherrypy.lib import httputil, file_generator


class Hook(object):
    """A callback and its metadata: failsafe, priority, and kwargs."""
    
    callback = None
    """
    The bare callable that this Hook object is wrapping, which will
    be called when the Hook is called."""
    
    failsafe = False
    """
    If True, the callback is guaranteed to run even if other callbacks
    from the same call point raise exceptions."""
    
    priority = 50
    """
    Defines the order of execution for a list of Hooks. Priority numbers
    should be limited to the closed interval [0, 100], but values outside
    this range are acceptable, as are fractional values."""
    
    kwargs = {}
    """
    A set of keyword arguments that will be passed to the
    callable on each call."""
    
    def __init__(self, callback, failsafe=None, priority=None, **kwargs):
        self.callback = callback
        
        if failsafe is None:
            failsafe = getattr(callback, "failsafe", False)
        self.failsafe = failsafe
        
        if priority is None:
            priority = getattr(callback, "priority", 50)
        self.priority = priority
        
        self.kwargs = kwargs
    
    def __lt__(self, other):
        # Python 3
        return self.priority < other.priority

    def __cmp__(self, other):
        # Python 2
        return cmp(self.priority, other.priority)
    
    def __call__(self):
        """Run self.callback(**self.kwargs)."""
        return self.callback(**self.kwargs)
    
    def __repr__(self):
        cls = self.__class__
        return ("%s.%s(callback=%r, failsafe=%r, priority=%r, %s)"
                % (cls.__module__, cls.__name__, self.callback,
                   self.failsafe, self.priority,
                   ", ".join(['%s=%r' % (k, v)
                              for k, v in self.kwargs.items()])))


class HookMap(dict):
    """A map of call points to lists of callbacks (Hook objects)."""
    
    def __new__(cls, points=None):
        d = dict.__new__(cls)
        for p in points or []:
            d[p] = []
        return d
    
    def __init__(self, *a, **kw):
        pass
    
    def attach(self, point, callback, failsafe=None, priority=None, **kwargs):
        """Append a new Hook made from the supplied arguments."""
        self[point].append(Hook(callback, failsafe, priority, **kwargs))
    
    def run(self, point):
        """Execute all registered Hooks (callbacks) for the given point."""
        exc = None
        hooks = self[point]
        hooks.sort()
        for hook in hooks:
            # Some hooks are guaranteed to run even if others at
            # the same hookpoint fail. We will still log the failure,
            # but proceed on to the next hook. The only way
            # to stop all processing from one of these hooks is
            # to raise SystemExit and stop the whole server.
            if exc is None or hook.failsafe:
                try:
                    hook()
                except (KeyboardInterrupt, SystemExit):
                    raise
                except (cherrypy.HTTPError, cherrypy.HTTPRedirect,
                        cherrypy.InternalRedirect):
                    exc = sys.exc_info()[1]
                except:
                    exc = sys.exc_info()[1]
                    cherrypy.log(traceback=True, severity=40)
        if exc:
            raise exc
    
    def __copy__(self):
        newmap = self.__class__()
        # We can't just use 'update' because we want copies of the
        # mutable values (each is a list) as well.
        for k, v in self.items():
            newmap[k] = v[:]
        return newmap
    copy = __copy__
    
    def __repr__(self):
        cls = self.__class__
        return "%s.%s(points=%r)" % (cls.__module__, cls.__name__, copykeys(self))


# Config namespace handlers

def hooks_namespace(k, v):
    """Attach bare hooks declared in config."""
    # Use split again to allow multiple hooks for a single
    # hookpoint per path (e.g. "hooks.before_handler.1").
    # Little-known fact you only get from reading source ;)
    hookpoint = k.split(".", 1)[0]
    if isinstance(v, basestring):
        v = cherrypy.lib.attributes(v)
    if not isinstance(v, Hook):
        v = Hook(v)
    cherrypy.serving.request.hooks[hookpoint].append(v)

def request_namespace(k, v):
    """Attach request attributes declared in config."""
    # Provides config entries to set request.body attrs (like attempt_charsets).
    if k[:5] == 'body.':
        setattr(cherrypy.serving.request.body, k[5:], v)
    else:
        setattr(cherrypy.serving.request, k, v)

def response_namespace(k, v):
    """Attach response attributes declared in config."""
    # Provides config entries to set default response headers
    # http://cherrypy.org/ticket/889
    if k[:8] == 'headers.':
        cherrypy.serving.response.headers[k.split('.', 1)[1]] = v
    else:
        setattr(cherrypy.serving.response, k, v)

def error_page_namespace(k, v):
    """Attach error pages declared in config."""
    if k != 'default':
        k = int(k)
    cherrypy.serving.request.error_page[k] = v


hookpoints = ['on_start_resource', 'before_request_body',
              'before_handler', 'before_finalize',
              'on_end_resource', 'on_end_request',
              'before_error_response', 'after_error_response']


class Request(object):
    """An HTTP request.
    
    This object represents the metadata of an HTTP request message;
    that is, it contains attributes which describe the environment
    in which the request URL, headers, and body were sent (if you
    want tools to interpret the headers and body, those are elsewhere,
    mostly in Tools). This 'metadata' consists of socket data,
    transport characteristics, and the Request-Line. This object
    also contains data regarding the configuration in effect for
    the given URL, and the execution plan for generating a response.
    """
    
    prev = None
    """
    The previous Request object (if any). This should be None
    unless we are processing an InternalRedirect."""
    
    # Conversation/connection attributes
    local = httputil.Host("127.0.0.1", 80)
    "An httputil.Host(ip, port, hostname) object for the server socket."
    
    remote = httputil.Host("127.0.0.1", 1111)
    "An httputil.Host(ip, port, hostname) object for the client socket."
    
    scheme = "http"
    """
    The protocol used between client and server. In most cases,
    this will be either 'http' or 'https'."""
    
    server_protocol = "HTTP/1.1"
    """
    The HTTP version for which the HTTP server is at least
    conditionally compliant."""
    
    base = ""
    """The (scheme://host) portion of the requested URL.
    In some cases (e.g. when proxying via mod_rewrite), this may contain
    path segments which cherrypy.url uses when constructing url's, but
    which otherwise are ignored by CherryPy. Regardless, this value
    MUST NOT end in a slash."""
    
    # Request-Line attributes
    request_line = ""
    """
    The complete Request-Line received from the client. This is a
    single string consisting of the request method, URI, and protocol
    version (joined by spaces). Any final CRLF is removed."""
    
    method = "GET"
    """
    Indicates the HTTP method to be performed on the resource identified
    by the Request-URI. Common methods include GET, HEAD, POST, PUT, and
    DELETE. CherryPy allows any extension method; however, various HTTP
    servers and gateways may restrict the set of allowable methods.
    CherryPy applications SHOULD restrict the set (on a per-URI basis)."""
    
    query_string = ""
    """
    The query component of the Request-URI, a string of information to be
    interpreted by the resource. The query portion of a URI follows the
    path component, and is separated by a '?'. For example, the URI
    'http://www.cherrypy.org/wiki?a=3&b=4' has the query component,
    'a=3&b=4'."""
    
    query_string_encoding = 'utf8'
    """
    The encoding expected for query string arguments after % HEX HEX decoding).
    If a query string is provided that cannot be decoded with this encoding,
    404 is raised (since technically it's a different URI). If you want
    arbitrary encodings to not error, set this to 'Latin-1'; you can then
    encode back to bytes and re-decode to whatever encoding you like later.
    """
    
    protocol = (1, 1)
    """The HTTP protocol version corresponding to the set
    of features which should be allowed in the response. If BOTH
    the client's request message AND the server's level of HTTP
    compliance is HTTP/1.1, this attribute will be the tuple (1, 1).
    If either is 1.0, this attribute will be the tuple (1, 0).
    Lower HTTP protocol versions are not explicitly supported."""
    
    params = {}
    """
    A dict which combines query string (GET) and request entity (POST)
    variables. This is populated in two stages: GET params are added
    before the 'on_start_resource' hook, and POST params are added
    between the 'before_request_body' and 'before_handler' hooks."""
    
    # Message attributes
    header_list = []
    """
    A list of the HTTP request headers as (name, value) tuples.
    In general, you should use request.headers (a dict) instead."""
    
    headers = httputil.HeaderMap()
    """
    A dict-like object containing the request headers. Keys are header
    names (in Title-Case format); however, you may get and set them in
    a case-insensitive manner. That is, headers['Content-Type'] and
    headers['content-type'] refer to the same value. Values are header
    values (decoded according to :rfc:`2047` if necessary). See also:
    httputil.HeaderMap, httputil.HeaderElement."""
    
    cookie = SimpleCookie()
    """See help(Cookie)."""
    
    rfile = None
    """
    If the request included an entity (body), it will be available
    as a stream in this attribute. However, the rfile will normally
    be read for you between the 'before_request_body' hook and the
    'before_handler' hook, and the resulting string is placed into
    either request.params or the request.body attribute.
    
    You may disable the automatic consumption of the rfile by setting
    request.process_request_body to False, either in config for the desired
    path, or in an 'on_start_resource' or 'before_request_body' hook.
    
    WARNING: In almost every case, you should not attempt to read from the
    rfile stream after CherryPy's automatic mechanism has read it. If you
    turn off the automatic parsing of rfile, you should read exactly the
    number of bytes specified in request.headers['Content-Length'].
    Ignoring either of these warnings may result in a hung request thread
    or in corruption of the next (pipelined) request.
    """
    
    process_request_body = True
    """
    If True, the rfile (if any) is automatically read and parsed,
    and the result placed into request.params or request.body."""
    
    methods_with_bodies = ("POST", "PUT")
    """
    A sequence of HTTP methods for which CherryPy will automatically
    attempt to read a body from the rfile."""
    
    body = None
    """
    If the request Content-Type is 'application/x-www-form-urlencoded'
    or multipart, this will be None. Otherwise, this will be an instance
    of :class:`RequestBody<cherrypy._cpreqbody.RequestBody>` (which you
    can .read()); this value is set between the 'before_request_body' and
    'before_handler' hooks (assuming that process_request_body is True)."""
    
    # Dispatch attributes
    dispatch = cherrypy.dispatch.Dispatcher()
    """
    The object which looks up the 'page handler' callable and collects
    config for the current request based on the path_info, other
    request attributes, and the application architecture. The core
    calls the dispatcher as early as possible, passing it a 'path_info'
    argument.
    
    The default dispatcher discovers the page handler by matching path_info
    to a hierarchical arrangement of objects, starting at request.app.root.
    See help(cherrypy.dispatch) for more information."""
    
    script_name = ""
    """
    The 'mount point' of the application which is handling this request.
    
    This attribute MUST NOT end in a slash. If the script_name refers to
    the root of the URI, it MUST be an empty string (not "/").
    """
    
    path_info = "/"
    """
    The 'relative path' portion of the Request-URI. This is relative
    to the script_name ('mount point') of the application which is
    handling this request."""

    login = None
    """
    When authentication is used during the request processing this is
    set to 'False' if it failed and to the 'username' value if it succeeded.
    The default 'None' implies that no authentication happened."""
    
    # Note that cherrypy.url uses "if request.app:" to determine whether
    # the call is during a real HTTP request or not. So leave this None.
    app = None
    """The cherrypy.Application object which is handling this request."""
    
    handler = None
    """
    The function, method, or other callable which CherryPy will call to
    produce the response. The discovery of the handler and the arguments
    it will receive are determined by the request.dispatch object.
    By default, the handler is discovered by walking a tree of objects
    starting at request.app.root, and is then passed all HTTP params
    (from the query string and POST body) as keyword arguments."""
    
    toolmaps = {}
    """
    A nested dict of all Toolboxes and Tools in effect for this request,
    of the form: {Toolbox.namespace: {Tool.name: config dict}}."""
    
    config = None
    """
    A flat dict of all configuration entries which apply to the
    current request. These entries are collected from global config,
    application config (based on request.path_info), and from handler
    config (exactly how is governed by the request.dispatch object in
    effect for this request; by default, handler config can be attached
    anywhere in the tree between request.app.root and the final handler,
    and inherits downward)."""
    
    is_index = None
    """
    This will be True if the current request is mapped to an 'index'
    resource handler (also, a 'default' handler if path_info ends with
    a slash). The value may be used to automatically redirect the
    user-agent to a 'more canonical' URL which either adds or removes
    the trailing slash. See cherrypy.tools.trailing_slash."""
    
    hooks = HookMap(hookpoints)
    """
    A HookMap (dict-like object) of the form: {hookpoint: [hook, ...]}.
    Each key is a str naming the hook point, and each value is a list
    of hooks which will be called at that hook point during this request.
    The list of hooks is generally populated as early as possible (mostly
    from Tools specified in config), but may be extended at any time.
    See also: _cprequest.Hook, _cprequest.HookMap, and cherrypy.tools."""
    
    error_response = cherrypy.HTTPError(500).set_response
    """
    The no-arg callable which will handle unexpected, untrapped errors
    during request processing. This is not used for expected exceptions
    (like NotFound, HTTPError, or HTTPRedirect) which are raised in
    response to expected conditions (those should be customized either
    via request.error_page or by overriding HTTPError.set_response).
    By default, error_response uses HTTPError(500) to return a generic
    error response to the user-agent."""
    
    error_page = {}
    """
    A dict of {error code: response filename or callable} pairs.
    
    The error code must be an int representing a given HTTP error code,
    or the string 'default', which will be used if no matching entry
    is found for a given numeric code.
    
    If a filename is provided, the file should contain a Python string-
    formatting template, and can expect by default to receive format 
    values with the mapping keys %(status)s, %(message)s, %(traceback)s,
    and %(version)s. The set of format mappings can be extended by
    overriding HTTPError.set_response.
    
    If a callable is provided, it will be called by default with keyword
    arguments 'status', 'message', 'traceback', and 'version', as for a
    string-formatting template. The callable must return a string or iterable of
    strings which will be set to response.body. It may also override headers or
    perform any other processing.
    
    If no entry is given for an error code, and no 'default' entry exists,
    a default template will be used.
    """
    
    show_tracebacks = True
    """
    If True, unexpected errors encountered during request processing will
    include a traceback in the response body."""

    show_mismatched_params = True
    """
    If True, mismatched parameters encountered during PageHandler invocation
    processing will be included in the response body."""
    
    throws = (KeyboardInterrupt, SystemExit, cherrypy.InternalRedirect)
    """The sequence of exceptions which Request.run does not trap."""
    
    throw_errors = False
    """
    If True, Request.run will not trap any errors (except HTTPRedirect and
    HTTPError, which are more properly called 'exceptions', not errors)."""
    
    closed = False
    """True once the close method has been called, False otherwise."""
    
    stage = None
    """
    A string containing the stage reached in the request-handling process.
    This is useful when debugging a live server with hung requests."""
    
    namespaces = _cpconfig.NamespaceSet(
        **{"hooks": hooks_namespace,
           "request": request_namespace,
           "response": response_namespace,
           "error_page": error_page_namespace,
           "tools": cherrypy.tools,
           })
    
    def __init__(self, local_host, remote_host, scheme="http",
                 server_protocol="HTTP/1.1"):
        """Populate a new Request object.
        
        local_host should be an httputil.Host object with the server info.
        remote_host should be an httputil.Host object with the client info.
        scheme should be a string, either "http" or "https".
        """
        self.local = local_host
        self.remote = remote_host
        self.scheme = scheme
        self.server_protocol = server_protocol
        
        self.closed = False
        
        # Put a *copy* of the class error_page into self.
        self.error_page = self.error_page.copy()
        
        # Put a *copy* of the class namespaces into self.
        self.namespaces = self.namespaces.copy()
        
        self.stage = None
    
    def close(self):
        """Run cleanup code. (Core)"""
        if not self.closed:
            self.closed = True
            self.stage = 'on_end_request'
            self.hooks.run('on_end_request')
            self.stage = 'close'
    
    def run(self, method, path, query_string, req_protocol, headers, rfile):
        r"""Process the Request. (Core)
        
        method, path, query_string, and req_protocol should be pulled directly
        from the Request-Line (e.g. "GET /path?key=val HTTP/1.0").
        
        path
            This should be %XX-unquoted, but query_string should not be.
            
            When using Python 2, they both MUST be byte strings,
            not unicode strings.
            
            When using Python 3, they both MUST be unicode strings,
            not byte strings, and preferably not bytes \x00-\xFF
            disguised as unicode.
        
        headers
            A list of (name, value) tuples.
        
        rfile
            A file-like object containing the HTTP request entity.
        
        When run() is done, the returned object should have 3 attributes:
        
          * status, e.g. "200 OK"
          * header_list, a list of (name, value) tuples
          * body, an iterable yielding strings
        
        Consumer code (HTTP servers) should then access these response
        attributes to build the outbound stream.
        
        """
        response = cherrypy.serving.response
        self.stage = 'run'
        try:
            self.error_response = cherrypy.HTTPError(500).set_response
            
            self.method = method
            path = path or "/"
            self.query_string = query_string or ''
            self.params = {}
            
            # Compare request and server HTTP protocol versions, in case our
            # server does not support the requested protocol. Limit our output
            # to min(req, server). We want the following output:
            #     request    server     actual written   supported response
            #     protocol   protocol  response protocol    feature set
            # a     1.0        1.0           1.0                1.0
            # b     1.0        1.1           1.1                1.0
            # c     1.1        1.0           1.0                1.0
            # d     1.1        1.1           1.1                1.1
            # Notice that, in (b), the response will be "HTTP/1.1" even though
            # the client only understands 1.0. RFC 2616 10.5.6 says we should
            # only return 505 if the _major_ version is different.
            rp = int(req_protocol[5]), int(req_protocol[7])
            sp = int(self.server_protocol[5]), int(self.server_protocol[7])
            self.protocol = min(rp, sp)
            response.headers.protocol = self.protocol
            
            # Rebuild first line of the request (e.g. "GET /path HTTP/1.0").
            url = path
            if query_string:
                url += '?' + query_string
            self.request_line = '%s %s %s' % (method, url, req_protocol)
            
            self.header_list = list(headers)
            self.headers = httputil.HeaderMap()
            
            self.rfile = rfile
            self.body = None
            
            self.cookie = SimpleCookie()
            self.handler = None
            
            # path_info should be the path from the
            # app root (script_name) to the handler.
            self.script_name = self.app.script_name
            self.path_info = pi = path[len(self.script_name):]
            
            self.stage = 'respond'
            self.respond(pi)
            
        except self.throws:
            raise
        except:
            if self.throw_errors:
                raise
            else:
                # Failure in setup, error handler or finalize. Bypass them.
                # Can't use handle_error because we may not have hooks yet.
                cherrypy.log(traceback=True, severity=40)
                if self.show_tracebacks:
                    body = format_exc()
                else:
                    body = ""
                r = bare_error(body)
                response.output_status, response.header_list, response.body = r
        
        if self.method == "HEAD":
            # HEAD requests MUST NOT return a message-body in the response.
            response.body = []
        
        try:
            cherrypy.log.access()
        except:
            cherrypy.log.error(traceback=True)
        
        if response.timed_out:
            raise cherrypy.TimeoutError()
        
        return response
    
    # Uncomment for stage debugging
    # stage = property(lambda self: self._stage, lambda self, v: print(v))
    
    def respond(self, path_info):
        """Generate a response for the resource at self.path_info. (Core)"""
        response = cherrypy.serving.response
        try:
            try:
                try:
                    if self.app is None:
                        raise cherrypy.NotFound()
                    
                    # Get the 'Host' header, so we can HTTPRedirect properly.
                    self.stage = 'process_headers'
                    self.process_headers()
                    
                    # Make a copy of the class hooks
                    self.hooks = self.__class__.hooks.copy()
                    self.toolmaps = {}
                    
                    self.stage = 'get_resource'
                    self.get_resource(path_info)
                    
                    self.body = _cpreqbody.RequestBody(
                        self.rfile, self.headers, request_params=self.params)
                    
                    self.namespaces(self.config)
                    
                    self.stage = 'on_start_resource'
                    self.hooks.run('on_start_resource')
                    
                    # Parse the querystring
                    self.stage = 'process_query_string'
                    self.process_query_string()
                    
                    # Process the body
                    if self.process_request_body:
                        if self.method not in self.methods_with_bodies:
                            self.process_request_body = False
                    self.stage = 'before_request_body'
                    self.hooks.run('before_request_body')
                    if self.process_request_body:
                        self.body.process()
                    
                    # Run the handler
                    self.stage = 'before_handler'
                    self.hooks.run('before_handler')
                    if self.handler:
                        self.stage = 'handler'
                        response.body = self.handler()
                    
                    # Finalize
                    self.stage = 'before_finalize'
                    self.hooks.run('before_finalize')
                    response.finalize()
                except (cherrypy.HTTPRedirect, cherrypy.HTTPError):
                    inst = sys.exc_info()[1]
                    inst.set_response()
                    self.stage = 'before_finalize (HTTPError)'
                    self.hooks.run('before_finalize')
                    response.finalize()
            finally:
                self.stage = 'on_end_resource'
                self.hooks.run('on_end_resource')
        except self.throws:
            raise
        except:
            if self.throw_errors:
                raise
            self.handle_error()
    
    def process_query_string(self):
        """Parse the query string into Python structures. (Core)"""
        try:
            p = httputil.parse_query_string(
                self.query_string, encoding=self.query_string_encoding)
        except UnicodeDecodeError:
            raise cherrypy.HTTPError(
                404, "The given query string could not be processed. Query "
                "strings for this resource must be encoded with %r." %
                self.query_string_encoding)
        
        # Python 2 only: keyword arguments must be byte strings (type 'str').
        if not py3k:
            for key, value in p.items():
                if isinstance(key, unicode):
                    del p[key]
                    p[key.encode(self.query_string_encoding)] = value
        self.params.update(p)
    
    def process_headers(self):
        """Parse HTTP header data into Python structures. (Core)"""
        # Process the headers into self.headers
        headers = self.headers
        for name, value in self.header_list:
            # Call title() now (and use dict.__method__(headers))
            # so title doesn't have to be called twice.
            name = name.title()
            value = value.strip()
            
            # Warning: if there is more than one header entry for cookies (AFAIK,
            # only Konqueror does that), only the last one will remain in headers
            # (but they will be correctly stored in request.cookie).
            if "=?" in value:
                dict.__setitem__(headers, name, httputil.decode_TEXT(value))
            else:
                dict.__setitem__(headers, name, value)
            
            # Handle cookies differently because on Konqueror, multiple
            # cookies come on different lines with the same key
            if name == 'Cookie':
                try:
                    self.cookie.load(value)
                except CookieError:
                    msg = "Illegal cookie name %s" % value.split('=')[0]
                    raise cherrypy.HTTPError(400, msg)
        
        if not dict.__contains__(headers, 'Host'):
            # All Internet-based HTTP/1.1 servers MUST respond with a 400
            # (Bad Request) status code to any HTTP/1.1 request message
            # which lacks a Host header field.
            if self.protocol >= (1, 1):
                msg = "HTTP/1.1 requires a 'Host' request header."
                raise cherrypy.HTTPError(400, msg)
        host = dict.get(headers, 'Host')
        if not host:
            host = self.local.name or self.local.ip
        self.base = "%s://%s" % (self.scheme, host)
    
    def get_resource(self, path):
        """Call a dispatcher (which sets self.handler and .config). (Core)"""
        # First, see if there is a custom dispatch at this URI. Custom
        # dispatchers can only be specified in app.config, not in _cp_config
        # (since custom dispatchers may not even have an app.root).
        dispatch = self.app.find_config(path, "request.dispatch", self.dispatch)
        
        # dispatch() should set self.handler and self.config
        dispatch(path)
    
    def handle_error(self):
        """Handle the last unanticipated exception. (Core)"""
        try:
            self.hooks.run("before_error_response")
            if self.error_response:
                self.error_response()
            self.hooks.run("after_error_response")
            cherrypy.serving.response.finalize()
        except cherrypy.HTTPRedirect:
            inst = sys.exc_info()[1]
            inst.set_response()
            cherrypy.serving.response.finalize()
    
    # ------------------------- Properties ------------------------- #
    
    def _get_body_params(self):
        warnings.warn(
                "body_params is deprecated in CherryPy 3.2, will be removed in "
                "CherryPy 3.3.",
                DeprecationWarning
            )
        return self.body.params
    body_params = property(_get_body_params,
                      doc= """
    If the request Content-Type is 'application/x-www-form-urlencoded' or
    multipart, this will be a dict of the params pulled from the entity
    body; that is, it will be the portion of request.params that come
    from the message body (sometimes called "POST params", although they
    can be sent with various HTTP method verbs). This value is set between
    the 'before_request_body' and 'before_handler' hooks (assuming that
    process_request_body is True).
    
    Deprecated in 3.2, will be removed for 3.3 in favor of
    :attr:`request.body.params<cherrypy._cprequest.RequestBody.params>`.""")


class ResponseBody(object):
    """The body of the HTTP response (the response entity)."""
    
    if py3k:
        unicode_err = ("Page handlers MUST return bytes. Use tools.encode "
                       "if you wish to return unicode.")
    
    def __get__(self, obj, objclass=None):
        if obj is None:
            # When calling on the class instead of an instance...
            return self
        else:
            return obj._body
    
    def __set__(self, obj, value):
        # Convert the given value to an iterable object.
        if py3k and isinstance(value, str):
            raise ValueError(self.unicode_err)
        
        if isinstance(value, basestring):
            # strings get wrapped in a list because iterating over a single
            # item list is much faster than iterating over every character
            # in a long string.
            if value:
                value = [value]
            else:
                # [''] doesn't evaluate to False, so replace it with [].
                value = []
        elif py3k and isinstance(value, list):
            # every item in a list must be bytes... 
            for i, item in enumerate(value):
                if isinstance(item, str):
                    raise ValueError(self.unicode_err)
        # Don't use isinstance here; io.IOBase which has an ABC takes
        # 1000 times as long as, say, isinstance(value, str)
        elif hasattr(value, 'read'):
            value = file_generator(value)
        elif value is None:
            value = []
        obj._body = value


class Response(object):
    """An HTTP Response, including status, headers, and body."""
    
    status = ""
    """The HTTP Status-Code and Reason-Phrase."""
    
    header_list = []
    """
    A list of the HTTP response headers as (name, value) tuples.
    In general, you should use response.headers (a dict) instead. This
    attribute is generated from response.headers and is not valid until
    after the finalize phase."""
    
    headers = httputil.HeaderMap()
    """
    A dict-like object containing the response headers. Keys are header
    names (in Title-Case format); however, you may get and set them in
    a case-insensitive manner. That is, headers['Content-Type'] and
    headers['content-type'] refer to the same value. Values are header
    values (decoded according to :rfc:`2047` if necessary).
    
    .. seealso:: classes :class:`HeaderMap`, :class:`HeaderElement`
    """
    
    cookie = SimpleCookie()
    """See help(Cookie)."""
    
    body = ResponseBody()
    """The body (entity) of the HTTP response."""
    
    time = None
    """The value of time.time() when created. Use in HTTP dates."""
    
    timeout = 300
    """Seconds after which the response will be aborted."""
    
    timed_out = False
    """
    Flag to indicate the response should be aborted, because it has
    exceeded its timeout."""
    
    stream = False
    """If False, buffer the response body."""
    
    def __init__(self):
        self.status = None
        self.header_list = None
        self._body = []
        self.time = time.time()
        
        self.headers = httputil.HeaderMap()
        # Since we know all our keys are titled strings, we can
        # bypass HeaderMap.update and get a big speed boost.
        dict.update(self.headers, {
            "Content-Type": 'text/html',
            "Server": "CherryPy/" + cherrypy.__version__,
            "Date": httputil.HTTPDate(self.time),
        })
        self.cookie = SimpleCookie()
    
    def collapse_body(self):
        """Collapse self.body to a single string; replace it and return it."""
        if isinstance(self.body, basestring):
            return self.body
        
        newbody = []
        for chunk in self.body:
            if py3k and not isinstance(chunk, bytes):
                raise TypeError("Chunk %s is not of type 'bytes'." % repr(chunk))
            newbody.append(chunk)
        newbody = ntob('').join(newbody)
        
        self.body = newbody
        return newbody
    
    def finalize(self):
        """Transform headers (and cookies) into self.header_list. (Core)"""
        try:
            code, reason, _ = httputil.valid_status(self.status)
        except ValueError:
            raise cherrypy.HTTPError(500, sys.exc_info()[1].args[0])
        
        headers = self.headers
        
        self.status = "%s %s" % (code, reason)
        self.output_status = ntob(str(code), 'ascii') + ntob(" ") + headers.encode(reason)
        
        if self.stream:
            # The upshot: wsgiserver will chunk the response if
            # you pop Content-Length (or set it explicitly to None).
            # Note that lib.static sets C-L to the file's st_size.
            if dict.get(headers, 'Content-Length') is None:
                dict.pop(headers, 'Content-Length', None)
        elif code < 200 or code in (204, 205, 304):
            # "All 1xx (informational), 204 (no content),
            # and 304 (not modified) responses MUST NOT
            # include a message-body."
            dict.pop(headers, 'Content-Length', None)
            self.body = ntob("")
        else:
            # Responses which are not streamed should have a Content-Length,
            # but allow user code to set Content-Length if desired.
            if dict.get(headers, 'Content-Length') is None:
                content = self.collapse_body()
                dict.__setitem__(headers, 'Content-Length', len(content))
        
        # Transform our header dict into a list of tuples.
        self.header_list = h = headers.output()
        
        cookie = self.cookie.output()
        if cookie:
            for line in cookie.split("\n"):
                if line.endswith("\r"):
                    # Python 2.4 emits cookies joined by LF but 2.5+ by CRLF.
                    line = line[:-1]
                name, value = line.split(": ", 1)
                if isinstance(name, unicodestr):
                    name = name.encode("ISO-8859-1")
                if isinstance(value, unicodestr):
                    value = headers.encode(value)
                h.append((name, value))
    
    def check_timeout(self):
        """If now > self.time + self.timeout, set self.timed_out.
        
        This purposefully sets a flag, rather than raising an error,
        so that a monitor thread can interrupt the Response thread.
        """
        if time.time() > self.time + self.timeout:
            self.timed_out = True



