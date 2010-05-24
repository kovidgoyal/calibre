"""Provides common classes and functions most users will want access to."""
import threading, sys

class _RequestConfig(object):
    """
    RequestConfig thread-local singleton
    
    The Routes RequestConfig object is a thread-local singleton that should 
    be initialized by the web framework that is utilizing Routes.
    """
    __shared_state = threading.local()
    
    def __getattr__(self, name):
        return getattr(self.__shared_state, name)

    def __setattr__(self, name, value):
        """
        If the name is environ, load the wsgi envion with load_wsgi_environ
        and set the environ
        """
        if name == 'environ':
            self.load_wsgi_environ(value)
            return self.__shared_state.__setattr__(name, value)
        return self.__shared_state.__setattr__(name, value)
    
    def __delattr__(self, name):
        delattr(self.__shared_state, name)
    
    def load_wsgi_environ(self, environ):
        """
        Load the protocol/server info from the environ and store it.
        Also, match the incoming URL if there's already a mapper, and
        store the resulting match dict in mapper_dict.
        """
        if 'HTTPS' in environ or environ.get('wsgi.url_scheme') == 'https' \
           or environ.get('HTTP_X_FORWARDED_PROTO') == 'https':
            self.__shared_state.protocol = 'https'
        else:
            self.__shared_state.protocol = 'http'
        try:
            self.mapper.environ = environ
        except AttributeError:
            pass
        
        # Wrap in try/except as common case is that there is a mapper
        # attached to self
        try:
            if 'PATH_INFO' in environ:
                mapper = self.mapper
                path = environ['PATH_INFO']
                result = mapper.routematch(path)
                if result is not None:
                    self.__shared_state.mapper_dict = result[0]
                    self.__shared_state.route = result[1]
                else:
                    self.__shared_state.mapper_dict = None
                    self.__shared_state.route = None
        except AttributeError:
            pass
        
        if 'HTTP_X_FORWARDED_HOST' in environ:
            self.__shared_state.host = environ['HTTP_X_FORWARDED_HOST']
        elif 'HTTP_HOST' in environ:
            self.__shared_state.host = environ['HTTP_HOST']
        else:
            self.__shared_state.host = environ['SERVER_NAME']
            if environ['wsgi.url_scheme'] == 'https':
                if environ['SERVER_PORT'] != '443':
                    self.__shared_state.host += ':' + environ['SERVER_PORT']
            else:
                if environ['SERVER_PORT'] != '80':
                    self.__shared_state.host += ':' + environ['SERVER_PORT']

def request_config(original=False):
    """
    Returns the Routes RequestConfig object.
    
    To get the Routes RequestConfig:
    
    >>> from routes import *
    >>> config = request_config()
    
    The following attributes must be set on the config object every request:
    
    mapper
        mapper should be a Mapper instance thats ready for use
    host
        host is the hostname of the webapp
    protocol
        protocol is the protocol of the current request
    mapper_dict
        mapper_dict should be the dict returned by mapper.match()
    redirect
        redirect should be a function that issues a redirect, 
        and takes a url as the sole argument
    prefix (optional)
        Set if the application is moved under a URL prefix. Prefix
        will be stripped before matching, and prepended on generation
    environ (optional)
        Set to the WSGI environ for automatic prefix support if the
        webapp is underneath a 'SCRIPT_NAME'
        
        Setting the environ will use information in environ to try and
        populate the host/protocol/mapper_dict options if you've already
        set a mapper.
    
    **Using your own requst local**
    
    If you have your own request local object that you'd like to use instead 
    of the default thread local provided by Routes, you can configure Routes 
    to use it::
        
        from routes import request_config()
        config = request_config()
        if hasattr(config, 'using_request_local'):
            config.request_local = YourLocalCallable
            config = request_config()
    
    Once you have configured request_config, its advisable you retrieve it 
    again to get the object you wanted. The variable you assign to 
    request_local is assumed to be a callable that will get the local config 
    object you wish.
    
    This example tests for the presence of the 'using_request_local' attribute
    which will be present if you haven't assigned it yet. This way you can 
    avoid repeat assignments of the request specific callable.
    
    Should you want the original object, perhaps to change the callable its 
    using or stop this behavior, call request_config(original=True).
    """
    obj = _RequestConfig()
    try:
        if obj.request_local and original is False:
            return getattr(obj, 'request_local')()
    except AttributeError:
        obj.request_local = False
        obj.using_request_local = False
    return _RequestConfig()
    
from routes.mapper import Mapper
from routes.util import redirect_to, url_for, URLGenerator
__all__=['Mapper', 'url_for', 'URLGenerator', 'redirect_to', 'request_config']
