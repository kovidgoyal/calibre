import os
import warnings

import cherrypy


class Checker(object):
    """A checker for CherryPy sites and their mounted applications.
    
    on: set this to False to turn off the checker completely.
    
    When this object is called at engine startup, it executes each
    of its own methods whose names start with "check_". If you wish
    to disable selected checks, simply add a line in your global
    config which sets the appropriate method to False:
    
    [global]
    checker.check_skipped_app_config = False
    
    You may also dynamically add or replace check_* methods in this way.
    """
    
    on = True
    
    def __init__(self):
        self._populate_known_types()
    
    def __call__(self):
        """Run all check_* methods."""
        if self.on:
            oldformatwarning = warnings.formatwarning
            warnings.formatwarning = self.formatwarning
            try:
                for name in dir(self):
                    if name.startswith("check_"):
                        method = getattr(self, name)
                        if method and callable(method):
                            method()
            finally:
                warnings.formatwarning = oldformatwarning
    
    def formatwarning(self, message, category, filename, lineno):
        """Function to format a warning."""
        return "CherryPy Checker:\n%s\n\n" % message
    
    # This value should be set inside _cpconfig.
    global_config_contained_paths = False
    
    def check_skipped_app_config(self):
        for sn, app in cherrypy.tree.apps.iteritems():
            if not isinstance(app, cherrypy.Application):
                continue
            if not app.config:
                msg = "The Application mounted at %r has an empty config." % sn
                if self.global_config_contained_paths:
                    msg += (" It looks like the config you passed to "
                            "cherrypy.config.update() contains application-"
                            "specific sections. You must explicitly pass "
                            "application config via "
                            "cherrypy.tree.mount(..., config=app_config)")
                warnings.warn(msg)
                return
    
    def check_static_paths(self):
        # Use the dummy Request object in the main thread.
        request = cherrypy.request
        for sn, app in cherrypy.tree.apps.iteritems():
            if not isinstance(app, cherrypy.Application):
                continue
            request.app = app
            for section in app.config:
                # get_resource will populate request.config
                request.get_resource(section + "/dummy.html")
                conf = request.config.get
                
                if conf("tools.staticdir.on", False):
                    msg = ""
                    root = conf("tools.staticdir.root")
                    dir = conf("tools.staticdir.dir")
                    if dir is None:
                        msg = "tools.staticdir.dir is not set."
                    else:
                        fulldir = ""
                        if os.path.isabs(dir):
                            fulldir = dir
                            if root:
                                msg = ("dir is an absolute path, even "
                                       "though a root is provided.")
                                testdir = os.path.join(root, dir[1:])
                                if os.path.exists(testdir):
                                    msg += ("\nIf you meant to serve the "
                                            "filesystem folder at %r, remove "
                                            "the leading slash from dir." % testdir)
                        else:
                            if not root:
                                msg = "dir is a relative path and no root provided."
                            else:
                                fulldir = os.path.join(root, dir)
                                if not os.path.isabs(fulldir):
                                    msg = "%r is not an absolute path." % fulldir
                        
                        if fulldir and not os.path.exists(fulldir):
                            if msg:
                                msg += "\n"
                            msg += ("%r (root + dir) is not an existing "
                                    "filesystem path." % fulldir)
                    
                    if msg:
                        warnings.warn("%s\nsection: [%s]\nroot: %r\ndir: %r"
                                      % (msg, section, root, dir))
    
    
    # -------------------------- Compatibility -------------------------- #
    
    obsolete = {
        'server.default_content_type': 'tools.response_headers.headers',
        'log_access_file': 'log.access_file',
        'log_config_options': None,
        'log_file': 'log.error_file',
        'log_file_not_found': None,
        'log_request_headers': 'tools.log_headers.on',
        'log_to_screen': 'log.screen',
        'show_tracebacks': 'request.show_tracebacks',
        'throw_errors': 'request.throw_errors',
        'profiler.on': ('cherrypy.tree.mount(profiler.make_app('
                        'cherrypy.Application(Root())))'),
        }
    
    deprecated = {}
    
    def _compat(self, config):
        """Process config and warn on each obsolete or deprecated entry."""
        for section, conf in config.iteritems():
            if isinstance(conf, dict):
                for k, v in conf.iteritems():
                    if k in self.obsolete:
                        warnings.warn("%r is obsolete. Use %r instead.\n"
                                      "section: [%s]" %
                                      (k, self.obsolete[k], section))
                    elif k in self.deprecated:
                        warnings.warn("%r is deprecated. Use %r instead.\n"
                                      "section: [%s]" %
                                      (k, self.deprecated[k], section))
            else:
                if section in self.obsolete:
                    warnings.warn("%r is obsolete. Use %r instead."
                                  % (section, self.obsolete[section]))
                elif section in self.deprecated:
                    warnings.warn("%r is deprecated. Use %r instead."
                                  % (section, self.deprecated[section]))
    
    def check_compatibility(self):
        """Process config and warn on each obsolete or deprecated entry."""
        self._compat(cherrypy.config)
        for sn, app in cherrypy.tree.apps.iteritems():
            if not isinstance(app, cherrypy.Application):
                continue
            self._compat(app.config)
    
    
    # ------------------------ Known Namespaces ------------------------ #
    
    extra_config_namespaces = []
    
    def _known_ns(self, app):
        ns = ["wsgi"]
        ns.extend(app.toolboxes.keys())
        ns.extend(app.namespaces.keys())
        ns.extend(app.request_class.namespaces.keys())
        ns.extend(cherrypy.config.namespaces.keys())
        ns += self.extra_config_namespaces
        
        for section, conf in app.config.iteritems():
            is_path_section = section.startswith("/")
            if is_path_section and isinstance(conf, dict):
                for k, v in conf.iteritems():
                    atoms = k.split(".")
                    if len(atoms) > 1:
                        if atoms[0] not in ns:
                            # Spit out a special warning if a known
                            # namespace is preceded by "cherrypy."
                            if (atoms[0] == "cherrypy" and atoms[1] in ns):
                                msg = ("The config entry %r is invalid; "
                                       "try %r instead.\nsection: [%s]"
                                       % (k, ".".join(atoms[1:]), section))
                            else:
                                msg = ("The config entry %r is invalid, because "
                                       "the %r config namespace is unknown.\n"
                                       "section: [%s]" % (k, atoms[0], section))
                            warnings.warn(msg)
                        elif atoms[0] == "tools":
                            if atoms[1] not in dir(cherrypy.tools):
                                msg = ("The config entry %r may be invalid, "
                                       "because the %r tool was not found.\n"
                                       "section: [%s]" % (k, atoms[1], section))
                                warnings.warn(msg)
    
    def check_config_namespaces(self):
        """Process config and warn on each unknown config namespace."""
        for sn, app in cherrypy.tree.apps.iteritems():
            if not isinstance(app, cherrypy.Application):
                continue
            self._known_ns(app)


    
    
    # -------------------------- Config Types -------------------------- #
    
    known_config_types = {}
    
    def _populate_known_types(self):
        import __builtin__
        builtins = [x for x in vars(__builtin__).values()
                    if type(x) is type(str)]
        
        def traverse(obj, namespace):
            for name in dir(obj):
                vtype = type(getattr(obj, name, None))
                if vtype in builtins:
                    self.known_config_types[namespace + "." + name] = vtype
        
        traverse(cherrypy.request, "request")
        traverse(cherrypy.response, "response")
        traverse(cherrypy.server, "server")
        traverse(cherrypy.engine, "engine")
        traverse(cherrypy.log, "log")
    
    def _known_types(self, config):
        msg = ("The config entry %r in section %r is of type %r, "
               "which does not match the expected type %r.")
        
        for section, conf in config.iteritems():
            if isinstance(conf, dict):
                for k, v in conf.iteritems():
                    if v is not None:
                        expected_type = self.known_config_types.get(k, None)
                        vtype = type(v)
                        if expected_type and vtype != expected_type:
                            warnings.warn(msg % (k, section, vtype.__name__,
                                                 expected_type.__name__))
            else:
                k, v = section, conf
                if v is not None:
                    expected_type = self.known_config_types.get(k, None)
                    vtype = type(v)
                    if expected_type and vtype != expected_type:
                        warnings.warn(msg % (k, section, vtype.__name__,
                                             expected_type.__name__))
    
    def check_config_types(self):
        """Assert that config values are of the same type as default values."""
        self._known_types(cherrypy.config)
        for sn, app in cherrypy.tree.apps.iteritems():
            if not isinstance(app, cherrypy.Application):
                continue
            self._known_types(app.config)
    
    
    # -------------------- Specific config warnings -------------------- #
    
    def check_localhost(self):
        """Warn if any socket_host is 'localhost'. See #711."""
        for k, v in cherrypy.config.iteritems():
            if k == 'server.socket_host' and v == 'localhost':
                warnings.warn("The use of 'localhost' as a socket host can "
                    "cause problems on newer systems, since 'localhost' can "
                    "map to either an IPv4 or an IPv6 address. You should "
                    "use '127.0.0.1' or '[::1]' instead.")
