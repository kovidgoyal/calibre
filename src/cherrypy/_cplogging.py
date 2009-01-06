"""CherryPy logging."""

import datetime
import logging
# Silence the no-handlers "warning" (stderr write!) in stdlib logging
logging.Logger.manager.emittedNoHandlerWarning = 1
logfmt = logging.Formatter("%(message)s")
import os
import rfc822
import sys

import cherrypy
from cherrypy import _cperror


class LogManager(object):
    
    appid = None
    error_log = None
    access_log = None
    access_log_format = \
        '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
    
    def __init__(self, appid=None, logger_root="cherrypy"):
        self.logger_root = logger_root
        self.appid = appid
        if appid is None:
            self.error_log = logging.getLogger("%s.error" % logger_root)
            self.access_log = logging.getLogger("%s.access" % logger_root)
        else:
            self.error_log = logging.getLogger("%s.error.%s" % (logger_root, appid))
            self.access_log = logging.getLogger("%s.access.%s" % (logger_root, appid))
        self.error_log.setLevel(logging.DEBUG)
        self.access_log.setLevel(logging.INFO)
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
        """Write to the error log.
        
        This is not just for errors! Applications may call this at any time
        to log application-specific information.
        """
        if traceback:
            msg += _cperror.format_exc()
        self.error_log.log(severity, ' '.join((self.time(), context, msg)))
    
    def __call__(self, *args, **kwargs):
        """Write to the error log.
        
        This is not just for errors! Applications may call this at any time
        to log application-specific information.
        """
        return self.error(*args, **kwargs)
    
    def access(self):
        """Write to the access log (in Apache/NCSA Combined Log format).
        
        Like Apache started doing in 2.0.46, non-printable and other special
        characters in %r (and we expand that to all parts) are escaped using
        \\xhh sequences, where hh stands for the hexadecimal representation
        of the raw byte. Exceptions from this rule are " and \\, which are
        escaped by prepending a backslash, and all whitespace characters,
        which are written in their C-style notation (\\n, \\t, etc).
        """
        request = cherrypy.request
        remote = request.remote
        response = cherrypy.response
        outheaders = response.headers
        inheaders = request.headers
        
        atoms = {'h': remote.name or remote.ip,
                 'l': '-',
                 'u': getattr(request, "login", None) or "-",
                 't': self.time(),
                 'r': request.request_line,
                 's': response.status.split(" ", 1)[0],
                 'b': outheaders.get('Content-Length', '') or "-",
                 'f': inheaders.get('Referer', ''),
                 'a': inheaders.get('User-Agent', ''),
                 }
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
        month = rfc822._monthnames[now.month - 1].capitalize()
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
        self._set_screen_handler(self.access_log, newvalue)
    screen = property(_get_screen, _set_screen,
                      doc="If True, error and access will print to stderr.")
    
    
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
                          doc="The filename for self.error_log.")
    
    def _get_access_file(self):
        h = self._get_builtin_handler(self.access_log, "file")
        if h:
            return h.baseFilename
        return ''
    def _set_access_file(self, newvalue):
        self._set_file_handler(self.access_log, newvalue)
    access_file = property(_get_access_file, _set_access_file,
                           doc="The filename for self.access_log.")
    
    
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
                      doc="If True, error messages will be sent to wsgi.errors.")


class WSGIErrorHandler(logging.Handler):
    "A handler class which writes logging records to environ['wsgi.errors']."
    
    def flush(self):
        """Flushes the stream."""
        try:
            stream = cherrypy.request.wsgi_environ.get('wsgi.errors')
        except (AttributeError, KeyError):
            pass
        else:
            stream.flush()
    
    def emit(self, record):
        """Emit a record."""
        try:
            stream = cherrypy.request.wsgi_environ.get('wsgi.errors')
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
