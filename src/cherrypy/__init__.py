"""CherryPy is a pythonic, object-oriented HTTP framework.


CherryPy consists of not one, but four separate API layers.

The APPLICATION LAYER is the simplest. CherryPy applications are written as
a tree of classes and methods, where each branch in the tree corresponds to
a branch in the URL path. Each method is a 'page handler', which receives
GET and POST params as keyword arguments, and returns or yields the (HTML)
body of the response. The special method name 'index' is used for paths
that end in a slash, and the special method name 'default' is used to
handle multiple paths via a single handler. This layer also includes:

 * the 'exposed' attribute (and cherrypy.expose)
 * cherrypy.quickstart()
 * _cp_config attributes
 * cherrypy.tools (including cherrypy.session)
 * cherrypy.url()

The ENVIRONMENT LAYER is used by developers at all levels. It provides
information about the current request and response, plus the application
and server environment, via a (default) set of top-level objects:

 * cherrypy.request
 * cherrypy.response
 * cherrypy.engine
 * cherrypy.server
 * cherrypy.tree
 * cherrypy.config
 * cherrypy.thread_data
 * cherrypy.log
 * cherrypy.HTTPError, NotFound, and HTTPRedirect
 * cherrypy.lib

The EXTENSION LAYER allows advanced users to construct and share their own
plugins. It consists of:

 * Hook API
 * Tool API
 * Toolbox API
 * Dispatch API
 * Config Namespace API

Finally, there is the CORE LAYER, which uses the core API's to construct
the default components which are available at higher layers. You can think
of the default components as the 'reference implementation' for CherryPy.
Megaframeworks (and advanced users) may replace the default components
with customized or extended components. The core API's are:

 * Application API
 * Engine API
 * Request API
 * Server API
 * WSGI API

These API's are described in the CherryPy specification:
http://www.cherrypy.org/wiki/CherryPySpec
"""

__version__ = "3.2.2"

from cherrypy._cpcompat import urljoin as _urljoin, urlencode as _urlencode
from cherrypy._cpcompat import basestring, unicodestr, set

from cherrypy._cperror import HTTPError, HTTPRedirect, InternalRedirect
from cherrypy._cperror import NotFound, CherryPyException, TimeoutError

from cherrypy import _cpdispatch as dispatch

from cherrypy import _cptools
tools = _cptools.default_toolbox
Tool = _cptools.Tool

from cherrypy import _cprequest
from cherrypy.lib import httputil as _httputil

from cherrypy import _cptree
tree = _cptree.Tree()
from cherrypy._cptree import Application
from cherrypy import _cpwsgi as wsgi

from cherrypy import process
try:
    from cherrypy.process import win32
    engine = win32.Win32Bus()
    engine.console_control_handler = win32.ConsoleCtrlHandler(engine)
    del win32
except ImportError:
    engine = process.bus


# Timeout monitor. We add two channels to the engine
# to which cherrypy.Application will publish.
engine.listeners['before_request'] = set()
engine.listeners['after_request'] = set()

class _TimeoutMonitor(process.plugins.Monitor):
    
    def __init__(self, bus):
        self.servings = []
        process.plugins.Monitor.__init__(self, bus, self.run)
    
    def before_request(self):
        self.servings.append((serving.request, serving.response))
    
    def after_request(self):
        try:
            self.servings.remove((serving.request, serving.response))
        except ValueError:
            pass
    
    def run(self):
        """Check timeout on all responses. (Internal)"""
        for req, resp in self.servings:
            resp.check_timeout()
engine.timeout_monitor = _TimeoutMonitor(engine)
engine.timeout_monitor.subscribe()

engine.autoreload = process.plugins.Autoreloader(engine)
engine.autoreload.subscribe()

engine.thread_manager = process.plugins.ThreadManager(engine)
engine.thread_manager.subscribe()

engine.signal_handler = process.plugins.SignalHandler(engine)


from cherrypy import _cpserver
server = _cpserver.Server()
server.subscribe()


def quickstart(root=None, script_name="", config=None):
    """Mount the given root, start the builtin server (and engine), then block.
    
    root: an instance of a "controller class" (a collection of page handler
        methods) which represents the root of the application.
    script_name: a string containing the "mount point" of the application.
        This should start with a slash, and be the path portion of the URL
        at which to mount the given root. For example, if root.index() will
        handle requests to "http://www.example.com:8080/dept/app1/", then
        the script_name argument would be "/dept/app1".
        
        It MUST NOT end in a slash. If the script_name refers to the root
        of the URI, it MUST be an empty string (not "/").
    config: a file or dict containing application config. If this contains
        a [global] section, those entries will be used in the global
        (site-wide) config.
    """
    if config:
        _global_conf_alias.update(config)
    
    tree.mount(root, script_name, config)
    
    if hasattr(engine, "signal_handler"):
        engine.signal_handler.subscribe()
    if hasattr(engine, "console_control_handler"):
        engine.console_control_handler.subscribe()
    
    engine.start()
    engine.block()


from cherrypy._cpcompat import threadlocal as _local

class _Serving(_local):
    """An interface for registering request and response objects.
    
    Rather than have a separate "thread local" object for the request and
    the response, this class works as a single threadlocal container for
    both objects (and any others which developers wish to define). In this
    way, we can easily dump those objects when we stop/start a new HTTP
    conversation, yet still refer to them as module-level globals in a
    thread-safe way.
    """
    
    request = _cprequest.Request(_httputil.Host("127.0.0.1", 80),
                                 _httputil.Host("127.0.0.1", 1111))
    """
    The request object for the current thread. In the main thread,
    and any threads which are not receiving HTTP requests, this is None."""
    
    response = _cprequest.Response()
    """
    The response object for the current thread. In the main thread,
    and any threads which are not receiving HTTP requests, this is None."""
    
    def load(self, request, response):
        self.request = request
        self.response = response
    
    def clear(self):
        """Remove all attributes of self."""
        self.__dict__.clear()

serving = _Serving()


class _ThreadLocalProxy(object):
    
    __slots__ = ['__attrname__', '__dict__']
    
    def __init__(self, attrname):
        self.__attrname__ = attrname
    
    def __getattr__(self, name):
        child = getattr(serving, self.__attrname__)
        return getattr(child, name)
    
    def __setattr__(self, name, value):
        if name in ("__attrname__", ):
            object.__setattr__(self, name, value)
        else:
            child = getattr(serving, self.__attrname__)
            setattr(child, name, value)
    
    def __delattr__(self, name):
        child = getattr(serving, self.__attrname__)
        delattr(child, name)
    
    def _get_dict(self):
        child = getattr(serving, self.__attrname__)
        d = child.__class__.__dict__.copy()
        d.update(child.__dict__)
        return d
    __dict__ = property(_get_dict)
    
    def __getitem__(self, key):
        child = getattr(serving, self.__attrname__)
        return child[key]
    
    def __setitem__(self, key, value):
        child = getattr(serving, self.__attrname__)
        child[key] = value
    
    def __delitem__(self, key):
        child = getattr(serving, self.__attrname__)
        del child[key]
    
    def __contains__(self, key):
        child = getattr(serving, self.__attrname__)
        return key in child
    
    def __len__(self):
        child = getattr(serving, self.__attrname__)
        return len(child)
    
    def __nonzero__(self):
        child = getattr(serving, self.__attrname__)
        return bool(child)
    # Python 3
    __bool__ = __nonzero__

# Create request and response object (the same objects will be used
#   throughout the entire life of the webserver, but will redirect
#   to the "serving" object)
request = _ThreadLocalProxy('request')
response = _ThreadLocalProxy('response')

# Create thread_data object as a thread-specific all-purpose storage
class _ThreadData(_local):
    """A container for thread-specific data."""
thread_data = _ThreadData()


# Monkeypatch pydoc to allow help() to go through the threadlocal proxy.
# Jan 2007: no Googleable examples of anyone else replacing pydoc.resolve.
# The only other way would be to change what is returned from type(request)
# and that's not possible in pure Python (you'd have to fake ob_type).
def _cherrypy_pydoc_resolve(thing, forceload=0):
    """Given an object or a path to an object, get the object and its name."""
    if isinstance(thing, _ThreadLocalProxy):
        thing = getattr(serving, thing.__attrname__)
    return _pydoc._builtin_resolve(thing, forceload)

try:
    import pydoc as _pydoc
    _pydoc._builtin_resolve = _pydoc.resolve
    _pydoc.resolve = _cherrypy_pydoc_resolve
except ImportError:
    pass


from cherrypy import _cplogging

class _GlobalLogManager(_cplogging.LogManager):
    """A site-wide LogManager; routes to app.log or global log as appropriate.
    
    This :class:`LogManager<cherrypy._cplogging.LogManager>` implements
    cherrypy.log() and cherrypy.log.access(). If either
    function is called during a request, the message will be sent to the
    logger for the current Application. If they are called outside of a
    request, the message will be sent to the site-wide logger.
    """
    
    def __call__(self, *args, **kwargs):
        """Log the given message to the app.log or global log as appropriate."""
        # Do NOT use try/except here. See http://www.cherrypy.org/ticket/945
        if hasattr(request, 'app') and hasattr(request.app, 'log'):
            log = request.app.log
        else:
            log = self
        return log.error(*args, **kwargs)
    
    def access(self):
        """Log an access message to the app.log or global log as appropriate."""
        try:
            return request.app.log.access()
        except AttributeError:
            return _cplogging.LogManager.access(self)


log = _GlobalLogManager()
# Set a default screen handler on the global log.
log.screen = True
log.error_file = ''
# Using an access file makes CP about 10% slower. Leave off by default.
log.access_file = ''

def _buslog(msg, level):
    log.error(msg, 'ENGINE', severity=level)
engine.subscribe('log', _buslog)

#                       Helper functions for CP apps                       #


def expose(func=None, alias=None):
    """Expose the function, optionally providing an alias or set of aliases."""
    def expose_(func):
        func.exposed = True
        if alias is not None:
            if isinstance(alias, basestring):
                parents[alias.replace(".", "_")] = func
            else:
                for a in alias:
                    parents[a.replace(".", "_")] = func
        return func
    
    import sys, types
    if isinstance(func, (types.FunctionType, types.MethodType)):
        if alias is None:
            # @expose
            func.exposed = True
            return func
        else:
            # func = expose(func, alias)
            parents = sys._getframe(1).f_locals
            return expose_(func)
    elif func is None:
        if alias is None:
            # @expose()
            parents = sys._getframe(1).f_locals
            return expose_
        else:
            # @expose(alias="alias") or
            # @expose(alias=["alias1", "alias2"])
            parents = sys._getframe(1).f_locals
            return expose_
    else:
        # @expose("alias") or
        # @expose(["alias1", "alias2"])
        parents = sys._getframe(1).f_locals
        alias = func
        return expose_

def popargs(*args, **kwargs):
    """A decorator for _cp_dispatch 
    (cherrypy.dispatch.Dispatcher.dispatch_method_name).

    Optional keyword argument: handler=(Object or Function)
    
    Provides a _cp_dispatch function that pops off path segments into 
    cherrypy.request.params under the names specified.  The dispatch
    is then forwarded on to the next vpath element.
    
    Note that any existing (and exposed) member function of the class that
    popargs is applied to will override that value of the argument.  For
    instance, if you have a method named "list" on the class decorated with
    popargs, then accessing "/list" will call that function instead of popping
    it off as the requested parameter.  This restriction applies to all 
    _cp_dispatch functions.  The only way around this restriction is to create
    a "blank class" whose only function is to provide _cp_dispatch.
    
    If there are path elements after the arguments, or more arguments
    are requested than are available in the vpath, then the 'handler'
    keyword argument specifies the next object to handle the parameterized
    request.  If handler is not specified or is None, then self is used.
    If handler is a function rather than an instance, then that function
    will be called with the args specified and the return value from that
    function used as the next object INSTEAD of adding the parameters to
    cherrypy.request.args.
    
    This decorator may be used in one of two ways:
    
    As a class decorator:
    @cherrypy.popargs('year', 'month', 'day')
    class Blog:
        def index(self, year=None, month=None, day=None):
            #Process the parameters here; any url like
            #/, /2009, /2009/12, or /2009/12/31
            #will fill in the appropriate parameters.
            
        def create(self):
            #This link will still be available at /create.  Defined functions
            #take precedence over arguments.
            
    Or as a member of a class:
    class Blog:
        _cp_dispatch = cherrypy.popargs('year', 'month', 'day')
        #...
        
    The handler argument may be used to mix arguments with built in functions.
    For instance, the following setup allows different activities at the
    day, month, and year level:
    
    class DayHandler:
        def index(self, year, month, day):
            #Do something with this day; probably list entries
            
        def delete(self, year, month, day):
            #Delete all entries for this day
            
    @cherrypy.popargs('day', handler=DayHandler())
    class MonthHandler:
        def index(self, year, month):
            #Do something with this month; probably list entries
            
        def delete(self, year, month):
            #Delete all entries for this month
            
    @cherrypy.popargs('month', handler=MonthHandler())
    class YearHandler:
        def index(self, year):
            #Do something with this year
            
        #...
        
    @cherrypy.popargs('year', handler=YearHandler())
    class Root:
        def index(self):
            #...
        
    """

    #Since keyword arg comes after *args, we have to process it ourselves
    #for lower versions of python.

    handler = None
    handler_call = False
    for k,v in kwargs.items():
        if k == 'handler':
            handler = v
        else:
            raise TypeError(
                "cherrypy.popargs() got an unexpected keyword argument '{0}'" \
                .format(k)
                )

    import inspect

    if handler is not None \
        and (hasattr(handler, '__call__') or inspect.isclass(handler)):
        handler_call = True
    
    def decorated(cls_or_self=None, vpath=None):
        if inspect.isclass(cls_or_self):
            #cherrypy.popargs is a class decorator
            cls = cls_or_self
            setattr(cls, dispatch.Dispatcher.dispatch_method_name, decorated)
            return cls
        
        #We're in the actual function
        self = cls_or_self
        parms = {}
        for arg in args:
            if not vpath:
                break
            parms[arg] = vpath.pop(0)
                
        if handler is not None:
            if handler_call:
                return handler(**parms)
            else:
                request.params.update(parms)
                return handler
                
        request.params.update(parms)
            
        #If we are the ultimate handler, then to prevent our _cp_dispatch
        #from being called again, we will resolve remaining elements through
        #getattr() directly.
        if vpath:
            return getattr(self, vpath.pop(0), None)
        else:
            return self
        
    return decorated

def url(path="", qs="", script_name=None, base=None, relative=None):
    """Create an absolute URL for the given path.
    
    If 'path' starts with a slash ('/'), this will return
        (base + script_name + path + qs).
    If it does not start with a slash, this returns
        (base + script_name [+ request.path_info] + path + qs).
    
    If script_name is None, cherrypy.request will be used
    to find a script_name, if available.
    
    If base is None, cherrypy.request.base will be used (if available).
    Note that you can use cherrypy.tools.proxy to change this.
    
    Finally, note that this function can be used to obtain an absolute URL
    for the current request path (minus the querystring) by passing no args.
    If you call url(qs=cherrypy.request.query_string), you should get the
    original browser URL (assuming no internal redirections).
    
    If relative is None or not provided, request.app.relative_urls will
    be used (if available, else False). If False, the output will be an
    absolute URL (including the scheme, host, vhost, and script_name).
    If True, the output will instead be a URL that is relative to the
    current request path, perhaps including '..' atoms. If relative is
    the string 'server', the output will instead be a URL that is
    relative to the server root; i.e., it will start with a slash.
    """
    if isinstance(qs, (tuple, list, dict)):
        qs = _urlencode(qs)
    if qs:
        qs = '?' + qs
    
    if request.app:
        if not path.startswith("/"):
            # Append/remove trailing slash from path_info as needed
            # (this is to support mistyped URL's without redirecting;
            # if you want to redirect, use tools.trailing_slash).
            pi = request.path_info
            if request.is_index is True:
                if not pi.endswith('/'):
                    pi = pi + '/'
            elif request.is_index is False:
                if pi.endswith('/') and pi != '/':
                    pi = pi[:-1]
            
            if path == "":
                path = pi
            else:
                path = _urljoin(pi, path)
        
        if script_name is None:
            script_name = request.script_name
        if base is None:
            base = request.base
        
        newurl = base + script_name + path + qs
    else:
        # No request.app (we're being called outside a request).
        # We'll have to guess the base from server.* attributes.
        # This will produce very different results from the above
        # if you're using vhosts or tools.proxy.
        if base is None:
            base = server.base()
        
        path = (script_name or "") + path
        newurl = base + path + qs
    
    if './' in newurl:
        # Normalize the URL by removing ./ and ../
        atoms = []
        for atom in newurl.split('/'):
            if atom == '.':
                pass
            elif atom == '..':
                atoms.pop()
            else:
                atoms.append(atom)
        newurl = '/'.join(atoms)
    
    # At this point, we should have a fully-qualified absolute URL.
    
    if relative is None:
        relative = getattr(request.app, "relative_urls", False)
    
    # See http://www.ietf.org/rfc/rfc2396.txt
    if relative == 'server':
        # "A relative reference beginning with a single slash character is
        # termed an absolute-path reference, as defined by <abs_path>..."
        # This is also sometimes called "server-relative".
        newurl = '/' + '/'.join(newurl.split('/', 3)[3:])
    elif relative:
        # "A relative reference that does not begin with a scheme name
        # or a slash character is termed a relative-path reference."
        old = url(relative=False).split('/')[:-1]
        new = newurl.split('/')
        while old and new:
            a, b = old[0], new[0]
            if a != b:
                break
            old.pop(0)
            new.pop(0)
        new = (['..'] * len(old)) + new
        newurl = '/'.join(new)
    
    return newurl


# import _cpconfig last so it can reference other top-level objects
from cherrypy import _cpconfig
# Use _global_conf_alias so quickstart can use 'config' as an arg
# without shadowing cherrypy.config.
config = _global_conf_alias = _cpconfig.Config()
config.defaults = {
    'tools.log_tracebacks.on': True,
    'tools.log_headers.on': True,
    'tools.trailing_slash.on': True,
    'tools.encode.on': True
    }
config.namespaces["log"] = lambda k, v: setattr(log, k, v)
config.namespaces["checker"] = lambda k, v: setattr(checker, k, v)
# Must reset to get our defaults applied.
config.reset()

from cherrypy import _cpchecker
checker = _cpchecker.Checker()
engine.subscribe('start', checker)
