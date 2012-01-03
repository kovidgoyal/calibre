"""CherryPy Application and Tree objects."""

import os
import sys

import cherrypy
from cherrypy._cpcompat import ntou, py3k
from cherrypy import _cpconfig, _cplogging, _cprequest, _cpwsgi, tools
from cherrypy.lib import httputil


class Application(object):
    """A CherryPy Application.
    
    Servers and gateways should not instantiate Request objects directly.
    Instead, they should ask an Application object for a request object.
    
    An instance of this class may also be used as a WSGI callable
    (WSGI application object) for itself.
    """
    
    root = None
    """The top-most container of page handlers for this app. Handlers should
    be arranged in a hierarchy of attributes, matching the expected URI
    hierarchy; the default dispatcher then searches this hierarchy for a
    matching handler. When using a dispatcher other than the default,
    this value may be None."""
    
    config = {}
    """A dict of {path: pathconf} pairs, where 'pathconf' is itself a dict
    of {key: value} pairs."""
    
    namespaces = _cpconfig.NamespaceSet()
    toolboxes = {'tools': cherrypy.tools}
    
    log = None
    """A LogManager instance. See _cplogging."""
    
    wsgiapp = None
    """A CPWSGIApp instance. See _cpwsgi."""
    
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
    
    script_name_doc = """The URI "mount point" for this app. A mount point is that portion of
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
            return cherrypy.serving.request.wsgi_environ['SCRIPT_NAME'].rstrip("/")
        return self._script_name
    def _set_script_name(self, value):
        if value:
            value = value.rstrip("/")
        self._script_name = value
    script_name = property(fget=_get_script_name, fset=_set_script_name,
                           doc=script_name_doc)
    
    def merge(self, config):
        """Merge the given config into self.config."""
        _cpconfig.merge(self.config, config)
        
        # Handle namespaces specified in config.
        self.namespaces(self.config.get("/", {}))
    
    def find_config(self, path, key, default=None):
        """Return the most-specific value for key along path, or default."""
        trail = path or "/"
        while trail:
            nodeconf = self.config.get(trail, {})
            
            if key in nodeconf:
                return nodeconf[key]
            
            lastslash = trail.rfind("/")
            if lastslash == -1:
                break
            elif lastslash == 0 and trail != "/":
                trail = "/"
            else:
                trail = trail[:lastslash]
        
        return default
    
    def get_serving(self, local, remote, scheme, sproto):
        """Create and return a Request and Response object."""
        req = self.request_class(local, remote, scheme, sproto)
        req.app = self
        
        for name, toolbox in self.toolboxes.items():
            req.namespaces[name] = toolbox
        
        resp = self.response_class()
        cherrypy.serving.load(req, resp)
        cherrypy.engine.publish('acquire_thread')
        cherrypy.engine.publish('before_request')
        
        return req, resp
    
    def release_serving(self):
        """Release the current serving (request and response)."""
        req = cherrypy.serving.request
        
        cherrypy.engine.publish('after_request')
        
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
    """
    A dict of the form {script name: application}, where "script name"
    is a string declaring the URI mount point (no trailing slash), and
    "application" is an instance of cherrypy.Application (or an arbitrary
    WSGI callable if you happen to be using a WSGI server)."""
    
    def __init__(self):
        self.apps = {}
    
    def mount(self, root, script_name="", config=None):
        """Mount a new app from a root object, script_name, and config.
        
        root
            An instance of a "controller class" (a collection of page
            handler methods) which represents the root of the application.
            This may also be an Application instance, or None if using
            a dispatcher other than the default.
        
        script_name
            A string containing the "mount point" of the application.
            This should start with a slash, and be the path portion of the
            URL at which to mount the given root. For example, if root.index()
            will handle requests to "http://www.example.com:8080/dept/app1/",
            then the script_name argument would be "/dept/app1".
            
            It MUST NOT end in a slash. If the script_name refers to the
            root of the URI, it MUST be an empty string (not "/").
        
        config
            A file or dict containing application config.
        """
        if script_name is None:
            raise TypeError(
                "The 'script_name' argument may not be None. Application "
                "objects may, however, possess a script_name of None (in "
                "order to inpect the WSGI environ for SCRIPT_NAME upon each "
                "request). You cannot mount such Applications on this Tree; "
                "you must pass them to a WSGI server interface directly.")
        
        # Next line both 1) strips trailing slash and 2) maps "/" -> "".
        script_name = script_name.rstrip("/")
        
        if isinstance(root, Application):
            app = root
            if script_name != "" and script_name != app.script_name:
                raise ValueError("Cannot specify a different script name and "
                                 "pass an Application instance to cherrypy.mount")
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
                request = cherrypy.serving.request
                path = httputil.urljoin(request.script_name,
                                        request.path_info)
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
        env1x = environ
        if environ.get(ntou('wsgi.version')) == (ntou('u'), 0):
            env1x = _cpwsgi.downgrade_wsgi_ux_to_1x(environ)
        path = httputil.urljoin(env1x.get('SCRIPT_NAME', ''),
                                env1x.get('PATH_INFO', ''))
        sn = self.script_name(path or "/")
        if sn is None:
            start_response('404 Not Found', [])
            return []
        
        app = self.apps[sn]
        
        # Correct the SCRIPT_NAME and PATH_INFO environ entries.
        environ = environ.copy()
        if not py3k:
            if environ.get(ntou('wsgi.version')) == (ntou('u'), 0):
                # Python 2/WSGI u.0: all strings MUST be of type unicode
                enc = environ[ntou('wsgi.url_encoding')]
                environ[ntou('SCRIPT_NAME')] = sn.decode(enc)
                environ[ntou('PATH_INFO')] = path[len(sn.rstrip("/")):].decode(enc)
            else:
                # Python 2/WSGI 1.x: all strings MUST be of type str
                environ['SCRIPT_NAME'] = sn
                environ['PATH_INFO'] = path[len(sn.rstrip("/")):]
        else:
            if environ.get(ntou('wsgi.version')) == (ntou('u'), 0):
                # Python 3/WSGI u.0: all strings MUST be full unicode
                environ['SCRIPT_NAME'] = sn
                environ['PATH_INFO'] = path[len(sn.rstrip("/")):]
            else:
                # Python 3/WSGI 1.x: all strings MUST be ISO-8859-1 str
                environ['SCRIPT_NAME'] = sn.encode('utf-8').decode('ISO-8859-1')
                environ['PATH_INFO'] = path[len(sn.rstrip("/")):].encode('utf-8').decode('ISO-8859-1')
        return app(environ, start_response)
