"""WSGI interface (see PEP 333)."""

import StringIO as _StringIO
import sys as _sys

import cherrypy as _cherrypy
from cherrypy import _cperror
from cherrypy.lib import http as _http


class VirtualHost(object):
    """Select a different WSGI application based on the Host header.
    
    This can be useful when running multiple sites within one CP server.
    It allows several domains to point to different applications. For example:
    
        root = Root()
        RootApp = cherrypy.Application(root)
        Domain2App = cherrypy.Application(root)
        SecureApp = cherrypy.Application(Secure())
        
        vhost = cherrypy._cpwsgi.VirtualHost(RootApp,
            domains={'www.domain2.example': Domain2App,
                     'www.domain2.example:443': SecureApp,
                     })
        
        cherrypy.tree.graft(vhost)
    
    default: required. The default WSGI application.
    
    use_x_forwarded_host: if True (the default), any "X-Forwarded-Host"
        request header will be used instead of the "Host" header. This
        is commonly added by HTTP servers (such as Apache) when proxying.
    
    domains: a dict of {host header value: application} pairs.
        The incoming "Host" request header is looked up in this dict,
        and, if a match is found, the corresponding WSGI application
        will be called instead of the default. Note that you often need
        separate entries for "example.com" and "www.example.com".
        In addition, "Host" headers may contain the port number.
    """
    
    def __init__(self, default, domains=None, use_x_forwarded_host=True):
        self.default = default
        self.domains = domains or {}
        self.use_x_forwarded_host = use_x_forwarded_host
    
    def __call__(self, environ, start_response):
        domain = environ.get('HTTP_HOST', '')
        if self.use_x_forwarded_host:
            domain = environ.get("HTTP_X_FORWARDED_HOST", domain)
        
        nextapp = self.domains.get(domain)
        if nextapp is None:
            nextapp = self.default
        return nextapp(environ, start_response)



#                           WSGI-to-CP Adapter                           #


class AppResponse(object):
    
    throws = (KeyboardInterrupt, SystemExit)
    request = None
    
    def __init__(self, environ, start_response, cpapp, recursive=False):
        self.redirections = []
        self.recursive = recursive
        self.environ = environ
        self.start_response = start_response
        self.cpapp = cpapp
        self.setapp()
    
    def setapp(self):
        try:
            self.request = self.get_request()
            s, h, b = self.get_response()
            self.iter_response = iter(b)
            self.start_response(s, h)
        except self.throws:
            self.close()
            raise
        except _cherrypy.InternalRedirect, ir:
            self.environ['cherrypy.previous_request'] = _cherrypy.serving.request
            self.close()
            self.iredirect(ir.path, ir.query_string)
            return
        except:
            if getattr(self.request, "throw_errors", False):
                self.close()
                raise
            
            tb = _cperror.format_exc()
            _cherrypy.log(tb, severity=40)
            if not getattr(self.request, "show_tracebacks", True):
                tb = ""
            s, h, b = _cperror.bare_error(tb)
            self.iter_response = iter(b)
            
            try:
                self.start_response(s, h, _sys.exc_info())
            except:
                # "The application must not trap any exceptions raised by
                # start_response, if it called start_response with exc_info.
                # Instead, it should allow such exceptions to propagate
                # back to the server or gateway."
                # But we still log and call close() to clean up ourselves.
                _cherrypy.log(traceback=True, severity=40)
                self.close()
                raise
    
    def iredirect(self, path, query_string):
        """Doctor self.environ and perform an internal redirect.
        
        When cherrypy.InternalRedirect is raised, this method is called.
        It rewrites the WSGI environ using the new path and query_string,
        and calls a new CherryPy Request object. Because the wsgi.input
        stream may have already been consumed by the next application,
        the redirected call will always be of HTTP method "GET"; therefore,
        any params must be passed in the query_string argument, which is
        formed from InternalRedirect.query_string when using that exception.
        If you need something more complicated, make and raise your own
        exception and write your own AppResponse subclass to trap it. ;)
        
        It would be a bad idea to redirect after you've already yielded
        response content, although an enterprising soul could choose
        to abuse this.
        """
        env = self.environ
        if not self.recursive:
            sn = env.get('SCRIPT_NAME', '')
            qs = query_string
            if qs:
                qs = "?" + qs
            if sn + path + qs in self.redirections:
                raise RuntimeError("InternalRedirector visited the "
                                   "same URL twice: %r + %r + %r" %
                                   (sn, path, qs))
            else:
                # Add the *previous* path_info + qs to redirections.
                p = env.get('PATH_INFO', '')
                qs = env.get('QUERY_STRING', '')
                if qs:
                    qs = "?" + qs
                self.redirections.append(sn + p + qs)
        
        # Munge environment and try again.
        env['REQUEST_METHOD'] = "GET"
        env['PATH_INFO'] = path
        env['QUERY_STRING'] = query_string
        env['wsgi.input'] = _StringIO.StringIO()
        env['CONTENT_LENGTH'] = "0"
        
        self.setapp()
    
    def __iter__(self):
        return self
    
    def next(self):
        try:
            chunk = self.iter_response.next()
            # WSGI requires all data to be of type "str". This coercion should
            # not take any time at all if chunk is already of type "str".
            # If it's unicode, it could be a big performance hit (x ~500).
            if not isinstance(chunk, str):
                chunk = chunk.encode("ISO-8859-1")
            return chunk
        except self.throws:
            self.close()
            raise
        except _cherrypy.InternalRedirect, ir:
            self.environ['cherrypy.previous_request'] = _cherrypy.serving.request
            self.close()
            self.iredirect(ir.path, ir.query_string)
        except StopIteration:
            raise
        except:
            if getattr(self.request, "throw_errors", False):
                self.close()
                raise
            
            tb = _cperror.format_exc()
            _cherrypy.log(tb, severity=40)
            if not getattr(self.request, "show_tracebacks", True):
                tb = ""
            s, h, b = _cperror.bare_error(tb)
            # Empty our iterable (so future calls raise StopIteration)
            self.iter_response = iter([])
            
            try:
                self.start_response(s, h, _sys.exc_info())
            except:
                # "The application must not trap any exceptions raised by
                # start_response, if it called start_response with exc_info.
                # Instead, it should allow such exceptions to propagate
                # back to the server or gateway."
                # But we still log and call close() to clean up ourselves.
                _cherrypy.log(traceback=True, severity=40)
                self.close()
                raise
            
            return "".join(b)
    
    def close(self):
        """Close and de-reference the current request and response. (Core)"""
        self.cpapp.release_serving()
    
    def get_response(self):
        """Run self.request and return its response."""
        meth = self.environ['REQUEST_METHOD']
        path = _http.urljoin(self.environ.get('SCRIPT_NAME', ''),
                             self.environ.get('PATH_INFO', ''))
        qs = self.environ.get('QUERY_STRING', '')
        rproto = self.environ.get('SERVER_PROTOCOL')
        headers = self.translate_headers(self.environ)
        rfile = self.environ['wsgi.input']
        response = self.request.run(meth, path, qs, rproto, headers, rfile)
        return response.status, response.header_list, response.body
    
    def get_request(self):
        """Create a Request object using environ."""
        env = self.environ.get
        
        local = _http.Host('', int(env('SERVER_PORT', 80)),
                           env('SERVER_NAME', ''))
        remote = _http.Host(env('REMOTE_ADDR', ''),
                            int(env('REMOTE_PORT', -1)),
                            env('REMOTE_HOST', ''))
        scheme = env('wsgi.url_scheme')
        sproto = env('ACTUAL_SERVER_PROTOCOL', "HTTP/1.1")
        request, resp = self.cpapp.get_serving(local, remote, scheme, sproto)
        
        # LOGON_USER is served by IIS, and is the name of the
        # user after having been mapped to a local account.
        # Both IIS and Apache set REMOTE_USER, when possible.
        request.login = env('LOGON_USER') or env('REMOTE_USER') or None
        request.multithread = self.environ['wsgi.multithread']
        request.multiprocess = self.environ['wsgi.multiprocess']
        request.wsgi_environ = self.environ
        request.prev = env('cherrypy.previous_request', None)
        return request
    
    headerNames = {'HTTP_CGI_AUTHORIZATION': 'Authorization',
                   'CONTENT_LENGTH': 'Content-Length',
                   'CONTENT_TYPE': 'Content-Type',
                   'REMOTE_HOST': 'Remote-Host',
                   'REMOTE_ADDR': 'Remote-Addr',
                   }
    
    def translate_headers(self, environ):
        """Translate CGI-environ header names to HTTP header names."""
        for cgiName in environ:
            # We assume all incoming header keys are uppercase already.
            if cgiName in self.headerNames:
                yield self.headerNames[cgiName], environ[cgiName]
            elif cgiName[:5] == "HTTP_":
                # Hackish attempt at recovering original header names.
                translatedHeader = cgiName[5:].replace("_", "-")
                yield translatedHeader, environ[cgiName]


class CPWSGIApp(object):
    """A WSGI application object for a CherryPy Application.
    
    pipeline: a list of (name, wsgiapp) pairs. Each 'wsgiapp' MUST be a
        constructor that takes an initial, positional 'nextapp' argument,
        plus optional keyword arguments, and returns a WSGI application
        (that takes environ and start_response arguments). The 'name' can
        be any you choose, and will correspond to keys in self.config.
    
    head: rather than nest all apps in the pipeline on each call, it's only
        done the first time, and the result is memoized into self.head. Set
        this to None again if you change self.pipeline after calling self.
    
    config: a dict whose keys match names listed in the pipeline. Each
        value is a further dict which will be passed to the corresponding
        named WSGI callable (from the pipeline) as keyword arguments.
    """
    
    pipeline = []
    head = None
    config = {}
    
    response_class = AppResponse
    
    def __init__(self, cpapp, pipeline=None):
        self.cpapp = cpapp
        self.pipeline = self.pipeline[:]
        if pipeline:
            self.pipeline.extend(pipeline)
        self.config = self.config.copy()
    
    def tail(self, environ, start_response):
        """WSGI application callable for the actual CherryPy application.
        
        You probably shouldn't call this; call self.__call__ instead,
        so that any WSGI middleware in self.pipeline can run first.
        """
        return self.response_class(environ, start_response, self.cpapp)
    
    def __call__(self, environ, start_response):
        head = self.head
        if head is None:
            # Create and nest the WSGI apps in our pipeline (in reverse order).
            # Then memoize the result in self.head.
            head = self.tail
            for name, callable in self.pipeline[::-1]:
                conf = self.config.get(name, {})
                head = callable(head, **conf)
            self.head = head
        return head(environ, start_response)
    
    def namespace_handler(self, k, v):
        """Config handler for the 'wsgi' namespace."""
        if k == "pipeline":
            # Note this allows multiple 'wsgi.pipeline' config entries
            # (but each entry will be processed in a 'random' order).
            # It should also allow developers to set default middleware
            # in code (passed to self.__init__) that deployers can add to
            # (but not remove) via config.
            self.pipeline.extend(v)
        elif k == "response_class":
            self.response_class = v
        else:
            name, arg = k.split(".", 1)
            bucket = self.config.setdefault(name, {})
            bucket[arg] = v

