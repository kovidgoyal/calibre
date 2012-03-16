"""CherryPy dispatchers.

A 'dispatcher' is the object which looks up the 'page handler' callable
and collects config for the current request based on the path_info, other
request attributes, and the application architecture. The core calls the
dispatcher as early as possible, passing it a 'path_info' argument.

The default dispatcher discovers the page handler by matching path_info
to a hierarchical arrangement of objects, starting at request.app.root.
"""

import string
import sys
import types
try:
    classtype = (type, types.ClassType)
except AttributeError:
    classtype = type

import cherrypy
from cherrypy._cpcompat import set


class PageHandler(object):
    """Callable which sets response.body."""
    
    def __init__(self, callable, *args, **kwargs):
        self.callable = callable
        self.args = args
        self.kwargs = kwargs
    
    def __call__(self):
        try:
            return self.callable(*self.args, **self.kwargs)
        except TypeError:
            x = sys.exc_info()[1]
            try:
                test_callable_spec(self.callable, self.args, self.kwargs)
            except cherrypy.HTTPError:
                raise sys.exc_info()[1]
            except:
                raise x
            raise


def test_callable_spec(callable, callable_args, callable_kwargs):
    """
    Inspect callable and test to see if the given args are suitable for it.

    When an error occurs during the handler's invoking stage there are 2
    erroneous cases:
    1.  Too many parameters passed to a function which doesn't define
        one of *args or **kwargs.
    2.  Too little parameters are passed to the function.

    There are 3 sources of parameters to a cherrypy handler.
    1.  query string parameters are passed as keyword parameters to the handler.
    2.  body parameters are also passed as keyword parameters.
    3.  when partial matching occurs, the final path atoms are passed as
        positional args.
    Both the query string and path atoms are part of the URI.  If they are
    incorrect, then a 404 Not Found should be raised. Conversely the body
    parameters are part of the request; if they are invalid a 400 Bad Request.
    """
    show_mismatched_params = getattr(
        cherrypy.serving.request, 'show_mismatched_params', False)
    try:
        (args, varargs, varkw, defaults) = inspect.getargspec(callable)
    except TypeError:
        if isinstance(callable, object) and hasattr(callable, '__call__'):
            (args, varargs, varkw, defaults) = inspect.getargspec(callable.__call__)
        else:
            # If it wasn't one of our own types, re-raise 
            # the original error
            raise

    if args and args[0] == 'self':
        args = args[1:]

    arg_usage = dict([(arg, 0,) for arg in args])
    vararg_usage = 0
    varkw_usage = 0
    extra_kwargs = set()

    for i, value in enumerate(callable_args):
        try:
            arg_usage[args[i]] += 1
        except IndexError:
            vararg_usage += 1

    for key in callable_kwargs.keys():
        try:
            arg_usage[key] += 1
        except KeyError:
            varkw_usage += 1
            extra_kwargs.add(key)

    # figure out which args have defaults.
    args_with_defaults = args[-len(defaults or []):]
    for i, val in enumerate(defaults or []):
        # Defaults take effect only when the arg hasn't been used yet.
        if arg_usage[args_with_defaults[i]] == 0:
            arg_usage[args_with_defaults[i]] += 1

    missing_args = []
    multiple_args = []
    for key, usage in arg_usage.items():
        if usage == 0:
            missing_args.append(key)
        elif usage > 1:
            multiple_args.append(key)

    if missing_args:
        # In the case where the method allows body arguments
        # there are 3 potential errors:
        # 1. not enough query string parameters -> 404
        # 2. not enough body parameters -> 400
        # 3. not enough path parts (partial matches) -> 404
        #
        # We can't actually tell which case it is, 
        # so I'm raising a 404 because that covers 2/3 of the
        # possibilities
        # 
        # In the case where the method does not allow body
        # arguments it's definitely a 404.
        message = None
        if show_mismatched_params:
            message="Missing parameters: %s" % ",".join(missing_args)
        raise cherrypy.HTTPError(404, message=message)

    # the extra positional arguments come from the path - 404 Not Found
    if not varargs and vararg_usage > 0:
        raise cherrypy.HTTPError(404)

    body_params = cherrypy.serving.request.body.params or {}
    body_params = set(body_params.keys())
    qs_params = set(callable_kwargs.keys()) - body_params

    if multiple_args:
        if qs_params.intersection(set(multiple_args)):
            # If any of the multiple parameters came from the query string then
            # it's a 404 Not Found
            error = 404
        else:
            # Otherwise it's a 400 Bad Request
            error = 400

        message = None
        if show_mismatched_params:
            message="Multiple values for parameters: "\
                    "%s" % ",".join(multiple_args)
        raise cherrypy.HTTPError(error, message=message)

    if not varkw and varkw_usage > 0:

        # If there were extra query string parameters, it's a 404 Not Found
        extra_qs_params = set(qs_params).intersection(extra_kwargs)
        if extra_qs_params:
            message = None
            if show_mismatched_params:
                message="Unexpected query string "\
                        "parameters: %s" % ", ".join(extra_qs_params)
            raise cherrypy.HTTPError(404, message=message)

        # If there were any extra body parameters, it's a 400 Not Found
        extra_body_params = set(body_params).intersection(extra_kwargs)
        if extra_body_params:
            message = None
            if show_mismatched_params:
                message="Unexpected body parameters: "\
                        "%s" % ", ".join(extra_body_params)
            raise cherrypy.HTTPError(400, message=message)


try:
    import inspect
except ImportError:
    test_callable_spec = lambda callable, args, kwargs: None



class LateParamPageHandler(PageHandler):
    """When passing cherrypy.request.params to the page handler, we do not
    want to capture that dict too early; we want to give tools like the
    decoding tool a chance to modify the params dict in-between the lookup
    of the handler and the actual calling of the handler. This subclass
    takes that into account, and allows request.params to be 'bound late'
    (it's more complicated than that, but that's the effect).
    """
    
    def _get_kwargs(self):
        kwargs = cherrypy.serving.request.params.copy()
        if self._kwargs:
            kwargs.update(self._kwargs)
        return kwargs
    
    def _set_kwargs(self, kwargs):
        self._kwargs = kwargs
    
    kwargs = property(_get_kwargs, _set_kwargs,
                      doc='page handler kwargs (with '
                      'cherrypy.request.params copied in)')


if sys.version_info < (3, 0):
    punctuation_to_underscores = string.maketrans(
        string.punctuation, '_' * len(string.punctuation))
    def validate_translator(t):
        if not isinstance(t, str) or len(t) != 256:
            raise ValueError("The translate argument must be a str of len 256.")
else:
    punctuation_to_underscores = str.maketrans(
        string.punctuation, '_' * len(string.punctuation))
    def validate_translator(t):
        if not isinstance(t, dict):
            raise ValueError("The translate argument must be a dict.")

class Dispatcher(object):
    """CherryPy Dispatcher which walks a tree of objects to find a handler.
    
    The tree is rooted at cherrypy.request.app.root, and each hierarchical
    component in the path_info argument is matched to a corresponding nested
    attribute of the root object. Matching handlers must have an 'exposed'
    attribute which evaluates to True. The special method name "index"
    matches a URI which ends in a slash ("/"). The special method name
    "default" may match a portion of the path_info (but only when no longer
    substring of the path_info matches some other object).
    
    This is the default, built-in dispatcher for CherryPy.
    """
    
    dispatch_method_name = '_cp_dispatch'
    """
    The name of the dispatch method that nodes may optionally implement
    to provide their own dynamic dispatch algorithm.
    """
    
    def __init__(self, dispatch_method_name=None,
                 translate=punctuation_to_underscores):
        validate_translator(translate)
        self.translate = translate
        if dispatch_method_name:
            self.dispatch_method_name = dispatch_method_name

    def __call__(self, path_info):
        """Set handler and config for the current request."""
        request = cherrypy.serving.request
        func, vpath = self.find_handler(path_info)
        
        if func:
            # Decode any leftover %2F in the virtual_path atoms.
            vpath = [x.replace("%2F", "/") for x in vpath]
            request.handler = LateParamPageHandler(func, *vpath)
        else:
            request.handler = cherrypy.NotFound()
    
    def find_handler(self, path):
        """Return the appropriate page handler, plus any virtual path.
        
        This will return two objects. The first will be a callable,
        which can be used to generate page output. Any parameters from
        the query string or request body will be sent to that callable
        as keyword arguments.
        
        The callable is found by traversing the application's tree,
        starting from cherrypy.request.app.root, and matching path
        components to successive objects in the tree. For example, the
        URL "/path/to/handler" might return root.path.to.handler.
        
        The second object returned will be a list of names which are
        'virtual path' components: parts of the URL which are dynamic,
        and were not used when looking up the handler.
        These virtual path components are passed to the handler as
        positional arguments.
        """
        request = cherrypy.serving.request
        app = request.app
        root = app.root
        dispatch_name = self.dispatch_method_name
        
        # Get config for the root object/path.
        fullpath = [x for x in path.strip('/').split('/') if x] + ['index']
        fullpath_len = len(fullpath)
        segleft = fullpath_len
        nodeconf = {}
        if hasattr(root, "_cp_config"):
            nodeconf.update(root._cp_config)
        if "/" in app.config:
            nodeconf.update(app.config["/"])
        object_trail = [['root', root, nodeconf, segleft]]
        
        node = root
        iternames = fullpath[:]
        while iternames:
            name = iternames[0]
            # map to legal Python identifiers (e.g. replace '.' with '_')
            objname = name.translate(self.translate)
            
            nodeconf = {}
            subnode = getattr(node, objname, None)
            pre_len = len(iternames)
            if subnode is None:
                dispatch = getattr(node, dispatch_name, None)
                if dispatch and hasattr(dispatch, '__call__') and not \
                        getattr(dispatch, 'exposed', False) and \
                        pre_len > 1:
                    #Don't expose the hidden 'index' token to _cp_dispatch
                    #We skip this if pre_len == 1 since it makes no sense
                    #to call a dispatcher when we have no tokens left.
                    index_name = iternames.pop()
                    subnode = dispatch(vpath=iternames)
                    iternames.append(index_name)
                else:
                    #We didn't find a path, but keep processing in case there
                    #is a default() handler.
                    iternames.pop(0)
            else:
                #We found the path, remove the vpath entry
                iternames.pop(0)
            segleft = len(iternames)
            if segleft > pre_len:
                #No path segment was removed.  Raise an error.
                raise cherrypy.CherryPyException(
                    "A vpath segment was added.  Custom dispatchers may only "
                    + "remove elements.  While trying to process "
                    + "{0} in {1}".format(name, fullpath)
                    )
            elif segleft == pre_len:
                #Assume that the handler used the current path segment, but
                #did not pop it.  This allows things like 
                #return getattr(self, vpath[0], None)
                iternames.pop(0)
                segleft -= 1
            node = subnode

            if node is not None:
                # Get _cp_config attached to this node.
                if hasattr(node, "_cp_config"):
                    nodeconf.update(node._cp_config)
            
            # Mix in values from app.config for this path.
            existing_len = fullpath_len - pre_len
            if existing_len != 0:
                curpath = '/' + '/'.join(fullpath[0:existing_len])
            else:
                curpath = ''
            new_segs = fullpath[fullpath_len - pre_len:fullpath_len - segleft]
            for seg in new_segs:
                curpath += '/' + seg
                if curpath in app.config:
                    nodeconf.update(app.config[curpath])
            
            object_trail.append([name, node, nodeconf, segleft])
            
        def set_conf():
            """Collapse all object_trail config into cherrypy.request.config."""
            base = cherrypy.config.copy()
            # Note that we merge the config from each node
            # even if that node was None.
            for name, obj, conf, segleft in object_trail:
                base.update(conf)
                if 'tools.staticdir.dir' in conf:
                    base['tools.staticdir.section'] = '/' + '/'.join(fullpath[0:fullpath_len - segleft])
            return base
        
        # Try successive objects (reverse order)
        num_candidates = len(object_trail) - 1
        for i in range(num_candidates, -1, -1):
            
            name, candidate, nodeconf, segleft = object_trail[i]
            if candidate is None:
                continue
            
            # Try a "default" method on the current leaf.
            if hasattr(candidate, "default"):
                defhandler = candidate.default
                if getattr(defhandler, 'exposed', False):
                    # Insert any extra _cp_config from the default handler.
                    conf = getattr(defhandler, "_cp_config", {})
                    object_trail.insert(i+1, ["default", defhandler, conf, segleft])
                    request.config = set_conf()
                    # See http://www.cherrypy.org/ticket/613
                    request.is_index = path.endswith("/")
                    return defhandler, fullpath[fullpath_len - segleft:-1]
            
            # Uncomment the next line to restrict positional params to "default".
            # if i < num_candidates - 2: continue
            
            # Try the current leaf.
            if getattr(candidate, 'exposed', False):
                request.config = set_conf()
                if i == num_candidates:
                    # We found the extra ".index". Mark request so tools
                    # can redirect if path_info has no trailing slash.
                    request.is_index = True
                else:
                    # We're not at an 'index' handler. Mark request so tools
                    # can redirect if path_info has NO trailing slash.
                    # Note that this also includes handlers which take
                    # positional parameters (virtual paths).
                    request.is_index = False
                return candidate, fullpath[fullpath_len - segleft:-1]
        
        # We didn't find anything
        request.config = set_conf()
        return None, []


class MethodDispatcher(Dispatcher):
    """Additional dispatch based on cherrypy.request.method.upper().
    
    Methods named GET, POST, etc will be called on an exposed class.
    The method names must be all caps; the appropriate Allow header
    will be output showing all capitalized method names as allowable
    HTTP verbs.
    
    Note that the containing class must be exposed, not the methods.
    """
    
    def __call__(self, path_info):
        """Set handler and config for the current request."""
        request = cherrypy.serving.request
        resource, vpath = self.find_handler(path_info)
        
        if resource:
            # Set Allow header
            avail = [m for m in dir(resource) if m.isupper()]
            if "GET" in avail and "HEAD" not in avail:
                avail.append("HEAD")
            avail.sort()
            cherrypy.serving.response.headers['Allow'] = ", ".join(avail)
            
            # Find the subhandler
            meth = request.method.upper()
            func = getattr(resource, meth, None)
            if func is None and meth == "HEAD":
                func = getattr(resource, "GET", None)
            if func:
                # Grab any _cp_config on the subhandler.
                if hasattr(func, "_cp_config"):
                    request.config.update(func._cp_config)
                
                # Decode any leftover %2F in the virtual_path atoms.
                vpath = [x.replace("%2F", "/") for x in vpath]
                request.handler = LateParamPageHandler(func, *vpath)
            else:
                request.handler = cherrypy.HTTPError(405)
        else:
            request.handler = cherrypy.NotFound()


class RoutesDispatcher(object):
    """A Routes based dispatcher for CherryPy."""
    
    def __init__(self, full_result=False):
        """
        Routes dispatcher

        Set full_result to True if you wish the controller
        and the action to be passed on to the page handler
        parameters. By default they won't be.
        """
        import routes
        self.full_result = full_result
        self.controllers = {}
        self.mapper = routes.Mapper()
        self.mapper.controller_scan = self.controllers.keys
        
    def connect(self, name, route, controller, **kwargs):
        self.controllers[name] = controller
        self.mapper.connect(name, route, controller=name, **kwargs)
    
    def redirect(self, url):
        raise cherrypy.HTTPRedirect(url)
    
    def __call__(self, path_info):
        """Set handler and config for the current request."""
        func = self.find_handler(path_info)
        if func:
            cherrypy.serving.request.handler = LateParamPageHandler(func)
        else:
            cherrypy.serving.request.handler = cherrypy.NotFound()
    
    def find_handler(self, path_info):
        """Find the right page handler, and set request.config."""
        import routes
        
        request = cherrypy.serving.request
        
        config = routes.request_config()
        config.mapper = self.mapper
        if hasattr(request, 'wsgi_environ'):
            config.environ = request.wsgi_environ
        config.host = request.headers.get('Host', None)
        config.protocol = request.scheme
        config.redirect = self.redirect
        
        result = self.mapper.match(path_info)
        
        config.mapper_dict = result
        params = {}
        if result:
            params = result.copy()
        if not self.full_result:
            params.pop('controller', None)
            params.pop('action', None)
        request.params.update(params)
        
        # Get config for the root object/path.
        request.config = base = cherrypy.config.copy()
        curpath = ""
        
        def merge(nodeconf):
            if 'tools.staticdir.dir' in nodeconf:
                nodeconf['tools.staticdir.section'] = curpath or "/"
            base.update(nodeconf)
        
        app = request.app
        root = app.root
        if hasattr(root, "_cp_config"):
            merge(root._cp_config)
        if "/" in app.config:
            merge(app.config["/"])
        
        # Mix in values from app.config.
        atoms = [x for x in path_info.split("/") if x]
        if atoms:
            last = atoms.pop()
        else:
            last = None
        for atom in atoms:
            curpath = "/".join((curpath, atom))
            if curpath in app.config:
                merge(app.config[curpath])
        
        handler = None
        if result:
            controller = result.get('controller')
            controller = self.controllers.get(controller, controller)
            if controller:
                if isinstance(controller, classtype):
                    controller = controller()
                # Get config from the controller.
                if hasattr(controller, "_cp_config"):
                    merge(controller._cp_config)
            
            action = result.get('action')
            if action is not None:
                handler = getattr(controller, action, None)
                # Get config from the handler 
                if hasattr(handler, "_cp_config"): 
                    merge(handler._cp_config)
            else:
                handler = controller
        
        # Do the last path atom here so it can
        # override the controller's _cp_config.
        if last:
            curpath = "/".join((curpath, last))
            if curpath in app.config:
                merge(app.config[curpath])
        
        return handler


def XMLRPCDispatcher(next_dispatcher=Dispatcher()):
    from cherrypy.lib import xmlrpcutil
    def xmlrpc_dispatch(path_info):
        path_info = xmlrpcutil.patched_path(path_info)
        return next_dispatcher(path_info)
    return xmlrpc_dispatch


def VirtualHost(next_dispatcher=Dispatcher(), use_x_forwarded_host=True, **domains):
    """
    Select a different handler based on the Host header.
    
    This can be useful when running multiple sites within one CP server.
    It allows several domains to point to different parts of a single
    website structure. For example::
    
        http://www.domain.example  ->  root
        http://www.domain2.example  ->  root/domain2/
        http://www.domain2.example:443  ->  root/secure
    
    can be accomplished via the following config::
    
        [/]
        request.dispatch = cherrypy.dispatch.VirtualHost(
            **{'www.domain2.example': '/domain2',
               'www.domain2.example:443': '/secure',
              })
    
    next_dispatcher
        The next dispatcher object in the dispatch chain.
        The VirtualHost dispatcher adds a prefix to the URL and calls
        another dispatcher. Defaults to cherrypy.dispatch.Dispatcher().
    
    use_x_forwarded_host
        If True (the default), any "X-Forwarded-Host"
        request header will be used instead of the "Host" header. This
        is commonly added by HTTP servers (such as Apache) when proxying.
    
    ``**domains``
        A dict of {host header value: virtual prefix} pairs.
        The incoming "Host" request header is looked up in this dict,
        and, if a match is found, the corresponding "virtual prefix"
        value will be prepended to the URL path before calling the
        next dispatcher. Note that you often need separate entries
        for "example.com" and "www.example.com". In addition, "Host"
        headers may contain the port number.
    """
    from cherrypy.lib import httputil
    def vhost_dispatch(path_info):
        request = cherrypy.serving.request
        header = request.headers.get
        
        domain = header('Host', '')
        if use_x_forwarded_host:
            domain = header("X-Forwarded-Host", domain)
        
        prefix = domains.get(domain, "")
        if prefix:
            path_info = httputil.urljoin(prefix, path_info)
        
        result = next_dispatcher(path_info)
        
        # Touch up staticdir config. See http://www.cherrypy.org/ticket/614.
        section = request.config.get('tools.staticdir.section')
        if section:
            section = section[len(prefix):]
            request.config['tools.staticdir.section'] = section
        
        return result
    return vhost_dispatch

