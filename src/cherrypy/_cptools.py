"""CherryPy tools. A "tool" is any helper, adapted to CP.

Tools are usually designed to be used in a variety of ways (although some
may only offer one if they choose):
    
    Library calls
        All tools are callables that can be used wherever needed.
        The arguments are straightforward and should be detailed within the
        docstring.
    
    Function decorators
        All tools, when called, may be used as decorators which configure
        individual CherryPy page handlers (methods on the CherryPy tree).
        That is, "@tools.anytool()" should "turn on" the tool via the
        decorated function's _cp_config attribute.
    
    CherryPy config
        If a tool exposes a "_setup" callable, it will be called
        once per Request (if the feature is "turned on" via config).

Tools may be implemented as any object with a namespace. The builtins
are generally either modules or instances of the tools.Tool class.
"""

import sys
import warnings

import cherrypy


def _getargs(func):
    """Return the names of all static arguments to the given function."""
    # Use this instead of importing inspect for less mem overhead.
    import types
    if sys.version_info >= (3, 0):
        if isinstance(func, types.MethodType):
            func = func.__func__
        co = func.__code__
    else:
        if isinstance(func, types.MethodType):
            func = func.im_func
        co = func.func_code
    return co.co_varnames[:co.co_argcount]


_attr_error = ("CherryPy Tools cannot be turned on directly. Instead, turn them "
               "on via config, or use them as decorators on your page handlers.")

class Tool(object):
    """A registered function for use with CherryPy request-processing hooks.
    
    help(tool.callable) should give you more information about this Tool.
    """
    
    namespace = "tools"
    
    def __init__(self, point, callable, name=None, priority=50):
        self._point = point
        self.callable = callable
        self._name = name
        self._priority = priority
        self.__doc__ = self.callable.__doc__
        self._setargs()
    
    def _get_on(self):
        raise AttributeError(_attr_error)
    def _set_on(self, value):
        raise AttributeError(_attr_error)
    on = property(_get_on, _set_on)
    
    def _setargs(self):
        """Copy func parameter names to obj attributes."""
        try:
            for arg in _getargs(self.callable):
                setattr(self, arg, None)
        except (TypeError, AttributeError):
            if hasattr(self.callable, "__call__"):
                for arg in _getargs(self.callable.__call__):
                    setattr(self, arg, None)
        # IronPython 1.0 raises NotImplementedError because
        # inspect.getargspec tries to access Python bytecode
        # in co_code attribute.
        except NotImplementedError:
            pass
        # IronPython 1B1 may raise IndexError in some cases,
        # but if we trap it here it doesn't prevent CP from working.
        except IndexError:
            pass
    
    def _merged_args(self, d=None):
        """Return a dict of configuration entries for this Tool."""
        if d:
            conf = d.copy()
        else:
            conf = {}
        
        tm = cherrypy.serving.request.toolmaps[self.namespace]
        if self._name in tm:
            conf.update(tm[self._name])
        
        if "on" in conf:
            del conf["on"]
        
        return conf
    
    def __call__(self, *args, **kwargs):
        """Compile-time decorator (turn on the tool in config).
        
        For example::
        
            @tools.proxy()
            def whats_my_base(self):
                return cherrypy.request.base
            whats_my_base.exposed = True
        """
        if args:
            raise TypeError("The %r Tool does not accept positional "
                            "arguments; you must use keyword arguments."
                            % self._name)
        def tool_decorator(f):
            if not hasattr(f, "_cp_config"):
                f._cp_config = {}
            subspace = self.namespace + "." + self._name + "."
            f._cp_config[subspace + "on"] = True
            for k, v in kwargs.items():
                f._cp_config[subspace + k] = v
            return f
        return tool_decorator
    
    def _setup(self):
        """Hook this tool into cherrypy.request.
        
        The standard CherryPy request object will automatically call this
        method when the tool is "turned on" in config.
        """
        conf = self._merged_args()
        p = conf.pop("priority", None)
        if p is None:
            p = getattr(self.callable, "priority", self._priority)
        cherrypy.serving.request.hooks.attach(self._point, self.callable,
                                              priority=p, **conf)


class HandlerTool(Tool):
    """Tool which is called 'before main', that may skip normal handlers.
    
    If the tool successfully handles the request (by setting response.body),
    if should return True. This will cause CherryPy to skip any 'normal' page
    handler. If the tool did not handle the request, it should return False
    to tell CherryPy to continue on and call the normal page handler. If the
    tool is declared AS a page handler (see the 'handler' method), returning
    False will raise NotFound.
    """
    
    def __init__(self, callable, name=None):
        Tool.__init__(self, 'before_handler', callable, name)
    
    def handler(self, *args, **kwargs):
        """Use this tool as a CherryPy page handler.
        
        For example::
        
            class Root:
                nav = tools.staticdir.handler(section="/nav", dir="nav",
                                              root=absDir)
        """
        def handle_func(*a, **kw):
            handled = self.callable(*args, **self._merged_args(kwargs))
            if not handled:
                raise cherrypy.NotFound()
            return cherrypy.serving.response.body
        handle_func.exposed = True
        return handle_func
    
    def _wrapper(self, **kwargs):
        if self.callable(**kwargs):
            cherrypy.serving.request.handler = None
    
    def _setup(self):
        """Hook this tool into cherrypy.request.
        
        The standard CherryPy request object will automatically call this
        method when the tool is "turned on" in config.
        """
        conf = self._merged_args()
        p = conf.pop("priority", None)
        if p is None:
            p = getattr(self.callable, "priority", self._priority)
        cherrypy.serving.request.hooks.attach(self._point, self._wrapper,
                                              priority=p, **conf)


class HandlerWrapperTool(Tool):
    """Tool which wraps request.handler in a provided wrapper function.
    
    The 'newhandler' arg must be a handler wrapper function that takes a
    'next_handler' argument, plus ``*args`` and ``**kwargs``. Like all
    page handler
    functions, it must return an iterable for use as cherrypy.response.body.
    
    For example, to allow your 'inner' page handlers to return dicts
    which then get interpolated into a template::
    
        def interpolator(next_handler, *args, **kwargs):
            filename = cherrypy.request.config.get('template')
            cherrypy.response.template = env.get_template(filename)
            response_dict = next_handler(*args, **kwargs)
            return cherrypy.response.template.render(**response_dict)
        cherrypy.tools.jinja = HandlerWrapperTool(interpolator)
    """
    
    def __init__(self, newhandler, point='before_handler', name=None, priority=50):
        self.newhandler = newhandler
        self._point = point
        self._name = name
        self._priority = priority
    
    def callable(self, debug=False):
        innerfunc = cherrypy.serving.request.handler
        def wrap(*args, **kwargs):
            return self.newhandler(innerfunc, *args, **kwargs)
        cherrypy.serving.request.handler = wrap


class ErrorTool(Tool):
    """Tool which is used to replace the default request.error_response."""
    
    def __init__(self, callable, name=None):
        Tool.__init__(self, None, callable, name)
    
    def _wrapper(self):
        self.callable(**self._merged_args())
    
    def _setup(self):
        """Hook this tool into cherrypy.request.
        
        The standard CherryPy request object will automatically call this
        method when the tool is "turned on" in config.
        """
        cherrypy.serving.request.error_response = self._wrapper


#                              Builtin tools                              #

from cherrypy.lib import cptools, encoding, auth, static, jsontools
from cherrypy.lib import sessions as _sessions, xmlrpcutil as _xmlrpc
from cherrypy.lib import caching as _caching
from cherrypy.lib import auth_basic, auth_digest


class SessionTool(Tool):
    """Session Tool for CherryPy.
    
    sessions.locking
        When 'implicit' (the default), the session will be locked for you,
        just before running the page handler.
        
        When 'early', the session will be locked before reading the request
        body. This is off by default for safety reasons; for example,
        a large upload would block the session, denying an AJAX
        progress meter (see http://www.cherrypy.org/ticket/630).
        
        When 'explicit' (or any other value), you need to call
        cherrypy.session.acquire_lock() yourself before using
        session data.
    """
    
    def __init__(self):
        # _sessions.init must be bound after headers are read
        Tool.__init__(self, 'before_request_body', _sessions.init)
    
    def _lock_session(self):
        cherrypy.serving.session.acquire_lock()
    
    def _setup(self):
        """Hook this tool into cherrypy.request.
        
        The standard CherryPy request object will automatically call this
        method when the tool is "turned on" in config.
        """
        hooks = cherrypy.serving.request.hooks
        
        conf = self._merged_args()
        
        p = conf.pop("priority", None)
        if p is None:
            p = getattr(self.callable, "priority", self._priority)
        
        hooks.attach(self._point, self.callable, priority=p, **conf)
        
        locking = conf.pop('locking', 'implicit')
        if locking == 'implicit':
            hooks.attach('before_handler', self._lock_session)
        elif locking == 'early':
            # Lock before the request body (but after _sessions.init runs!)
            hooks.attach('before_request_body', self._lock_session,
                         priority=60)
        else:
            # Don't lock
            pass
        
        hooks.attach('before_finalize', _sessions.save)
        hooks.attach('on_end_request', _sessions.close)
        
    def regenerate(self):
        """Drop the current session and make a new one (with a new id)."""
        sess = cherrypy.serving.session
        sess.regenerate()
        
        # Grab cookie-relevant tool args
        conf = dict([(k, v) for k, v in self._merged_args().items()
                     if k in ('path', 'path_header', 'name', 'timeout',
                              'domain', 'secure')])
        _sessions.set_response_cookie(**conf)




class XMLRPCController(object):
    """A Controller (page handler collection) for XML-RPC.
    
    To use it, have your controllers subclass this base class (it will
    turn on the tool for you).
    
    You can also supply the following optional config entries::
    
        tools.xmlrpc.encoding: 'utf-8'
        tools.xmlrpc.allow_none: 0
    
    XML-RPC is a rather discontinuous layer over HTTP; dispatching to the
    appropriate handler must first be performed according to the URL, and
    then a second dispatch step must take place according to the RPC method
    specified in the request body. It also allows a superfluous "/RPC2"
    prefix in the URL, supplies its own handler args in the body, and
    requires a 200 OK "Fault" response instead of 404 when the desired
    method is not found.
    
    Therefore, XML-RPC cannot be implemented for CherryPy via a Tool alone.
    This Controller acts as the dispatch target for the first half (based
    on the URL); it then reads the RPC method from the request body and
    does its own second dispatch step based on that method. It also reads
    body params, and returns a Fault on error.
    
    The XMLRPCDispatcher strips any /RPC2 prefix; if you aren't using /RPC2
    in your URL's, you can safely skip turning on the XMLRPCDispatcher.
    Otherwise, you need to use declare it in config::
    
        request.dispatch: cherrypy.dispatch.XMLRPCDispatcher()
    """
    
    # Note we're hard-coding this into the 'tools' namespace. We could do
    # a huge amount of work to make it relocatable, but the only reason why
    # would be if someone actually disabled the default_toolbox. Meh.
    _cp_config = {'tools.xmlrpc.on': True}
    
    def default(self, *vpath, **params):
        rpcparams, rpcmethod = _xmlrpc.process_body()
        
        subhandler = self
        for attr in str(rpcmethod).split('.'):
            subhandler = getattr(subhandler, attr, None)
         
        if subhandler and getattr(subhandler, "exposed", False):
            body = subhandler(*(vpath + rpcparams), **params)
        
        else:
            # http://www.cherrypy.org/ticket/533
            # if a method is not found, an xmlrpclib.Fault should be returned
            # raising an exception here will do that; see
            # cherrypy.lib.xmlrpcutil.on_error
            raise Exception('method "%s" is not supported' % attr)
        
        conf = cherrypy.serving.request.toolmaps['tools'].get("xmlrpc", {})
        _xmlrpc.respond(body,
                        conf.get('encoding', 'utf-8'),
                        conf.get('allow_none', 0))
        return cherrypy.serving.response.body
    default.exposed = True


class SessionAuthTool(HandlerTool):
    
    def _setargs(self):
        for name in dir(cptools.SessionAuth):
            if not name.startswith("__"):
                setattr(self, name, None)


class CachingTool(Tool):
    """Caching Tool for CherryPy."""
    
    def _wrapper(self, **kwargs):
        request = cherrypy.serving.request
        if _caching.get(**kwargs):
            request.handler = None
        else:
            if request.cacheable:
                # Note the devious technique here of adding hooks on the fly
                request.hooks.attach('before_finalize', _caching.tee_output,
                                     priority = 90)
    _wrapper.priority = 20
    
    def _setup(self):
        """Hook caching into cherrypy.request."""
        conf = self._merged_args()
        
        p = conf.pop("priority", None)
        cherrypy.serving.request.hooks.attach('before_handler', self._wrapper,
                                              priority=p, **conf)



class Toolbox(object):
    """A collection of Tools.
    
    This object also functions as a config namespace handler for itself.
    Custom toolboxes should be added to each Application's toolboxes dict.
    """
    
    def __init__(self, namespace):
        self.namespace = namespace
    
    def __setattr__(self, name, value):
        # If the Tool._name is None, supply it from the attribute name.
        if isinstance(value, Tool):
            if value._name is None:
                value._name = name
            value.namespace = self.namespace
        object.__setattr__(self, name, value)
    
    def __enter__(self):
        """Populate request.toolmaps from tools specified in config."""
        cherrypy.serving.request.toolmaps[self.namespace] = map = {}
        def populate(k, v):
            toolname, arg = k.split(".", 1)
            bucket = map.setdefault(toolname, {})
            bucket[arg] = v
        return populate
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Run tool._setup() for each tool in our toolmap."""
        map = cherrypy.serving.request.toolmaps.get(self.namespace)
        if map:
            for name, settings in map.items():
                if settings.get("on", False):
                    tool = getattr(self, name)
                    tool._setup()


class DeprecatedTool(Tool):
    
    _name = None
    warnmsg = "This Tool is deprecated."
    
    def __init__(self, point, warnmsg=None):
        self.point = point
        if warnmsg is not None:
            self.warnmsg = warnmsg
    
    def __call__(self, *args, **kwargs):
        warnings.warn(self.warnmsg)
        def tool_decorator(f):
            return f
        return tool_decorator
    
    def _setup(self):
        warnings.warn(self.warnmsg)


default_toolbox = _d = Toolbox("tools")
_d.session_auth = SessionAuthTool(cptools.session_auth)
_d.allow = Tool('on_start_resource', cptools.allow)
_d.proxy = Tool('before_request_body', cptools.proxy, priority=30)
_d.response_headers = Tool('on_start_resource', cptools.response_headers)
_d.log_tracebacks = Tool('before_error_response', cptools.log_traceback)
_d.log_headers = Tool('before_error_response', cptools.log_request_headers)
_d.log_hooks = Tool('on_end_request', cptools.log_hooks, priority=100)
_d.err_redirect = ErrorTool(cptools.redirect)
_d.etags = Tool('before_finalize', cptools.validate_etags, priority=75)
_d.decode = Tool('before_request_body', encoding.decode)
# the order of encoding, gzip, caching is important
_d.encode = Tool('before_handler', encoding.ResponseEncoder, priority=70)
_d.gzip = Tool('before_finalize', encoding.gzip, priority=80)
_d.staticdir = HandlerTool(static.staticdir)
_d.staticfile = HandlerTool(static.staticfile)
_d.sessions = SessionTool()
_d.xmlrpc = ErrorTool(_xmlrpc.on_error)
_d.caching = CachingTool('before_handler', _caching.get, 'caching')
_d.expires = Tool('before_finalize', _caching.expires)
_d.tidy = DeprecatedTool('before_finalize',
    "The tidy tool has been removed from the standard distribution of CherryPy. "
    "The most recent version can be found at http://tools.cherrypy.org/browser.")
_d.nsgmls = DeprecatedTool('before_finalize',
    "The nsgmls tool has been removed from the standard distribution of CherryPy. "
    "The most recent version can be found at http://tools.cherrypy.org/browser.")
_d.ignore_headers = Tool('before_request_body', cptools.ignore_headers)
_d.referer = Tool('before_request_body', cptools.referer)
_d.basic_auth = Tool('on_start_resource', auth.basic_auth)
_d.digest_auth = Tool('on_start_resource', auth.digest_auth)
_d.trailing_slash = Tool('before_handler', cptools.trailing_slash, priority=60)
_d.flatten = Tool('before_finalize', cptools.flatten)
_d.accept = Tool('on_start_resource', cptools.accept)
_d.redirect = Tool('on_start_resource', cptools.redirect)
_d.autovary = Tool('on_start_resource', cptools.autovary, priority=0)
_d.json_in = Tool('before_request_body', jsontools.json_in, priority=30)
_d.json_out = Tool('before_handler', jsontools.json_out, priority=30)
_d.auth_basic = Tool('before_handler', auth_basic.basic_auth, priority=1)
_d.auth_digest = Tool('before_handler', auth_digest.digest_auth, priority=1)

del _d, cptools, encoding, auth, static
