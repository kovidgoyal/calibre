"""Configuration system for CherryPy.

Configuration in CherryPy is implemented via dictionaries. Keys are strings
which name the mapped value, which may be of any type.


Architecture
------------

CherryPy Requests are part of an Application, which runs in a global context,
and configuration data may apply to any of those three scopes:

    Global: configuration entries which apply everywhere are stored in
    cherrypy.config.
    
    Application: entries which apply to each mounted application are stored
    on the Application object itself, as 'app.config'. This is a two-level
    dict where each key is a path, or "relative URL" (for example, "/" or
    "/path/to/my/page"), and each value is a config dict. Usually, this
    data is provided in the call to tree.mount(root(), config=conf),
    although you may also use app.merge(conf).
    
    Request: each Request object possesses a single 'Request.config' dict.
    Early in the request process, this dict is populated by merging global
    config entries, Application entries (whose path equals or is a parent
    of Request.path_info), and any config acquired while looking up the
    page handler (see next).


Declaration
-----------

Configuration data may be supplied as a Python dictionary, as a filename,
or as an open file object. When you supply a filename or file, CherryPy
uses Python's builtin ConfigParser; you declare Application config by
writing each path as a section header:

    [/path/to/my/page]
    request.stream = True

To declare global configuration entries, place them in a [global] section.

You may also declare config entries directly on the classes and methods
(page handlers) that make up your CherryPy application via the '_cp_config'
attribute. For example:

    class Demo:
        _cp_config = {'tools.gzip.on': True}
        
        def index(self):
            return "Hello world"
        index.exposed = True
        index._cp_config = {'request.show_tracebacks': False}

Note, however, that this behavior is only guaranteed for the default
dispatcher. Other dispatchers may have different restrictions on where
you can attach _cp_config attributes.


Namespaces
----------

Configuration keys are separated into namespaces by the first "." in the key.
Current namespaces:

    engine:     Controls the 'application engine', including autoreload.
                These can only be declared in the global config.
    tree:       Grafts cherrypy.Application objects onto cherrypy.tree.
                These can only be declared in the global config.
    hooks:      Declares additional request-processing functions.
    log:        Configures the logging for each application.
                These can only be declared in the global or / config.
    request:    Adds attributes to each Request.
    response:   Adds attributes to each Response.
    server:     Controls the default HTTP server via cherrypy.server.
                These can only be declared in the global config.
    tools:      Runs and configures additional request-processing packages.
    wsgi:       Adds WSGI middleware to an Application's "pipeline".
                These can only be declared in the app's root config ("/").
    checker:    Controls the 'checker', which looks for common errors in
                app state (including config) when the engine starts.
                Global config only.

The only key that does not exist in a namespace is the "environment" entry.
This special entry 'imports' other config entries from a template stored in
cherrypy._cpconfig.environments[environment]. It only applies to the global
config, and only when you use cherrypy.config.update.

You can define your own namespaces to be called at the Global, Application,
or Request level, by adding a named handler to cherrypy.config.namespaces,
app.namespaces, or app.request_class.namespaces. The name can
be any string, and the handler must be either a callable or a (Python 2.5
style) context manager.
"""

import ConfigParser
try:
    set
except NameError:
    from sets import Set as set
import sys

import cherrypy


environments = {
    "staging": {
        'engine.autoreload_on': False,
        'checker.on': False,
        'tools.log_headers.on': False,
        'request.show_tracebacks': False,
        },
    "production": {
        'engine.autoreload_on': False,
        'checker.on': False,
        'tools.log_headers.on': False,
        'request.show_tracebacks': False,
        'log.screen': False,
        },
    "embedded": {
        # For use with CherryPy embedded in another deployment stack.
        'engine.autoreload_on': False,
        'checker.on': False,
        'tools.log_headers.on': False,
        'request.show_tracebacks': False,
        'log.screen': False,
        'engine.SIGHUP': None,
        'engine.SIGTERM': None,
        },
    "test_suite": {
        'engine.autoreload_on': False,
        'checker.on': False,
        'tools.log_headers.on': False,
        'request.show_tracebacks': True,
        'log.screen': False,
        },
    }

def as_dict(config):
    """Return a dict from 'config' whether it is a dict, file, or filename."""
    if isinstance(config, basestring):
        config = _Parser().dict_from_file(config)
    elif hasattr(config, 'read'):
        config = _Parser().dict_from_file(config)
    return config

def merge(base, other):
    """Merge one app config (from a dict, file, or filename) into another.
    
    If the given config is a filename, it will be appended to
    the list of files to monitor for "autoreload" changes.
    """
    if isinstance(other, basestring):
        cherrypy.engine.autoreload.files.add(other)
    
    # Load other into base
    for section, value_map in as_dict(other).iteritems():
        base.setdefault(section, {}).update(value_map)


class NamespaceSet(dict):
    """A dict of config namespace names and handlers.
    
    Each config entry should begin with a namespace name; the corresponding
    namespace handler will be called once for each config entry in that
    namespace, and will be passed two arguments: the config key (with the
    namespace removed) and the config value.
    
    Namespace handlers may be any Python callable; they may also be
    Python 2.5-style 'context managers', in which case their __enter__
    method should return a callable to be used as the handler.
    See cherrypy.tools (the Toolbox class) for an example.
    """
    
    def __call__(self, config):
        """Iterate through config and pass it to each namespace handler.
        
        'config' should be a flat dict, where keys use dots to separate
        namespaces, and values are arbitrary.
        
        The first name in each config key is used to look up the corresponding
        namespace handler. For example, a config entry of {'tools.gzip.on': v}
        will call the 'tools' namespace handler with the args: ('gzip.on', v)
        """
        # Separate the given config into namespaces
        ns_confs = {}
        for k in config:
            if "." in k:
                ns, name = k.split(".", 1)
                bucket = ns_confs.setdefault(ns, {})
                bucket[name] = config[k]
        
        # I chose __enter__ and __exit__ so someday this could be
        # rewritten using Python 2.5's 'with' statement:
        # for ns, handler in self.iteritems():
        #     with handler as callable:
        #         for k, v in ns_confs.get(ns, {}).iteritems():
        #             callable(k, v)
        for ns, handler in self.iteritems():
            exit = getattr(handler, "__exit__", None)
            if exit:
                callable = handler.__enter__()
                no_exc = True
                try:
                    try:
                        for k, v in ns_confs.get(ns, {}).iteritems():
                            callable(k, v)
                    except:
                        # The exceptional case is handled here
                        no_exc = False
                        if exit is None:
                            raise
                        if not exit(*sys.exc_info()):
                            raise
                        # The exception is swallowed if exit() returns true
                finally:
                    # The normal and non-local-goto cases are handled here
                    if no_exc and exit:
                        exit(None, None, None)
            else:
                for k, v in ns_confs.get(ns, {}).iteritems():
                    handler(k, v)
    
    def __repr__(self):
        return "%s.%s(%s)" % (self.__module__, self.__class__.__name__,
                              dict.__repr__(self))
    
    def __copy__(self):
        newobj = self.__class__()
        newobj.update(self)
        return newobj
    copy = __copy__


class Config(dict):
    """The 'global' configuration data for the entire CherryPy process."""
    
    defaults = {
        'tools.log_tracebacks.on': True,
        'tools.log_headers.on': True,
        'tools.trailing_slash.on': True,
        }
    
    namespaces = NamespaceSet(
        **{"server": lambda k, v: setattr(cherrypy.server, k, v),
           "log": lambda k, v: setattr(cherrypy.log, k, v),
           "checker": lambda k, v: setattr(cherrypy.checker, k, v),
           })
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        """Reset self to default values."""
        self.clear()
        dict.update(self, self.defaults)
    
    def update(self, config):
        """Update self from a dict, file or filename."""
        if isinstance(config, basestring):
            # Filename
            cherrypy.engine.autoreload.files.add(config)
            config = _Parser().dict_from_file(config)
        elif hasattr(config, 'read'):
            # Open file object
            config = _Parser().dict_from_file(config)
        else:
            config = config.copy()
        
        if isinstance(config.get("global", None), dict):
            if len(config) > 1:
                cherrypy.checker.global_config_contained_paths = True
            config = config["global"]
        
        which_env = config.get('environment')
        if which_env:
            env = environments[which_env]
            for k in env:
                if k not in config:
                    config[k] = env[k]
        
        if 'tools.staticdir.dir' in config:
            config['tools.staticdir.section'] = "global"
        
        dict.update(self, config)
        self.namespaces(config)
    
    def __setitem__(self, k, v):
        dict.__setitem__(self, k, v)
        self.namespaces({k: v})


def _engine_namespace_handler(k, v):
    """Backward compatibility handler for the "engine" namespace."""
    engine = cherrypy.engine
    if k == 'autoreload_on':
        if v:
            engine.autoreload.subscribe()
        else:
            engine.autoreload.unsubscribe()
    elif k == 'autoreload_frequency':
        engine.autoreload.frequency = v
    elif k == 'autoreload_match':
        engine.autoreload.match = v
    elif k == 'reload_files':
        engine.autoreload.files = v
    elif k == 'deadlock_poll_freq':
        engine.timeout_monitor.frequency = v
    elif k == 'SIGHUP':
        engine.listeners['SIGHUP'] = set([v])
    elif k == 'SIGTERM':
        engine.listeners['SIGTERM'] = set([v])
Config.namespaces["engine"] = _engine_namespace_handler


def _tree_namespace_handler(k, v):
    """Namespace handler for the 'tree' config namespace."""
    cherrypy.tree.graft(v, v.script_name)
    cherrypy.engine.log("Mounted: %s on %s" % (v, v.script_name or "/"))
Config.namespaces["tree"] = _tree_namespace_handler


class _Parser(ConfigParser.ConfigParser):
    """Sub-class of ConfigParser that keeps the case of options and that raises
    an exception if the file cannot be read.
    """
    
    def optionxform(self, optionstr):
        return optionstr
    
    def read(self, filenames):
        if isinstance(filenames, basestring):
            filenames = [filenames]
        for filename in filenames:
            # try:
            #     fp = open(filename)
            # except IOError:
            #     continue
            fp = open(filename)
            try:
                self._read(fp, filename)
            finally:
                fp.close()
    
    def as_dict(self, raw=False, vars=None):
        """Convert an INI file to a dictionary"""
        # Load INI file into a dict
        from cherrypy.lib import unrepr
        result = {}
        for section in self.sections():
            if section not in result:
                result[section] = {}
            for option in self.options(section):
                value = self.get(section, option, raw, vars)
                try:
                    value = unrepr(value)
                except Exception, x:
                    msg = ("Config error in section: %r, option: %r, "
                           "value: %r. Config values must be valid Python." %
                           (section, option, value))
                    raise ValueError(msg, x.__class__.__name__, x.args)
                result[section][option] = value
        return result
    
    def dict_from_file(self, file):
        if hasattr(file, 'read'):
            self.readfp(file)
        else:
            self.read(file)
        return self.as_dict()

del ConfigParser
