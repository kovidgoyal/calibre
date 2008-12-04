"""CherryPy Application and Tree objects."""

import os
import cherrypy
from cherrypy import _cpconfig, _cplogging, _cprequest, _cpwsgi, tools
from cherrypy.lib import http as _http


class Application(object):
    """A CherryPy Application.
    
    Servers and gateways should not instantiate Request objects directly.
    Instead, they should ask an Application object for a request object.
    
    An instance of this class may also be used as a WSGI callable
    (WSGI application object) for itself.
    """
    
    __metaclass__ = cherrypy._AttributeDocstrings
    
    root = None
    root__doc = """
    The top-most container of page handlers for this app. Handlers should
    be arranged in a hierarchy of attributes, matching the expected URI
    hierarchy; the default dispatcher then searches this hierarchy for a
    matching handler. When using a dispatcher other than the default,
    this value may be None."""
    
    config = {}
    config__doc = """
    A dict of {path: pathconf} pairs, where 'pathconf' is itself a dict
    of {key: value} pairs."""
    
    namespaces = _cpconfig.NamespaceSet()
    toolboxes = {'tools': cherrypy.tools}
    
    log = None
    log__doc = """A LogManager instance. See _cplogging."""
    
    wsgiapp = None
    wsgiapp__doc = """A CPWSGIApp instance. See _cpwsgi."""
    
    request_class = _cprequest.Request
    response_class = _cprequest.Response
    
    relative_urls = False
    
    def __init__(self, root, script_name="", config=None):
        self.log = _cplogging.LogManager(id(self), cherrypy.log.logger_root)
        self.root = root
        self.script_name = script_name
        self.wsgiapp = _cpwsgi.CPWSGIApp(self)
        
        self.namespaces = self.namespaces.copy()
        self.namespaces["log"] = lambda k, v: setattr(self.log, k, v)
        self.namespaces["wsgi"] = self.wsgiapp.namespace_handler
        
        self.config = self.__class__.config.copy()
        if config:
            self.merge(config)
    
    def __repr__(self):
        return "%s.%s(%r, %r)" % (self.__module__, self.__class__.__name__,
                                  self.root, self.script_name)
    
    script_name__doc = """
    The URI "mount point" for this app. A mount point is that portion of
    the URI which is constant for all URIs that are serviced by this
    application; it does not include scheme, host, or proxy ("virtual host")
    portions of the URI.
    
    For example, if script_name is "/my/cool/app", then the URL
    "http://www.example.com/my/cool/app/page1" might be handled by a
    "page1" method on the root object.
    
    The value of script_name MUST NOT end in a slash. If the script_name
    refers to the root of the URI, it MUST be an empty string (not "/").
    
    If script_name is explicitly set to None, then the script_name will be
    provided for each call from request.wsgi_environ['SCRIPT_NAME'].
    """
    def _get_script_name(self):
        if self._script_name is None:
            # None signals that the script name should be pulled from WSGI environ.
            return cherrypy.request.wsgi_environ['SCRIPT_NAME'].rstrip("/")
        return self._script_name
    def _set_script_name(self, value):
        if value:
            value = value.rstrip("/")
        self._script_name = value
    script_name = property(fget=_get_script_name, fset=_set_script_name,
                           doc=script_name__doc)
    
    def merge(self, config):
        """Merge the given config into self.config."""
        _cpconfig.merge(self.config, config)
        
        # Handle namespaces specified in config.
        self.namespaces(self.config.get("/", {}))
    
    def get_serving(self, local, remote, scheme, sproto):
        """Create and return a Request and Response object."""
        req = self.request_class(local, remote, scheme, sproto)
        req.app = self
        
        for name, toolbox in self.toolboxes.iteritems():
            req.namespaces[name] = toolbox
        
        resp = self.response_class()
        cherrypy.serving.load(req, resp)
        cherrypy.engine.timeout_monitor.acquire()
        cherrypy.engine.publish('acquire_thread')
        
        return req, resp
    
    def release_serving(self):
        """Release the current serving (request and response)."""
        req = cherrypy.serving.request
        
        cherrypy.engine.timeout_monitor.release()
        
        try:
            req.close()
        except:
            cherrypy.log(traceback=True, severity=40)
        
        cherrypy.serving.clear()
    
    def __call__(self, environ, start_response):
        return self.wsgiapp(environ, start_response)


class Tree(object):
    """A registry of CherryPy applications, mounted at diverse points.
    
    An instance of this class may also be used as a WSGI callable
    (WSGI application object), in which case it dispatches to all
    mounted apps.
    """
    
    apps = {}
    apps__doc = """
    A dict of the form {script name: application}, where "script name"
    is a string declaring the URI mount point (no trailing slash), and
    "application" is an instance of cherrypy.Application (or an arbitrary
    WSGI callable if you happen to be using a WSGI server)."""
    
    def __init__(self):
        self.apps = {}
    
    def mount(self, root, script_name="", config=None):
        """Mount a new app from a root object, script_name, and config.
        
        root: an instance of a "controller class" (a collection of page
            handler methods) which represents the root of the application.
            This may also be an Application instance, or None if using
            a dispatcher other than the default.
        script_name: a string containing the "mount point" of the application.
            This should start with a slash, and be the path portion of the
            URL at which to mount the given root. For example, if root.index()
            will handle requests to "http://www.example.com:8080/dept/app1/",
            then the script_name argument would be "/dept/app1".
            
            It MUST NOT end in a slash. If the script_name refers to the
            root of the URI, it MUST be an empty string (not "/").
        config: a file or dict containing application config.
        """
        # Next line both 1) strips trailing slash and 2) maps "/" -> "".
        script_name = script_name.rstrip("/")
        
        if isinstance(root, Application):
            app = root
            if script_name != "" and script_name != app.script_name:
                raise ValueError, "Cannot specify a different script name and pass an Application instance to cherrypy.mount"
            script_name = app.script_name
        else:
            app = Application(root, script_name)
            
            # If mounted at "", add favicon.ico
            if (script_name == "" and root is not None
                    and not hasattr(root, "favicon_ico")):
                favicon = os.path.join(os.getcwd(), os.path.dirname(__file__),
                                       "favicon.ico")
                root.favicon_ico = tools.staticfile.handler(favicon)
        
        if config:
            app.merge(config)
        
        self.apps[script_name] = app
        
        return app
    
    def graft(self, wsgi_callable, script_name=""):
        """Mount a wsgi callable at the given script_name."""
        # Next line both 1) strips trailing slash and 2) maps "/" -> "".
        script_name = script_name.rstrip("/")
        self.apps[script_name] = wsgi_callable
    
    def script_name(self, path=None):
        """The script_name of the app at the given path, or None.
        
        If path is None, cherrypy.request is used.
        """
        
        if path is None:
            try:
                path = _http.urljoin(cherrypy.request.script_name,
                                     cherrypy.request.path_info)
            except AttributeError:
                return None
        
        while True:
            if path in self.apps:
                return path
            
            if path == "":
                return None
            
            # Move one node up the tree and try again.
            path = path[:path.rfind("/")]
    
    def __call__(self, environ, start_response):
        # If you're calling this, then you're probably setting SCRIPT_NAME
        # to '' (some WSGI servers always set SCRIPT_NAME to '').
        # Try to look up the app using the full path.
        path = _http.urljoin(environ.get('SCRIPT_NAME', ''),
                             environ.get('PATH_INFO', ''))
        sn = self.script_name(path or "/")
        if sn is None:
            start_response('404 Not Found', [])
            return []
        
        app = self.apps[sn]
        
        # Correct the SCRIPT_NAME and PATH_INFO environ entries.
        environ = environ.copy()
        environ['SCRIPT_NAME'] = sn
        environ['PATH_INFO'] = path[len(sn.rstrip("/")):]
        return app(environ, start_response)

