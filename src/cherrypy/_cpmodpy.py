"""Native adapter for serving CherryPy via mod_python

Basic usage:

##########################################
# Application in a module called myapp.py
##########################################

import cherrypy

class Root:
    @cherrypy.expose
    def index(self):
        return 'Hi there, Ho there, Hey there'


# We will use this method from the mod_python configuration
# as the entry point to our application
def setup_server():
    cherrypy.tree.mount(Root())
    cherrypy.config.update({'environment': 'production',
                            'log.screen': False,
                            'show_tracebacks': False})

##########################################
# mod_python settings for apache2
# This should reside in your httpd.conf
# or a file that will be loaded at
# apache startup
##########################################

# Start
DocumentRoot "/"
Listen 8080
LoadModule python_module /usr/lib/apache2/modules/mod_python.so

<Location "/">
	PythonPath "sys.path+['/path/to/my/application']" 
	SetHandler python-program
	PythonHandler cherrypy._cpmodpy::handler
	PythonOption cherrypy.setup myapp::setup_server
	PythonDebug On
</Location> 
# End

The actual path to your mod_python.so is dependent on your
environment. In this case we suppose a global mod_python
installation on a Linux distribution such as Ubuntu.

We do set the PythonPath configuration setting so that
your application can be found by from the user running
the apache2 instance. Of course if your application
resides in the global site-package this won't be needed.

Then restart apache2 and access http://127.0.0.1:8080
"""

import logging
import StringIO

import cherrypy
from cherrypy._cperror import format_exc, bare_error
from cherrypy.lib import http



# ------------------------------ Request-handling



def setup(req):
    from mod_python import apache
    
    # Run any setup function defined by a "PythonOption cherrypy.setup" directive.
    options = req.get_options()
    if 'cherrypy.setup' in options:
        atoms = options['cherrypy.setup'].split('::', 1)
        if len(atoms) == 1:
            mod = __import__(atoms[0], globals(), locals())
        else:
            modname, fname = atoms
            mod = __import__(modname, globals(), locals(), [fname])
            func = getattr(mod, fname)
            func()
    
    cherrypy.config.update({'log.screen': False,
                            "tools.ignore_headers.on": True,
                            "tools.ignore_headers.headers": ['Range'],
                            })
    
    engine = cherrypy.engine
    if hasattr(engine, "signal_handler"):
        engine.signal_handler.unsubscribe()
    if hasattr(engine, "console_control_handler"):
        engine.console_control_handler.unsubscribe()
    engine.autoreload.unsubscribe()
    cherrypy.server.unsubscribe()
    
    def _log(msg, level):
        newlevel = apache.APLOG_ERR
        if logging.DEBUG >= level:
            newlevel = apache.APLOG_DEBUG
        elif logging.INFO >= level:
            newlevel = apache.APLOG_INFO
        elif logging.WARNING >= level:
            newlevel = apache.APLOG_WARNING
        # On Windows, req.server is required or the msg will vanish. See
        # http://www.modpython.org/pipermail/mod_python/2003-October/014291.html.
        # Also, "When server is not specified...LogLevel does not apply..."
        apache.log_error(msg, newlevel, req.server)
    engine.subscribe('log', _log)
    
    engine.start()
    
    def cherrypy_cleanup(data):
        engine.exit()
    try:
        # apache.register_cleanup wasn't available until 3.1.4.
        apache.register_cleanup(cherrypy_cleanup)
    except AttributeError:
        req.server.register_cleanup(req, cherrypy_cleanup)


class _ReadOnlyRequest:
    expose = ('read', 'readline', 'readlines')
    def __init__(self, req):
        for method in self.expose:
            self.__dict__[method] = getattr(req, method)


recursive = False

_isSetUp = False
def handler(req):
    from mod_python import apache
    try:
        global _isSetUp
        if not _isSetUp:
            setup(req)
            _isSetUp = True
        
        # Obtain a Request object from CherryPy
        local = req.connection.local_addr
        local = http.Host(local[0], local[1], req.connection.local_host or "")
        remote = req.connection.remote_addr
        remote = http.Host(remote[0], remote[1], req.connection.remote_host or "")
        
        scheme = req.parsed_uri[0] or 'http'
        req.get_basic_auth_pw()
        
        try:
            # apache.mpm_query only became available in mod_python 3.1
            q = apache.mpm_query
            threaded = q(apache.AP_MPMQ_IS_THREADED)
            forked = q(apache.AP_MPMQ_IS_FORKED)
        except AttributeError:
            bad_value = ("You must provide a PythonOption '%s', "
                         "either 'on' or 'off', when running a version "
                         "of mod_python < 3.1")
            
            threaded = options.get('multithread', '').lower()
            if threaded == 'on':
                threaded = True
            elif threaded == 'off':
                threaded = False
            else:
                raise ValueError(bad_value % "multithread")
            
            forked = options.get('multiprocess', '').lower()
            if forked == 'on':
                forked = True
            elif forked == 'off':
                forked = False
            else:
                raise ValueError(bad_value % "multiprocess")
        
        sn = cherrypy.tree.script_name(req.uri or "/")
        if sn is None:
            send_response(req, '404 Not Found', [], '')
        else:
            app = cherrypy.tree.apps[sn]
            method = req.method
            path = req.uri
            qs = req.args or ""
            reqproto = req.protocol
            headers = req.headers_in.items()
            rfile = _ReadOnlyRequest(req)
            prev = None
            
            try:
                redirections = []
                while True:
                    request, response = app.get_serving(local, remote, scheme,
                                                        "HTTP/1.1")
                    request.login = req.user
                    request.multithread = bool(threaded)
                    request.multiprocess = bool(forked)
                    request.app = app
                    request.prev = prev
                    
                    # Run the CherryPy Request object and obtain the response
                    try:
                        request.run(method, path, qs, reqproto, headers, rfile)
                        break
                    except cherrypy.InternalRedirect, ir:
                        app.release_serving()
                        prev = request
                        
                        if not recursive:
                            if ir.path in redirections:
                                raise RuntimeError("InternalRedirector visited the "
                                                   "same URL twice: %r" % ir.path)
                            else:
                                # Add the *previous* path_info + qs to redirections.
                                if qs:
                                    qs = "?" + qs
                                redirections.append(sn + path + qs)
                        
                        # Munge environment and try again.
                        method = "GET"
                        path = ir.path
                        qs = ir.query_string
                        rfile = StringIO.StringIO()
                
                send_response(req, response.status, response.header_list,
                              response.body, response.stream)
            finally:
                app.release_serving()
    except:
        tb = format_exc()
        cherrypy.log(tb, 'MOD_PYTHON', severity=logging.ERROR)
        s, h, b = bare_error()
        send_response(req, s, h, b)
    return apache.OK


def send_response(req, status, headers, body, stream=False):
    # Set response status
    req.status = int(status[:3])
    
    # Set response headers
    req.content_type = "text/plain"
    for header, value in headers:
        if header.lower() == 'content-type':
            req.content_type = value
            continue
        req.headers_out.add(header, value)
    
    if stream:
        # Flush now so the status and headers are sent immediately.
        req.flush()
    
    # Set response body
    if isinstance(body, basestring):
        req.write(body)
    else:
        for seg in body:
            req.write(seg)



# --------------- Startup tools for CherryPy + mod_python --------------- #


import os
import re


def read_process(cmd, args=""):
    pipein, pipeout = os.popen4("%s %s" % (cmd, args))
    try:
        firstline = pipeout.readline()
        if (re.search(r"(not recognized|No such file|not found)", firstline,
                      re.IGNORECASE)):
            raise IOError('%s must be on your system path.' % cmd)
        output = firstline + pipeout.read()
    finally:
        pipeout.close()
    return output


class ModPythonServer(object):
    
    template = """
# Apache2 server configuration file for running CherryPy with mod_python.

DocumentRoot "/"
Listen %(port)s
LoadModule python_module modules/mod_python.so

<Location %(loc)s>
    SetHandler python-program
    PythonHandler %(handler)s
    PythonDebug On
%(opts)s
</Location>
"""
    
    def __init__(self, loc="/", port=80, opts=None, apache_path="apache",
                 handler="cherrypy._cpmodpy::handler"):
        self.loc = loc
        self.port = port
        self.opts = opts
        self.apache_path = apache_path
        self.handler = handler
    
    def start(self):
        opts = "".join(["    PythonOption %s %s\n" % (k, v)
                        for k, v in self.opts])
        conf_data = self.template % {"port": self.port,
                                     "loc": self.loc,
                                     "opts": opts,
                                     "handler": self.handler,
                                     }
        
        mpconf = os.path.join(os.path.dirname(__file__), "cpmodpy.conf")
        f = open(mpconf, 'wb')
        try:
            f.write(conf_data)
        finally:
            f.close()
        
        response = read_process(self.apache_path, "-k start -f %s" % mpconf)
        self.ready = True
        return response
    
    def stop(self):
        os.popen("apache -k stop")
        self.ready = False

