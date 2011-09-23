"""Mapper and Sub-Mapper"""
import re
import sys
import threading

from routes import request_config
from routes.lru import LRUCache
from routes.util import controller_scan, MatchException, RoutesException
from routes.route import Route


COLLECTION_ACTIONS = ['index', 'create', 'new']
MEMBER_ACTIONS = ['show', 'update', 'delete', 'edit']


def strip_slashes(name):
    """Remove slashes from the beginning and end of a part/URL."""
    if name.startswith('/'):
        name = name[1:]
    if name.endswith('/'):
        name = name[:-1]
    return name


class SubMapperParent(object):
    """Base class for Mapper and SubMapper, both of which may be the parent
    of SubMapper objects
    """
    
    def submapper(self, **kargs):
        """Create a partial version of the Mapper with the designated
        options set
        
        This results in a :class:`routes.mapper.SubMapper` object.
        
        If keyword arguments provided to this method also exist in the
        keyword arguments provided to the submapper, their values will
        be merged with the saved options going first.
        
        In addition to :class:`routes.route.Route` arguments, submapper
        can also take a ``path_prefix`` argument which will be
        prepended to the path of all routes that are connected.
        
        Example::
            
            >>> map = Mapper(controller_scan=None)
            >>> map.connect('home', '/', controller='home', action='splash')
            >>> map.matchlist[0].name == 'home'
            True
            >>> m = map.submapper(controller='home')
            >>> m.connect('index', '/index', action='index')
            >>> map.matchlist[1].name == 'index'
            True
            >>> map.matchlist[1].defaults['controller'] == 'home'
            True
        
        Optional ``collection_name`` and ``resource_name`` arguments are
        used in the generation of route names by the ``action`` and
        ``link`` methods.  These in turn are used by the ``index``,
        ``new``, ``create``, ``show``, ``edit``, ``update`` and
        ``delete`` methods which may be invoked indirectly by listing
        them in the ``actions`` argument.  If the ``formatted`` argument
        is set to ``True`` (the default), generated paths are given the
        suffix '{.format}' which matches or generates an optional format
        extension.
        
        Example::
        
            >>> from routes.util import url_for
            >>> map = Mapper(controller_scan=None)
            >>> m = map.submapper(path_prefix='/entries', collection_name='entries', resource_name='entry', actions=['index', 'new'])
            >>> url_for('entries') == '/entries'
            True
            >>> url_for('new_entry', format='xml') == '/entries/new.xml'
            True

        """
        return SubMapper(self, **kargs)

    def collection(self, collection_name, resource_name, path_prefix=None,
                   member_prefix='/{id}', controller=None,
                   collection_actions=COLLECTION_ACTIONS,
                   member_actions = MEMBER_ACTIONS, member_options=None,
                   **kwargs):
        """Create a submapper that represents a collection.

        This results in a :class:`routes.mapper.SubMapper` object, with a
        ``member`` property of the same type that represents the collection's
        member resources.
        
        Its interface is the same as the ``submapper`` together with
        ``member_prefix``, ``member_actions`` and ``member_options``
        which are passed to the ``member` submatter as ``path_prefix``,
        ``actions`` and keyword arguments respectively.
        
        Example::
        
            >>> from routes.util import url_for
            >>> map = Mapper(controller_scan=None)
            >>> c = map.collection('entries', 'entry')
            >>> c.member.link('ping', method='POST')
            >>> url_for('entries') == '/entries'
            True
            >>> url_for('edit_entry', id=1) == '/entries/1/edit'
            True
            >>> url_for('ping_entry', id=1) == '/entries/1/ping'
            True

        """
        if controller is None:
            controller = resource_name or collection_name
        
        if path_prefix is None:
            path_prefix = '/' + collection_name

        collection = SubMapper(self, collection_name=collection_name,
                               resource_name=resource_name,
                               path_prefix=path_prefix, controller=controller,
                               actions=collection_actions, **kwargs)
        
        collection.member = SubMapper(collection, path_prefix=member_prefix,
                                      actions=member_actions, 
                                      **(member_options or {}))

        return collection


class SubMapper(SubMapperParent):
    """Partial mapper for use with_options"""
    def __init__(self, obj, resource_name=None, collection_name=None,
                 actions=None, formatted=None, **kwargs):
        self.kwargs = kwargs
        self.obj = obj
        self.collection_name = collection_name
        self.member = None
        self.resource_name = resource_name \
                            or getattr(obj, 'resource_name', None) \
                            or kwargs.get('controller', None) \
                            or getattr(obj, 'controller', None)
        if formatted is not None:
            self.formatted = formatted
        else:
            self.formatted = getattr(obj, 'formatted', None)
            if self.formatted is None:
                self.formatted = True

        self.add_actions(actions or [])
        
    def connect(self, *args, **kwargs):
        newkargs = {}
        newargs = args
        for key, value in self.kwargs.items():
            if key == 'path_prefix':
                if len(args) > 1:
                    newargs = (args[0], self.kwargs[key] + args[1])
                else:
                    newargs = (self.kwargs[key] + args[0],)
            elif key in kwargs:
                if isinstance(value, dict):
                    newkargs[key] = dict(value, **kwargs[key]) # merge dicts
                else:
                    newkargs[key] = value + kwargs[key]
            else:
                newkargs[key] = self.kwargs[key]
        for key in kwargs:
            if key not in self.kwargs:
                newkargs[key] = kwargs[key]
        return self.obj.connect(*newargs, **newkargs)

    def link(self, rel=None, name=None, action=None, method='GET',
             formatted=None, **kwargs):
        """Generates a named route for a subresource.

        Example::
        
            >>> from routes.util import url_for
            >>> map = Mapper(controller_scan=None)
            >>> c = map.collection('entries', 'entry')
            >>> c.link('recent', name='recent_entries')
            >>> c.member.link('ping', method='POST', formatted=True)
            >>> url_for('entries') == '/entries'
            True
            >>> url_for('recent_entries') == '/entries/recent'
            True
            >>> url_for('ping_entry', id=1) == '/entries/1/ping'
            True
            >>> url_for('ping_entry', id=1, format='xml') == '/entries/1/ping.xml'
            True

        """
        if formatted or (formatted is None and self.formatted):
            suffix = '{.format}'
        else:
            suffix = ''

        return self.connect(name or (rel + '_' + self.resource_name),
                            '/' + (rel or name) + suffix,
                            action=action or rel or name,
                            **_kwargs_with_conditions(kwargs, method))

    def new(self, **kwargs):
        """Generates the "new" link for a collection submapper."""
        return self.link(rel='new', **kwargs)

    def edit(self, **kwargs):
        """Generates the "edit" link for a collection member submapper."""
        return self.link(rel='edit', **kwargs)

    def action(self, name=None, action=None, method='GET', formatted=None,
               **kwargs):
        """Generates a named route at the base path of a submapper.

        Example::
        
            >>> from routes import url_for
            >>> map = Mapper(controller_scan=None)
            >>> c = map.submapper(path_prefix='/entries', controller='entry')
            >>> c.action(action='index', name='entries', formatted=True)
            >>> c.action(action='create', method='POST')
            >>> url_for(controller='entry', action='index', method='GET') == '/entries'
            True
            >>> url_for(controller='entry', action='index', method='GET', format='xml') == '/entries.xml'
            True
            >>> url_for(controller='entry', action='create', method='POST') == '/entries'
            True

        """
        if formatted or (formatted is None and self.formatted):
            suffix = '{.format}'
        else:
            suffix = ''
        return self.connect(name or (action + '_' + self.resource_name),
                            suffix,
                            action=action or name,
                            **_kwargs_with_conditions(kwargs, method))
            
    def index(self, name=None, **kwargs):
        """Generates the "index" action for a collection submapper."""
        return self.action(name=name or self.collection_name,
                           action='index', method='GET', **kwargs)

    def show(self, name = None, **kwargs):
        """Generates the "show" action for a collection member submapper."""
        return self.action(name=name or self.resource_name,
                           action='show', method='GET', **kwargs)

    def create(self, **kwargs):
        """Generates the "create" action for a collection submapper."""
        return self.action(action='create', method='POST', **kwargs)
        
    def update(self, **kwargs):
        """Generates the "update" action for a collection member submapper."""
        return self.action(action='update', method='PUT', **kwargs)

    def delete(self, **kwargs):
        """Generates the "delete" action for a collection member submapper."""
        return self.action(action='delete', method='DELETE', **kwargs)

    def add_actions(self, actions):
        [getattr(self, action)() for action in actions]

    # Provided for those who prefer using the 'with' syntax in Python 2.5+
    def __enter__(self):
        return self
    
    def __exit__(self, type, value, tb):
        pass

# Create kwargs with a 'conditions' member generated for the given method
def _kwargs_with_conditions(kwargs, method):
    if method and 'conditions' not in kwargs:
        newkwargs = kwargs.copy()
        newkwargs['conditions'] = {'method': method}                
        return newkwargs             
    else:
        return kwargs



class Mapper(SubMapperParent):
    """Mapper handles URL generation and URL recognition in a web
    application.
    
    Mapper is built handling dictionary's. It is assumed that the web
    application will handle the dictionary returned by URL recognition
    to dispatch appropriately.
    
    URL generation is done by passing keyword parameters into the
    generate function, a URL is then returned.
    
    """
    def __init__(self, controller_scan=controller_scan, directory=None, 
                 always_scan=False, register=True, explicit=True):
        """Create a new Mapper instance
        
        All keyword arguments are optional.
        
        ``controller_scan``
            Function reference that will be used to return a list of
            valid controllers used during URL matching. If
            ``directory`` keyword arg is present, it will be passed
            into the function during its call. This option defaults to
            a function that will scan a directory for controllers.
            
            Alternatively, a list of controllers or None can be passed
            in which are assumed to be the definitive list of
            controller names valid when matching 'controller'.
        
        ``directory``
            Passed into controller_scan for the directory to scan. It
            should be an absolute path if using the default 
            ``controller_scan`` function.
        
        ``always_scan``
            Whether or not the ``controller_scan`` function should be
            run during every URL match. This is typically a good idea
            during development so the server won't need to be restarted
            anytime a controller is added.
        
        ``register``
            Boolean used to determine if the Mapper should use 
            ``request_config`` to register itself as the mapper. Since
            it's done on a thread-local basis, this is typically best
            used during testing though it won't hurt in other cases.
        
        ``explicit``
            Boolean used to determine if routes should be connected
            with implicit defaults of::
                
                {'controller':'content','action':'index','id':None}
            
            When set to True, these defaults will not be added to route
            connections and ``url_for`` will not use Route memory.
                
        Additional attributes that may be set after mapper
        initialization (ie, map.ATTRIBUTE = 'something'):
        
        ``encoding``
            Used to indicate alternative encoding/decoding systems to
            use with both incoming URL's, and during Route generation
            when passed a Unicode string. Defaults to 'utf-8'.
        
        ``decode_errors``
            How to handle errors in the encoding, generally ignoring
            any chars that don't convert should be sufficient. Defaults
            to 'ignore'.
        
        ``minimization``
            Boolean used to indicate whether or not Routes should
            minimize URL's and the generated URL's, or require every
            part where it appears in the path. Defaults to True.
        
        ``hardcode_names``
            Whether or not Named Routes result in the default options
            for the route being used *or* if they actually force url
            generation to use the route. Defaults to False.
        
        """
        self.matchlist = []
        self.maxkeys = {}
        self.minkeys = {}
        self.urlcache = LRUCache(1600)
        self._created_regs = False
        self._created_gens = False
        self._master_regexp = None
        self.prefix = None
        self.req_data = threading.local()
        self.directory = directory
        self.always_scan = always_scan
        self.controller_scan = controller_scan
        self._regprefix = None
        self._routenames = {}
        self.debug = False
        self.append_slash = False
        self.sub_domains = False
        self.sub_domains_ignore = []
        self.domain_match = '[^\.\/]+?\.[^\.\/]+'
        self.explicit = explicit
        self.encoding = 'utf-8'
        self.decode_errors = 'ignore'
        self.hardcode_names = True
        self.minimization = False
        self.create_regs_lock = threading.Lock()
        if register:
            config = request_config()
            config.mapper = self
    
    def __str__(self):
        """Generates a tabular string representation."""
        def format_methods(r):
            if r.conditions:
                method = r.conditions.get('method', '')
                return type(method) is str and method or ', '.join(method)
            else:
                return ''

        table = [('Route name', 'Methods', 'Path')] + \
                [(r.name or '', format_methods(r), r.routepath or '')
                 for r in self.matchlist]
            
        widths = [max(len(row[col]) for row in table)
                  for col in range(len(table[0]))]
        
        return '\n'.join(
            ' '.join(row[col].ljust(widths[col])
                     for col in range(len(widths)))
            for row in table)

    def _envget(self):
        try:
            return self.req_data.environ
        except AttributeError:
            return None
    def _envset(self, env):
        self.req_data.environ = env
    def _envdel(self):
        del self.req_data.environ
    environ = property(_envget, _envset, _envdel)
    
    def extend(self, routes, path_prefix=''):
        """Extends the mapper routes with a list of Route objects
        
        If a path_prefix is provided, all the routes will have their
        path prepended with the path_prefix.
        
        Example::
            
            >>> map = Mapper(controller_scan=None)
            >>> map.connect('home', '/', controller='home', action='splash')
            >>> map.matchlist[0].name == 'home'
            True
            >>> routes = [Route('index', '/index.htm', controller='home',
            ...                 action='index')]
            >>> map.extend(routes)
            >>> len(map.matchlist) == 2
            True
            >>> map.extend(routes, path_prefix='/subapp')
            >>> len(map.matchlist) == 3
            True
            >>> map.matchlist[2].routepath == '/subapp/index.htm'
            True
        
        .. note::
            
            This function does not merely extend the mapper with the
            given list of routes, it actually creates new routes with
            identical calling arguments.
        
        """
        for route in routes:
            if path_prefix and route.minimization:
                routepath = '/'.join([path_prefix, route.routepath])
            elif path_prefix:
                routepath = path_prefix + route.routepath
            else:
                routepath = route.routepath
            self.connect(route.name, routepath, **route._kargs)
                
    def connect(self, *args, **kargs):
        """Create and connect a new Route to the Mapper.
        
        Usage:
        
        .. code-block:: python
        
            m = Mapper()
            m.connect(':controller/:action/:id')
            m.connect('date/:year/:month/:day', controller="blog", action="view")
            m.connect('archives/:page', controller="blog", action="by_page",
            requirements = { 'page':'\d{1,2}' })
            m.connect('category_list', 'archives/category/:section', controller='blog', action='category',
            section='home', type='list')
            m.connect('home', '', controller='blog', action='view', section='home')
        
        """
        routename = None
        if len(args) > 1:
            routename = args[0]
        else:
            args = (None,) + args
        if '_explicit' not in kargs:
            kargs['_explicit'] = self.explicit
        if '_minimize' not in kargs:
            kargs['_minimize'] = self.minimization
        route = Route(*args, **kargs)
                
        # Apply encoding and errors if its not the defaults and the route 
        # didn't have one passed in.
        if (self.encoding != 'utf-8' or self.decode_errors != 'ignore') and \
           '_encoding' not in kargs:
            route.encoding = self.encoding
            route.decode_errors = self.decode_errors
        
        if not route.static:
            self.matchlist.append(route)
        
        if routename:
            self._routenames[routename] = route
            route.name = routename
        if route.static:
            return
        exists = False
        for key in self.maxkeys:
            if key == route.maxkeys:
                self.maxkeys[key].append(route)
                exists = True
                break
        if not exists:
            self.maxkeys[route.maxkeys] = [route]
        self._created_gens = False
    
    def _create_gens(self):
        """Create the generation hashes for route lookups"""
        # Use keys temporailly to assemble the list to avoid excessive
        # list iteration testing with "in"
        controllerlist = {}
        actionlist = {}
        
        # Assemble all the hardcoded/defaulted actions/controllers used
        for route in self.matchlist:
            if route.static:
                continue
            if route.defaults.has_key('controller'):
                controllerlist[route.defaults['controller']] = True
            if route.defaults.has_key('action'):
                actionlist[route.defaults['action']] = True
        
        # Setup the lists of all controllers/actions we'll add each route
        # to. We include the '*' in the case that a generate contains a
        # controller/action that has no hardcodes
        controllerlist = controllerlist.keys() + ['*']
        actionlist = actionlist.keys() + ['*']
        
        # Go through our list again, assemble the controllers/actions we'll
        # add each route to. If its hardcoded, we only add it to that dict key.
        # Otherwise we add it to every hardcode since it can be changed.
        gendict = {} # Our generated two-deep hash
        for route in self.matchlist:
            if route.static:
                continue
            clist = controllerlist
            alist = actionlist
            if 'controller' in route.hardcoded:
                clist = [route.defaults['controller']]
            if 'action' in route.hardcoded:
                alist = [unicode(route.defaults['action'])]
            for controller in clist:
                for action in alist:
                    actiondict = gendict.setdefault(controller, {})
                    actiondict.setdefault(action, ([], {}))[0].append(route)
        self._gendict = gendict
        self._created_gens = True

    def create_regs(self, *args, **kwargs):
        """Atomically creates regular expressions for all connected
        routes
        """
        self.create_regs_lock.acquire()
        try:
            self._create_regs(*args, **kwargs)
        finally:
            self.create_regs_lock.release()
    
    def _create_regs(self, clist=None):
        """Creates regular expressions for all connected routes"""
        if clist is None:
            if self.directory:
                clist = self.controller_scan(self.directory)
            elif callable(self.controller_scan):
                clist = self.controller_scan()
            elif not self.controller_scan:
                clist = []
            else:
                clist = self.controller_scan
        
        for key, val in self.maxkeys.iteritems():
            for route in val:
                route.makeregexp(clist)
        
        regexps = []
        routematches = []
        for route in self.matchlist:
            if not route.static:
                routematches.append(route)
                regexps.append(route.makeregexp(clist, include_names=False))
        self._routematches = routematches
        
        # Create our regexp to strip the prefix
        if self.prefix:
            self._regprefix = re.compile(self.prefix + '(.*)')
        
        # Save the master regexp
        regexp = '|'.join(['(?:%s)' % x for x in regexps])
        self._master_reg = regexp
        self._master_regexp = re.compile(regexp)
        self._created_regs = True
    
    def _match(self, url, environ):
        """Internal Route matcher
        
        Matches a URL against a route, and returns a tuple of the match
        dict and the route object if a match is successfull, otherwise
        it returns empty.
        
        For internal use only.
        
        """
        if not self._created_regs and self.controller_scan:
            self.create_regs()
        elif not self._created_regs:
            raise RoutesException("You must generate the regular expressions"
                                 " before matching.")
        
        if self.always_scan:
            self.create_regs()
        
        matchlog = []
        if self.prefix:
            if re.match(self._regprefix, url):
                url = re.sub(self._regprefix, r'\1', url)
                if not url:
                    url = '/'
            else:
                return (None, None, matchlog)
                
        environ = environ or self.environ
        sub_domains = self.sub_domains
        sub_domains_ignore = self.sub_domains_ignore
        domain_match = self.domain_match
        debug = self.debug
        
        # Check to see if its a valid url against the main regexp
        # Done for faster invalid URL elimination
        valid_url = re.match(self._master_regexp, url)
        if not valid_url:
            return (None, None, matchlog)
        
        for route in self.matchlist:
            if route.static:
                if debug:
                    matchlog.append(dict(route=route, static=True))
                continue
            match = route.match(url, environ, sub_domains, sub_domains_ignore,
                                domain_match)
            if debug:
                matchlog.append(dict(route=route, regexp=bool(match)))
            if isinstance(match, dict) or match:
                return (match, route, matchlog)
        return (None, None, matchlog)
    
    def match(self, url=None, environ=None):
        """Match a URL against against one of the routes contained.
        
        Will return None if no valid match is found.
        
        .. code-block:: python
            
            resultdict = m.match('/joe/sixpack')
        
        """
        if not url and not environ:
            raise RoutesException('URL or environ must be provided')
        
        if not url:
            url = environ['PATH_INFO']
                
        result = self._match(url, environ)
        if self.debug:
            return result[0], result[1], result[2]
        if isinstance(result[0], dict) or result[0]:
            return result[0]
        return None
    
    def routematch(self, url=None, environ=None):
        """Match a URL against against one of the routes contained.
        
        Will return None if no valid match is found, otherwise a
        result dict and a route object is returned.
        
        .. code-block:: python
        
            resultdict, route_obj = m.match('/joe/sixpack')
        
        """
        if not url and not environ:
            raise RoutesException('URL or environ must be provided')
        
        if not url:
            url = environ['PATH_INFO']
        result = self._match(url, environ)
        if self.debug:
            return result[0], result[1], result[2]
        if isinstance(result[0], dict) or result[0]:
            return result[0], result[1]
        return None
    
    def generate(self, *args, **kargs):
        """Generate a route from a set of keywords
        
        Returns the url text, or None if no URL could be generated.
        
        .. code-block:: python
            
            m.generate(controller='content',action='view',id=10)
        
        """
        # Generate ourself if we haven't already
        if not self._created_gens:
            self._create_gens()
        
        if self.append_slash:
            kargs['_append_slash'] = True
        
        if not self.explicit:
            if 'controller' not in kargs:
                kargs['controller'] = 'content'
            if 'action' not in kargs:
                kargs['action'] = 'index'
        
        environ = kargs.pop('_environ', self.environ)
        controller = kargs.get('controller', None)
        action = kargs.get('action', None)

        # If the URL didn't depend on the SCRIPT_NAME, we'll cache it
        # keyed by just by kargs; otherwise we need to cache it with
        # both SCRIPT_NAME and kargs:
        cache_key = unicode(args).encode('utf8') + \
            unicode(kargs).encode('utf8')
        
        if self.urlcache is not None:
            if self.environ:
                cache_key_script_name = '%s:%s' % (
                    environ.get('SCRIPT_NAME', ''), cache_key)
            else:
                cache_key_script_name = cache_key
        
            # Check the url cache to see if it exists, use it if it does
            for key in [cache_key, cache_key_script_name]:
                if key in self.urlcache:
                    return self.urlcache[key]
        
        actionlist = self._gendict.get(controller) or self._gendict.get('*', {})
        if not actionlist and not args:
            return None
        (keylist, sortcache) = actionlist.get(action) or \
                               actionlist.get('*', (None, {}))
        if not keylist and not args:
            return None

        keys = frozenset(kargs.keys())
        cacheset = False
        cachekey = unicode(keys)
        cachelist = sortcache.get(cachekey)
        if args:
            keylist = args
        elif cachelist:
            keylist = cachelist
        else:
            cacheset = True
            newlist = []
            for route in keylist:
                if len(route.minkeys - route.dotkeys - keys) == 0:
                    newlist.append(route)
            keylist = newlist
            
            def keysort(a, b):
                """Sorts two sets of sets, to order them ideally for
                matching."""
                am = a.minkeys
                a = a.maxkeys
                b = b.maxkeys
                
                lendiffa = len(keys^a)
                lendiffb = len(keys^b)
                # If they both match, don't switch them
                if lendiffa == 0 and lendiffb == 0:
                    return 0
                
                # First, if a matches exactly, use it
                if lendiffa == 0:
                    return -1
                
                # Or b matches exactly, use it
                if lendiffb == 0:
                    return 1
                
                # Neither matches exactly, return the one with the most in 
                # common
                if cmp(lendiffa, lendiffb) != 0:
                    return cmp(lendiffa, lendiffb)
                
                # Neither matches exactly, but if they both have just as much 
                # in common
                if len(keys&b) == len(keys&a):
                    # Then we return the shortest of the two
                    return cmp(len(a), len(b))
                
                # Otherwise, we return the one that has the most in common
                else:
                    return cmp(len(keys&b), len(keys&a))
            
            keylist.sort(keysort)
            if cacheset:
                sortcache[cachekey] = keylist
                
        # Iterate through the keylist of sorted routes (or a single route if
        # it was passed in explicitly for hardcoded named routes)
        for route in keylist:
            fail = False
            for key in route.hardcoded:
                kval = kargs.get(key)
                if not kval:
                    continue
                if isinstance(kval, str):
                    kval = kval.decode(self.encoding)
                else:
                    kval = unicode(kval)
                if kval != route.defaults[key] and not callable(route.defaults[key]):
                    fail = True
                    break
            if fail:
                continue
            path = route.generate(**kargs)
            if path:
                if self.prefix:
                    path = self.prefix + path
                external_static = route.static and route.external
                if environ and environ.get('SCRIPT_NAME', '') != ''\
                    and not route.absolute and not external_static:
                    path = environ['SCRIPT_NAME'] + path
                    key = cache_key_script_name
                else:
                    key = cache_key
                if self.urlcache is not None:
                    self.urlcache[key] = str(path)
                return str(path)
            else:
                continue
        return None
    
    def resource(self, member_name, collection_name, **kwargs):
        """Generate routes for a controller resource
        
        The member_name name should be the appropriate singular version
        of the resource given your locale and used with members of the
        collection. The collection_name name will be used to refer to
        the resource collection methods and should be a plural version
        of the member_name argument. By default, the member_name name
        will also be assumed to map to a controller you create.
        
        The concept of a web resource maps somewhat directly to 'CRUD' 
        operations. The overlying things to keep in mind is that
        mapping a resource is about handling creating, viewing, and
        editing that resource.
        
        All keyword arguments are optional.
        
        ``controller``
            If specified in the keyword args, the controller will be
            the actual controller used, but the rest of the naming
            conventions used for the route names and URL paths are
            unchanged.
        
        ``collection``
            Additional action mappings used to manipulate/view the
            entire set of resources provided by the controller.
            
            Example::
                
                map.resource('message', 'messages', collection={'rss':'GET'})
                # GET /message/rss (maps to the rss action)
                # also adds named route "rss_message"
        
        ``member``
            Additional action mappings used to access an individual
            'member' of this controllers resources.
            
            Example::
                
                map.resource('message', 'messages', member={'mark':'POST'})
                # POST /message/1/mark (maps to the mark action)
                # also adds named route "mark_message"
        
        ``new``
            Action mappings that involve dealing with a new member in
            the controller resources.
            
            Example::
                
                map.resource('message', 'messages', new={'preview':'POST'})
                # POST /message/new/preview (maps to the preview action)
                # also adds a url named "preview_new_message"
        
        ``path_prefix``
            Prepends the URL path for the Route with the path_prefix
            given. This is most useful for cases where you want to mix
            resources or relations between resources.
        
        ``name_prefix``
            Perpends the route names that are generated with the
            name_prefix given. Combined with the path_prefix option,
            it's easy to generate route names and paths that represent
            resources that are in relations.
            
            Example::
                
                map.resource('message', 'messages', controller='categories', 
                    path_prefix='/category/:category_id', 
                    name_prefix="category_")
                # GET /category/7/message/1
                # has named route "category_message"
                
        ``parent_resource`` 
            A ``dict`` containing information about the parent
            resource, for creating a nested resource. It should contain
            the ``member_name`` and ``collection_name`` of the parent
            resource. This ``dict`` will 
            be available via the associated ``Route`` object which can
            be accessed during a request via
            ``request.environ['routes.route']``
 
            If ``parent_resource`` is supplied and ``path_prefix``
            isn't, ``path_prefix`` will be generated from
            ``parent_resource`` as
            "<parent collection name>/:<parent member name>_id". 

            If ``parent_resource`` is supplied and ``name_prefix``
            isn't, ``name_prefix`` will be generated from
            ``parent_resource`` as  "<parent member name>_". 
 
            Example:: 
 
                >>> from routes.util import url_for 
                >>> m = Mapper() 
                >>> m.resource('location', 'locations', 
                ...            parent_resource=dict(member_name='region', 
                ...                                 collection_name='regions'))
                >>> # path_prefix is "regions/:region_id" 
                >>> # name prefix is "region_"  
                >>> url_for('region_locations', region_id=13) 
                '/regions/13/locations'
                >>> url_for('region_new_location', region_id=13) 
                '/regions/13/locations/new'
                >>> url_for('region_location', region_id=13, id=60) 
                '/regions/13/locations/60'
                >>> url_for('region_edit_location', region_id=13, id=60) 
                '/regions/13/locations/60/edit'

            Overriding generated ``path_prefix``::

                >>> m = Mapper()
                >>> m.resource('location', 'locations',
                ...            parent_resource=dict(member_name='region',
                ...                                 collection_name='regions'),
                ...            path_prefix='areas/:area_id')
                >>> # name prefix is "region_"
                >>> url_for('region_locations', area_id=51)
                '/areas/51/locations'

            Overriding generated ``name_prefix``::

                >>> m = Mapper()
                >>> m.resource('location', 'locations',
                ...            parent_resource=dict(member_name='region',
                ...                                 collection_name='regions'),
                ...            name_prefix='')
                >>> # path_prefix is "regions/:region_id" 
                >>> url_for('locations', region_id=51)
                '/regions/51/locations'

        """
        collection = kwargs.pop('collection', {})
        member = kwargs.pop('member', {})
        new = kwargs.pop('new', {})
        path_prefix = kwargs.pop('path_prefix', None)
        name_prefix = kwargs.pop('name_prefix', None)
        parent_resource = kwargs.pop('parent_resource', None)
        
        # Generate ``path_prefix`` if ``path_prefix`` wasn't specified and 
        # ``parent_resource`` was. Likewise for ``name_prefix``. Make sure
        # that ``path_prefix`` and ``name_prefix`` *always* take precedence if
        # they are specified--in particular, we need to be careful when they
        # are explicitly set to "".
        if parent_resource is not None: 
            if path_prefix is None: 
                path_prefix = '%s/:%s_id' % (parent_resource['collection_name'], 
                                             parent_resource['member_name']) 
            if name_prefix is None:
                name_prefix = '%s_' % parent_resource['member_name']
        else:
            if path_prefix is None: path_prefix = ''
            if name_prefix is None: name_prefix = ''
        
        # Ensure the edit and new actions are in and GET
        member['edit'] = 'GET'
        new.update({'new': 'GET'})
        
        # Make new dict's based off the old, except the old values become keys,
        # and the old keys become items in a list as the value
        def swap(dct, newdct):
            """Swap the keys and values in the dict, and uppercase the values
            from the dict during the swap."""
            for key, val in dct.iteritems():
                newdct.setdefault(val.upper(), []).append(key)
            return newdct
        collection_methods = swap(collection, {})
        member_methods = swap(member, {})
        new_methods = swap(new, {})
        
        # Insert create, update, and destroy methods
        collection_methods.setdefault('POST', []).insert(0, 'create')
        member_methods.setdefault('PUT', []).insert(0, 'update')
        member_methods.setdefault('DELETE', []).insert(0, 'delete')
        
        # If there's a path prefix option, use it with the controller
        controller = strip_slashes(collection_name)
        path_prefix = strip_slashes(path_prefix)
        path_prefix = '/' + path_prefix
        if path_prefix and path_prefix != '/':
            path = path_prefix + '/' + controller
        else:
            path = '/' + controller
        collection_path = path
        new_path = path + "/new"
        member_path = path + "/:(id)"
        
        options = { 
            'controller': kwargs.get('controller', controller),
            '_member_name': member_name,
            '_collection_name': collection_name,
            '_parent_resource': parent_resource,
            '_filter': kwargs.get('_filter')
        }
        
        def requirements_for(meth):
            """Returns a new dict to be used for all route creation as the
            route options"""
            opts = options.copy()
            if method != 'any': 
                opts['conditions'] = {'method':[meth.upper()]}
            return opts
        
        # Add the routes for handling collection methods
        for method, lst in collection_methods.iteritems():
            primary = (method != 'GET' and lst.pop(0)) or None
            route_options = requirements_for(method)
            for action in lst:
                route_options['action'] = action
                route_name = "%s%s_%s" % (name_prefix, action, collection_name)
                self.connect("formatted_" + route_name, "%s/%s.:(format)" % \
                             (collection_path, action), **route_options)
                self.connect(route_name, "%s/%s" % (collection_path, action),
                                                    **route_options)
            if primary:
                route_options['action'] = primary
                self.connect("%s.:(format)" % collection_path, **route_options)
                self.connect(collection_path, **route_options)
        
        # Specifically add in the built-in 'index' collection method and its 
        # formatted version
        self.connect("formatted_" + name_prefix + collection_name, 
            collection_path + ".:(format)", action='index', 
            conditions={'method':['GET']}, **options)
        self.connect(name_prefix + collection_name, collection_path, 
                     action='index', conditions={'method':['GET']}, **options)
        
        # Add the routes that deal with new resource methods
        for method, lst in new_methods.iteritems():
            route_options = requirements_for(method)
            for action in lst:
                path = (action == 'new' and new_path) or "%s/%s" % (new_path, 
                                                                    action)
                name = "new_" + member_name
                if action != 'new':
                    name = action + "_" + name
                route_options['action'] = action
                formatted_path = (action == 'new' and new_path + '.:(format)') or \
                    "%s/%s.:(format)" % (new_path, action)
                self.connect("formatted_" + name_prefix + name, formatted_path, 
                             **route_options)
                self.connect(name_prefix + name, path, **route_options)
        
        requirements_regexp = '[^\/]+'

        # Add the routes that deal with member methods of a resource
        for method, lst in member_methods.iteritems():
            route_options = requirements_for(method)
            route_options['requirements'] = {'id':requirements_regexp}
            if method not in ['POST', 'GET', 'any']:
                primary = lst.pop(0)
            else:
                primary = None
            for action in lst:
                route_options['action'] = action
                self.connect("formatted_%s%s_%s" % (name_prefix, action, 
                                                    member_name),
                    "%s/%s.:(format)" % (member_path, action), **route_options)
                self.connect("%s%s_%s" % (name_prefix, action, member_name),
                    "%s/%s" % (member_path, action), **route_options)
            if primary:
                route_options['action'] = primary
                self.connect("%s.:(format)" % member_path, **route_options)
                self.connect(member_path, **route_options)
        
        # Specifically add the member 'show' method
        route_options = requirements_for('GET')
        route_options['action'] = 'show'
        route_options['requirements'] = {'id':requirements_regexp}
        self.connect("formatted_" + name_prefix + member_name, 
                     member_path + ".:(format)", **route_options)
        self.connect(name_prefix + member_name, member_path, **route_options)
    
    def redirect(self, match_path, destination_path, *args, **kwargs):
        """Add a redirect route to the mapper
        
        Redirect routes bypass the wrapped WSGI application and instead
        result in a redirect being issued by the RoutesMiddleware. As
        such, this method is only meaningful when using
        RoutesMiddleware.
        
        By default, a 302 Found status code is used, this can be
        changed by providing a ``_redirect_code`` keyword argument
        which will then be used instead. Note that the entire status
        code string needs to be present.
        
        When using keyword arguments, all arguments that apply to
        matching will be used for the match, while generation specific
        options will be used during generation. Thus all options
        normally available to connected Routes may be used with
        redirect routes as well.
        
        Example::
            
            map = Mapper()
            map.redirect('/legacyapp/archives/{url:.*}, '/archives/{url})
            map.redirect('/home/index', '/', _redirect_code='301 Moved Permanently')
        
        """
        both_args = ['_encoding', '_explicit', '_minimize']
        gen_args = ['_filter']
        
        status_code = kwargs.pop('_redirect_code', '302 Found')
        gen_dict, match_dict = {}, {}
        
        # Create the dict of args for the generation route
        for key in both_args + gen_args:
            if key in kwargs:
                gen_dict[key] = kwargs[key]
        gen_dict['_static'] = True
        
        # Create the dict of args for the matching route
        for key in kwargs:
            if key not in gen_args:
                match_dict[key] = kwargs[key]
        
        self.connect(match_path, **match_dict)
        match_route = self.matchlist[-1]
        
        self.connect('_redirect_%s' % id(match_route), destination_path,
                     **gen_dict)
        match_route.redirect = True
        match_route.redirect_status = status_code
