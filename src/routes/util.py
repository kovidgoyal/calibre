"""Utility functions for use in templates / controllers

*PLEASE NOTE*: Many of these functions expect an initialized RequestConfig
object. This is expected to have been initialized for EACH REQUEST by the web
framework.

"""
import os
import re
import urllib
from routes import request_config


class RoutesException(Exception):
    """Tossed during Route exceptions"""


class MatchException(RoutesException):
    """Tossed during URL matching exceptions"""


class GenerationException(RoutesException):
    """Tossed during URL generation exceptions"""


def _screenargs(kargs, mapper, environ, force_explicit=False):
    """
    Private function that takes a dict, and screens it against the current 
    request dict to determine what the dict should look like that is used. 
    This is responsible for the requests "memory" of the current.
    """
    # Coerce any unicode args with the encoding
    encoding = mapper.encoding
    for key, val in kargs.iteritems():
        if isinstance(val, unicode):
            kargs[key] = val.encode(encoding)
    
    if mapper.explicit and mapper.sub_domains and not force_explicit:
        return _subdomain_check(kargs, mapper, environ)
    elif mapper.explicit and not force_explicit:
        return kargs
    
    controller_name = kargs.get('controller')
    
    if controller_name and controller_name.startswith('/'):
        # If the controller name starts with '/', ignore route memory
        kargs['controller'] = kargs['controller'][1:]
        return kargs
    elif controller_name and not kargs.has_key('action'):
        # Fill in an action if we don't have one, but have a controller
        kargs['action'] = 'index'
    
    route_args = environ.get('wsgiorg.routing_args')
    if route_args:
        memory_kargs = route_args[1].copy()
    else:
        memory_kargs = {}
     
    # Remove keys from memory and kargs if kargs has them as None
    for key in [key for key in kargs.keys() if kargs[key] is None]:
        del kargs[key]
        if memory_kargs.has_key(key):
            del memory_kargs[key]
    
    # Merge the new args on top of the memory args
    memory_kargs.update(kargs)
    
    # Setup a sub-domain if applicable
    if mapper.sub_domains:
        memory_kargs = _subdomain_check(memory_kargs, mapper, environ)
    return memory_kargs


def _subdomain_check(kargs, mapper, environ):
    """Screen the kargs for a subdomain and alter it appropriately depending
    on the current subdomain or lack therof."""
    if mapper.sub_domains:
        subdomain = kargs.pop('sub_domain', None)
        if isinstance(subdomain, unicode):
            subdomain = str(subdomain)
        
        fullhost = environ.get('HTTP_HOST') or environ.get('SERVER_NAME')
        
        # In case environ defaulted to {}
        if not fullhost:
            return kargs
        
        hostmatch = fullhost.split(':')
        host = hostmatch[0]
        port = ''
        if len(hostmatch) > 1:
            port += ':' + hostmatch[1]
        sub_match = re.compile('^.+?\.(%s)$' % mapper.domain_match)
        domain = re.sub(sub_match, r'\1', host)
        if subdomain and not host.startswith(subdomain) and \
            subdomain not in mapper.sub_domains_ignore:
            kargs['_host'] = subdomain + '.' + domain + port
        elif (subdomain in mapper.sub_domains_ignore or \
            subdomain is None) and domain != host:
            kargs['_host'] = domain + port
        return kargs
    else:
        return kargs


def _url_quote(string, encoding):
    """A Unicode handling version of urllib.quote."""
    if encoding:
        if isinstance(string, unicode):
            s = string.encode(encoding)
        elif isinstance(string, str):
            # assume the encoding is already correct
            s = string
        else:
            s = unicode(string).encode(encoding)
    else:
        s = str(string)
    return urllib.quote(s, '/')


def _str_encode(string, encoding):
    if encoding:
        if isinstance(string, unicode):
            s = string.encode(encoding)
        elif isinstance(string, str):
            # assume the encoding is already correct
            s = string
        else:
            s = unicode(string).encode(encoding)
    return s


def url_for(*args, **kargs):
    """Generates a URL 
    
    All keys given to url_for are sent to the Routes Mapper instance for 
    generation except for::
        
        anchor          specified the anchor name to be appened to the path
        host            overrides the default (current) host if provided
        protocol        overrides the default (current) protocol if provided
        qualified       creates the URL with the host/port information as 
                        needed
        
    The URL is generated based on the rest of the keys. When generating a new 
    URL, values will be used from the current request's parameters (if 
    present). The following rules are used to determine when and how to keep 
    the current requests parameters:
    
    * If the controller is present and begins with '/', no defaults are used
    * If the controller is changed, action is set to 'index' unless otherwise 
      specified
    
    For example, if the current request yielded a dict of
    {'controller': 'blog', 'action': 'view', 'id': 2}, with the standard 
    ':controller/:action/:id' route, you'd get the following results::
    
        url_for(id=4)                    =>  '/blog/view/4',
        url_for(controller='/admin')     =>  '/admin',
        url_for(controller='admin')      =>  '/admin/view/2'
        url_for(action='edit')           =>  '/blog/edit/2',
        url_for(action='list', id=None)  =>  '/blog/list'
    
    **Static and Named Routes**
    
    If there is a string present as the first argument, a lookup is done 
    against the named routes table to see if there's any matching routes. The
    keyword defaults used with static routes will be sent in as GET query 
    arg's if a route matches.
    
    If no route by that name is found, the string is assumed to be a raw URL. 
    Should the raw URL begin with ``/`` then appropriate SCRIPT_NAME data will
    be added if present, otherwise the string will be used as the url with 
    keyword args becoming GET query args.
    
    """
    anchor = kargs.get('anchor')
    host = kargs.get('host')
    protocol = kargs.get('protocol')
    qualified = kargs.pop('qualified', None)
    
    # Remove special words from kargs, convert placeholders
    for key in ['anchor', 'host', 'protocol']:
        if kargs.get(key):
            del kargs[key]
    config = request_config()
    route = None
    static = False
    encoding = config.mapper.encoding
    url = ''
    if len(args) > 0:
        route = config.mapper._routenames.get(args[0])
        
        # No named route found, assume the argument is a relative path
        if not route:
            static = True
            url = args[0]
        
        if url.startswith('/') and hasattr(config, 'environ') \
                and config.environ.get('SCRIPT_NAME'):
            url = config.environ.get('SCRIPT_NAME') + url
        
        if static:
            if kargs:
                url += '?'
                query_args = []
                for key, val in kargs.iteritems():
                    if isinstance(val, (list, tuple)):
                        for value in val:
                            query_args.append("%s=%s" % (
                                urllib.quote(unicode(key).encode(encoding)),
                                urllib.quote(unicode(value).encode(encoding))))
                    else:
                        query_args.append("%s=%s" % (
                            urllib.quote(unicode(key).encode(encoding)),
                            urllib.quote(unicode(val).encode(encoding))))
                url += '&'.join(query_args)
    environ = getattr(config, 'environ', {})
    if 'wsgiorg.routing_args' not in environ:
        environ = environ.copy()
        mapper_dict = getattr(config, 'mapper_dict', None)
        if mapper_dict is not None:
            match_dict = mapper_dict.copy()
        else:
            match_dict = {}
        environ['wsgiorg.routing_args'] = ((), match_dict)
    
    if not static:
        route_args = []
        if route:
            if config.mapper.hardcode_names:
                route_args.append(route)
            newargs = route.defaults.copy()
            newargs.update(kargs)
            
            # If this route has a filter, apply it
            if route.filter:
                newargs = route.filter(newargs)
            
            if not route.static:
                # Handle sub-domains
                newargs = _subdomain_check(newargs, config.mapper, environ)
        else:
            newargs = _screenargs(kargs, config.mapper, environ)
        anchor = newargs.pop('_anchor', None) or anchor
        host = newargs.pop('_host', None) or host
        protocol = newargs.pop('_protocol', None) or protocol
        url = config.mapper.generate(*route_args, **newargs)
    if anchor is not None:
        url += '#' + _url_quote(anchor, encoding)
    if host or protocol or qualified:
        if not host and not qualified:
            # Ensure we don't use a specific port, as changing the protocol
            # means that we most likely need a new port
            host = config.host.split(':')[0]
        elif not host:
            host = config.host
        if not protocol:
            protocol = config.protocol
        if url is not None:
            url = protocol + '://' + host + url
    
    if not isinstance(url, str) and url is not None:
        raise GenerationException("url_for can only return a string, got "
                        "unicode instead: %s" % url)
    if url is None:
        raise GenerationException(
            "url_for could not generate URL. Called with args: %s %s" % \
            (args, kargs))
    return url


class URLGenerator(object):
    """The URL Generator generates URL's
    
    It is automatically instantiated by the RoutesMiddleware and put
    into the ``wsgiorg.routing_args`` tuple accessible as::
    
        url = environ['wsgiorg.routing_args'][0][0]
    
    Or via the ``routes.url`` key::
    
        url = environ['routes.url']
    
    The url object may be instantiated outside of a web context for use
    in testing, however sub_domain support and fully qualified URL's
    cannot be generated without supplying a dict that must contain the
    key ``HTTP_HOST``.
    
    """
    def __init__(self, mapper, environ):
        """Instantiate the URLGenerator
        
        ``mapper``
            The mapper object to use when generating routes.
        ``environ``
            The environment dict used in WSGI, alternately, any dict
            that contains at least an ``HTTP_HOST`` value.
        
        """
        self.mapper = mapper
        if 'SCRIPT_NAME' not in environ:
            environ['SCRIPT_NAME'] = ''
        self.environ = environ
    
    def __call__(self, *args, **kargs):
        """Generates a URL 

        All keys given to url_for are sent to the Routes Mapper instance for 
        generation except for::

            anchor          specified the anchor name to be appened to the path
            host            overrides the default (current) host if provided
            protocol        overrides the default (current) protocol if provided
            qualified       creates the URL with the host/port information as 
                            needed

        """
        anchor = kargs.get('anchor')
        host = kargs.get('host')
        protocol = kargs.get('protocol')
        qualified = kargs.pop('qualified', None)

        # Remove special words from kargs, convert placeholders
        for key in ['anchor', 'host', 'protocol']:
            if kargs.get(key):
                del kargs[key]
        
        route = None
        use_current = '_use_current' in kargs and kargs.pop('_use_current')
        
        static = False
        encoding = self.mapper.encoding
        url = ''
                
        more_args = len(args) > 0
        if more_args:
            route = self.mapper._routenames.get(args[0])
        
        if not route and more_args:
            static = True
            url = args[0]
            if url.startswith('/') and self.environ.get('SCRIPT_NAME'):
                url = self.environ.get('SCRIPT_NAME') + url

            if static:
                if kargs:
                    url += '?'
                    query_args = []
                    for key, val in kargs.iteritems():
                        if isinstance(val, (list, tuple)):
                            for value in val:
                                query_args.append("%s=%s" % (
                                    urllib.quote(unicode(key).encode(encoding)),
                                    urllib.quote(unicode(value).encode(encoding))))
                        else:
                            query_args.append("%s=%s" % (
                                urllib.quote(unicode(key).encode(encoding)),
                                urllib.quote(unicode(val).encode(encoding))))
                    url += '&'.join(query_args)
        if not static:
            route_args = []
            if route:
                if self.mapper.hardcode_names:
                    route_args.append(route)
                newargs = route.defaults.copy()
                newargs.update(kargs)
                
                # If this route has a filter, apply it
                if route.filter:
                    newargs = route.filter(newargs)
                if not route.static or (route.static and not route.external):
                    # Handle sub-domains, retain sub_domain if there is one
                    sub = newargs.get('sub_domain', None)
                    newargs = _subdomain_check(newargs, self.mapper,
                                               self.environ)
                    # If the route requires a sub-domain, and we have it, restore
                    # it
                    if 'sub_domain' in route.defaults:
                        newargs['sub_domain'] = sub
                    
            elif use_current:
                newargs = _screenargs(kargs, self.mapper, self.environ, force_explicit=True)
            elif 'sub_domain' in kargs:
                newargs = _subdomain_check(kargs, self.mapper, self.environ)
            else:
                newargs = kargs
            
            anchor = anchor or newargs.pop('_anchor', None)
            host = host or newargs.pop('_host', None)
            protocol = protocol or newargs.pop('_protocol', None)
            url = self.mapper.generate(*route_args, **newargs)
        if anchor is not None:
            url += '#' + _url_quote(anchor, encoding)
        if host or protocol or qualified:
            if 'routes.cached_hostinfo' not in self.environ:
                cache_hostinfo(self.environ)
            hostinfo = self.environ['routes.cached_hostinfo']
            
            if not host and not qualified:
                # Ensure we don't use a specific port, as changing the protocol
                # means that we most likely need a new port
                host = hostinfo['host'].split(':')[0]
            elif not host:
                host = hostinfo['host']
            if not protocol:
                protocol = hostinfo['protocol']
            if url is not None:
                if host[-1] != '/':
                    host += '/'
                url = protocol + '://' + host + url.lstrip('/')

        if not isinstance(url, str) and url is not None:
            raise GenerationException("Can only return a string, got "
                            "unicode instead: %s" % url)
        if url is None:
            raise GenerationException(
                "Could not generate URL. Called with args: %s %s" % \
                (args, kargs))
        return url
    
    def current(self, *args, **kwargs):
        """Generate a route that includes params used on the current
        request
        
        The arguments for this method are identical to ``__call__``
        except that arguments set to None will remove existing route
        matches of the same name from the set of arguments used to
        construct a URL.
        """
        return self(_use_current=True, *args, **kwargs)


def redirect_to(*args, **kargs):
    """Issues a redirect based on the arguments. 
    
    Redirect's *should* occur as a "302 Moved" header, however the web 
    framework may utilize a different method.
    
    All arguments are passed to url_for to retrieve the appropriate URL, then
    the resulting URL it sent to the redirect function as the URL.
    """
    target = url_for(*args, **kargs)
    config = request_config()
    return config.redirect(target)


def cache_hostinfo(environ):
    """Processes the host information and stores a copy
    
    This work was previously done but wasn't stored in environ, nor is
    it guaranteed to be setup in the future (Routes 2 and beyond).
    
    cache_hostinfo processes environ keys that may be present to
    determine the proper host, protocol, and port information to use
    when generating routes.
    
    """
    hostinfo = {}
    if environ.get('HTTPS') or environ.get('wsgi.url_scheme') == 'https' \
       or environ.get('HTTP_X_FORWARDED_PROTO') == 'https':
        hostinfo['protocol'] = 'https'
    else:
        hostinfo['protocol'] = 'http'
    if environ.get('HTTP_X_FORWARDED_HOST'):
        hostinfo['host'] = environ['HTTP_X_FORWARDED_HOST']
    elif environ.get('HTTP_HOST'):
        hostinfo['host'] = environ['HTTP_HOST']
    else:
        hostinfo['host'] = environ['SERVER_NAME']
        if environ.get('wsgi.url_scheme') == 'https':
            if environ['SERVER_PORT'] != '443':
                hostinfo['host'] += ':' + environ['SERVER_PORT']
        else:
            if environ['SERVER_PORT'] != '80':
                hostinfo['host'] += ':' + environ['SERVER_PORT']
    environ['routes.cached_hostinfo'] = hostinfo
    return hostinfo


def controller_scan(directory=None):
    """Scan a directory for python files and use them as controllers"""
    if directory is None:
        return []
    
    def find_controllers(dirname, prefix=''):
        """Locate controllers in a directory"""
        controllers = []
        for fname in os.listdir(dirname):
            filename = os.path.join(dirname, fname)
            if os.path.isfile(filename) and \
                re.match('^[^_]{1,1}.*\.py$', fname):
                controllers.append(prefix + fname[:-3])
            elif os.path.isdir(filename):
                controllers.extend(find_controllers(filename, 
                                                    prefix=prefix+fname+'/'))
        return controllers
    def longest_first(fst, lst):
        """Compare the length of one string to another, shortest goes first"""
        return cmp(len(lst), len(fst))
    controllers = find_controllers(directory)
    controllers.sort(longest_first)
    return controllers
