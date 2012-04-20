"""
Simple config
=============

Although CherryPy uses the :mod:`Python logging module <logging>`, it does so
behind the scenes so that simple logging is simple, but complicated logging
is still possible. "Simple" logging means that you can log to the screen
(i.e. console/stdout) or to a file, and that you can easily have separate
error and access log files.

Here are the simplified logging settings. You use these by adding lines to
your config file or dict. You should set these at either the global level or
per application (see next), but generally not both.

 * ``log.screen``: Set this to True to have both "error" and "access" messages
   printed to stdout.
 * ``log.access_file``: Set this to an absolute filename where you want
   "access" messages written.
 * ``log.error_file``: Set this to an absolute filename where you want "error"
   messages written.

Many events are automatically logged; to log your own application events, call
:func:`cherrypy.log`.

Architecture
============

Separate scopes
---------------

CherryPy provides log managers at both the global and application layers.
This means you can have one set of logging rules for your entire site,
and another set of rules specific to each application. The global log
manager is found at :func:`cherrypy.log`, and the log manager for each
application is found at :attr:`app.log<cherrypy._cptree.Application.log>`.
If you're inside a request, the latter is reachable from
``cherrypy.request.app.log``; if you're outside a request, you'll have to obtain
a reference to the ``app``: either the return value of
:func:`tree.mount()<cherrypy._cptree.Tree.mount>` or, if you used
:func:`quickstart()<cherrypy.quickstart>` instead, via ``cherrypy.tree.apps['/']``.

By default, the global logs are named "cherrypy.error" and "cherrypy.access",
and the application logs are named "cherrypy.error.2378745" and
"cherrypy.access.2378745" (the number is the id of the Application object).
This means that the application logs "bubble up" to the site logs, so if your
application has no log handlers, the site-level handlers will still log the
messages.

Errors vs. Access
-----------------

Each log manager handles both "access" messages (one per HTTP request) and
"error" messages (everything else). Note that the "error" log is not just for
errors! The format of access messages is highly formalized, but the error log
isn't--it receives messages from a variety of sources (including full error
tracebacks, if enabled).


Custom Handlers
===============

The simple settings above work by manipulating Python's standard :mod:`logging`
module. So when you need something more complex, the full power of the standard
module is yours to exploit. You can borrow or create custom handlers, formats,
filters, and much more. Here's an example that skips the standard FileHandler
and uses a RotatingFileHandler instead:

::

    #python
    log = app.log
    
    # Remove the default FileHandlers if present.
    log.error_file = ""
    log.access_file = ""
    
    maxBytes = getattr(log, "rot_maxBytes", 10000000)
    backupCount = getattr(log, "rot_backupCount", 1000)
    
    # Make a new RotatingFileHandler for the error log.
    fname = getattr(log, "rot_error_file", "error.log")
    h = handlers.RotatingFileHandler(fname, 'a', maxBytes, backupCount)
    h.setLevel(DEBUG)
    h.setFormatter(_cplogging.logfmt)
    log.error_log.addHandler(h)
    
    # Make a new RotatingFileHandler for the access log.
    fname = getattr(log, "rot_access_file", "access.log")
    h = handlers.RotatingFileHandler(fname, 'a', maxBytes, backupCount)
    h.setLevel(DEBUG)
    h.setFormatter(_cplogging.logfmt)
    log.access_log.addHandler(h)


The ``rot_*`` attributes are pulled straight from the application log object.
Since "log.*" config entries simply set attributes on the log object, you can
add custom attributes to your heart's content. Note that these handlers are
used ''instead'' of the default, simple handlers outlined above (so don't set
the "log.error_file" config entry, for example).
"""

import datetime
import logging
# Silence the no-handlers "warning" (stderr write!) in stdlib logging
logging.Logger.manager.emittedNoHandlerWarning = 1
logfmt = logging.Formatter("%(message)s")
import os
import sys

import cherrypy
from cherrypy import _cperror
from cherrypy._cpcompat import ntob, py3k


class NullHandler(logging.Handler):
    """A no-op logging handler to silence the logging.lastResort handler."""

    def handle(self, record):
        pass

    def emit(self, record):
        pass

    def createLock(self):
        self.lock = None


class LogManager(object):
    """An object to assist both simple and advanced logging.
    
    ``cherrypy.log`` is an instance of this class.
    """
    
    appid = None
    """The id() of the Application object which owns this log manager. If this
    is a global log manager, appid is None."""
   
    error_log = None
    """The actual :class:`logging.Logger` instance for error messages."""
    
    access_log = None
    """The actual :class:`logging.Logger` instance for access messages."""
    
    if py3k:
        access_log_format = \
            '{h} {l} {u} {t} "{r}" {s} {b} "{f}" "{a}"'
    else:
        access_log_format = \
            '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
    
    logger_root = None
    """The "top-level" logger name.
    
    This string will be used as the first segment in the Logger names.
    The default is "cherrypy", for example, in which case the Logger names
    will be of the form::
    
        cherrypy.error.<appid>
        cherrypy.access.<appid>
    """
    
    def __init__(self, appid=None, logger_root="cherrypy"):
        self.logger_root = logger_root
        self.appid = appid
        if appid is None:
            self.error_log = logging.getLogger("%s.error" % logger_root)
            self.access_log = logging.getLogger("%s.access" % logger_root)
        else:
            self.error_log = logging.getLogger("%s.error.%s" % (logger_root, appid))
            self.access_log = logging.getLogger("%s.access.%s" % (logger_root, appid))
        self.error_log.setLevel(logging.INFO)
        self.access_log.setLevel(logging.INFO)

        # Silence the no-handlers "warning" (stderr write!) in stdlib logging
        self.error_log.addHandler(NullHandler())
        self.access_log.addHandler(NullHandler())

        cherrypy.engine.subscribe('graceful', self.reopen_files)

    def reopen_files(self):
        """Close and reopen all file handlers."""
        for log in (self.error_log, self.access_log):
            for h in log.handlers:
                if isinstance(h, logging.FileHandler):
                    h.acquire()
                    h.stream.close()
                    h.stream = open(h.baseFilename, h.mode)
                    h.release()
    
    def error(self, msg='', context='', severity=logging.INFO, traceback=False):
        """Write the given ``msg`` to the error log.
        
        This is not just for errors! Applications may call this at any time
        to log application-specific information.
        
        If ``traceback`` is True, the traceback of the current exception
        (if any) will be appended to ``msg``.
        """
        if traceback:
            msg += _cperror.format_exc()
        self.error_log.log(severity, ' '.join((self.time(), context, msg)))
    
    def __call__(self, *args, **kwargs):
        """An alias for ``error``."""
        return self.error(*args, **kwargs)
    
    def access(self):
        """Write to the access log (in Apache/NCSA Combined Log format).
        
        See http://httpd.apache.org/docs/2.0/logs.html#combined for format
        details.
        
        CherryPy calls this automatically for you. Note there are no arguments;
        it collects the data itself from
        :class:`cherrypy.request<cherrypy._cprequest.Request>`.
        
        Like Apache started doing in 2.0.46, non-printable and other special
        characters in %r (and we expand that to all parts) are escaped using
        \\xhh sequences, where hh stands for the hexadecimal representation
        of the raw byte. Exceptions from this rule are " and \\, which are
        escaped by prepending a backslash, and all whitespace characters,
        which are written in their C-style notation (\\n, \\t, etc).
        """
        request = cherrypy.serving.request
        remote = request.remote
        response = cherrypy.serving.response
        outheaders = response.headers
        inheaders = request.headers
        if response.output_status is None:
            status = "-"
        else:
            status = response.output_status.split(ntob(" "), 1)[0]
            if py3k:
                status = status.decode('ISO-8859-1')
        
        atoms = {'h': remote.name or remote.ip,
                 'l': '-',
                 'u': getattr(request, "login", None) or "-",
                 't': self.time(),
                 'r': request.request_line,
                 's': status,
                 'b': dict.get(outheaders, 'Content-Length', '') or "-",
                 'f': dict.get(inheaders, 'Referer', ''),
                 'a': dict.get(inheaders, 'User-Agent', ''),
                 }
        if py3k:
            for k, v in atoms.items():
                if not isinstance(v, str):
                    v = str(v)
                v = v.replace('"', '\\"').encode('utf8')
                # Fortunately, repr(str) escapes unprintable chars, \n, \t, etc
                # and backslash for us. All we have to do is strip the quotes.
                v = repr(v)[2:-1]
                
                # in python 3.0 the repr of bytes (as returned by encode) 
                # uses double \'s.  But then the logger escapes them yet, again
                # resulting in quadruple slashes.  Remove the extra one here.
                v = v.replace('\\\\', '\\')
                
                # Escape double-quote.
                atoms[k] = v
            
            try:
                self.access_log.log(logging.INFO, self.access_log_format.format(**atoms))
            except:
                self(traceback=True)
        else:
            for k, v in atoms.items():
                if isinstance(v, unicode):
                    v = v.encode('utf8')
                elif not isinstance(v, str):
                    v = str(v)
                # Fortunately, repr(str) escapes unprintable chars, \n, \t, etc
                # and backslash for us. All we have to do is strip the quotes.
                v = repr(v)[1:-1]
                # Escape double-quote.
                atoms[k] = v.replace('"', '\\"')
            
            try:
                self.access_log.log(logging.INFO, self.access_log_format % atoms)
            except:
                self(traceback=True)
    
    def time(self):
        """Return now() in Apache Common Log Format (no timezone)."""
        now = datetime.datetime.now()
        monthnames = ['jan', 'feb', 'mar', 'apr', 'may', 'jun',
                      'jul', 'aug', 'sep', 'oct', 'nov', 'dec']
        month = monthnames[now.month - 1].capitalize()
        return ('[%02d/%s/%04d:%02d:%02d:%02d]' %
                (now.day, month, now.year, now.hour, now.minute, now.second))
    
    def _get_builtin_handler(self, log, key):
        for h in log.handlers:
            if getattr(h, "_cpbuiltin", None) == key:
                return h
    
    
    # ------------------------- Screen handlers ------------------------- #
    
    def _set_screen_handler(self, log, enable, stream=None):
        h = self._get_builtin_handler(log, "screen")
        if enable:
            if not h:
                if stream is None:
                    stream=sys.stderr
                h = logging.StreamHandler(stream)
                h.setFormatter(logfmt)
                h._cpbuiltin = "screen"
                log.addHandler(h)
        elif h:
            log.handlers.remove(h)
    
    def _get_screen(self):
        h = self._get_builtin_handler
        has_h = h(self.error_log, "screen") or h(self.access_log, "screen")
        return bool(has_h)
    
    def _set_screen(self, newvalue):
        self._set_screen_handler(self.error_log, newvalue, stream=sys.stderr)
        self._set_screen_handler(self.access_log, newvalue, stream=sys.stdout)
    screen = property(_get_screen, _set_screen,
        doc="""Turn stderr/stdout logging on or off.
        
        If you set this to True, it'll add the appropriate StreamHandler for
        you. If you set it to False, it will remove the handler.
        """)
    
    # -------------------------- File handlers -------------------------- #
    
    def _add_builtin_file_handler(self, log, fname):
        h = logging.FileHandler(fname)
        h.setFormatter(logfmt)
        h._cpbuiltin = "file"
        log.addHandler(h)
    
    def _set_file_handler(self, log, filename):
        h = self._get_builtin_handler(log, "file")
        if filename:
            if h:
                if h.baseFilename != os.path.abspath(filename):
                    h.close()
                    log.handlers.remove(h)
                    self._add_builtin_file_handler(log, filename)
            else:
                self._add_builtin_file_handler(log, filename)
        else:
            if h:
                h.close()
                log.handlers.remove(h)
    
    def _get_error_file(self):
        h = self._get_builtin_handler(self.error_log, "file")
        if h:
            return h.baseFilename
        return ''
    def _set_error_file(self, newvalue):
        self._set_file_handler(self.error_log, newvalue)
    error_file = property(_get_error_file, _set_error_file,
        doc="""The filename for self.error_log.
        
        If you set this to a string, it'll add the appropriate FileHandler for
        you. If you set it to ``None`` or ``''``, it will remove the handler.
        """)
    
    def _get_access_file(self):
        h = self._get_builtin_handler(self.access_log, "file")
        if h:
            return h.baseFilename
        return ''
    def _set_access_file(self, newvalue):
        self._set_file_handler(self.access_log, newvalue)
    access_file = property(_get_access_file, _set_access_file,
        doc="""The filename for self.access_log.
        
        If you set this to a string, it'll add the appropriate FileHandler for
        you. If you set it to ``None`` or ``''``, it will remove the handler.
        """)
    
    # ------------------------- WSGI handlers ------------------------- #
    
    def _set_wsgi_handler(self, log, enable):
        h = self._get_builtin_handler(log, "wsgi")
        if enable:
            if not h:
                h = WSGIErrorHandler()
                h.setFormatter(logfmt)
                h._cpbuiltin = "wsgi"
                log.addHandler(h)
        elif h:
            log.handlers.remove(h)
    
    def _get_wsgi(self):
        return bool(self._get_builtin_handler(self.error_log, "wsgi"))
    
    def _set_wsgi(self, newvalue):
        self._set_wsgi_handler(self.error_log, newvalue)
    wsgi = property(_get_wsgi, _set_wsgi,
        doc="""Write errors to wsgi.errors.
        
        If you set this to True, it'll add the appropriate
        :class:`WSGIErrorHandler<cherrypy._cplogging.WSGIErrorHandler>` for you
        (which writes errors to ``wsgi.errors``).
        If you set it to False, it will remove the handler.
        """)


class WSGIErrorHandler(logging.Handler):
    "A handler class which writes logging records to environ['wsgi.errors']."
    
    def flush(self):
        """Flushes the stream."""
        try:
            stream = cherrypy.serving.request.wsgi_environ.get('wsgi.errors')
        except (AttributeError, KeyError):
            pass
        else:
            stream.flush()
    
    def emit(self, record):
        """Emit a record."""
        try:
            stream = cherrypy.serving.request.wsgi_environ.get('wsgi.errors')
        except (AttributeError, KeyError):
            pass
        else:
            try:
                msg = self.format(record)
                fs = "%s\n"
                import types
                if not hasattr(types, "UnicodeType"): #if no unicode support...
                    stream.write(fs % msg)
                else:
                    try:
                        stream.write(fs % msg)
                    except UnicodeError:
                        stream.write(fs % msg.encode("UTF-8"))
                self.flush()
            except:
                self.handleError(record)
