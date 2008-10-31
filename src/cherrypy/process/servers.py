"""Adapt an HTTP server."""

import time


class ServerAdapter(object):
    """Adapter for an HTTP server.
    
    If you need to start more than one HTTP server (to serve on multiple
    ports, or protocols, etc.), you can manually register each one and then
    start them all with bus.start:
    
        s1 = ServerAdapter(bus, MyWSGIServer(host='0.0.0.0', port=80))
        s2 = ServerAdapter(bus, another.HTTPServer(host='127.0.0.1', SSL=True))
        s1.subscribe()
        s2.subscribe()
        bus.start()
    """
    
    def __init__(self, bus, httpserver=None, bind_addr=None):
        self.bus = bus
        self.httpserver = httpserver
        self.bind_addr = bind_addr
        self.interrupt = None
        self.running = False
    
    def subscribe(self):
        self.bus.subscribe('start', self.start)
        self.bus.subscribe('stop', self.stop)
    
    def unsubscribe(self):
        self.bus.unsubscribe('start', self.start)
        self.bus.unsubscribe('stop', self.stop)
    
    def start(self):
        """Start the HTTP server."""
        if isinstance(self.bind_addr, tuple):
            host, port = self.bind_addr
            on_what = "%s:%s" % (host, port)
        else:
            on_what = "socket file: %s" % self.bind_addr
        
        if self.running:
            self.bus.log("Already serving on %s" % on_what)
            return
        
        self.interrupt = None
        if not self.httpserver:
            raise ValueError("No HTTP server has been created.")
        
        # Start the httpserver in a new thread.
        if isinstance(self.bind_addr, tuple):
            wait_for_free_port(*self.bind_addr)
        
        import threading
        t = threading.Thread(target=self._start_http_thread)
        t.setName("HTTPServer " + t.getName())
        t.start()
        
        self.wait()
        self.running = True
        self.bus.log("Serving on %s" % on_what)
    start.priority = 75
    
    def _start_http_thread(self):
        """HTTP servers MUST be running in new threads, so that the
        main thread persists to receive KeyboardInterrupt's. If an
        exception is raised in the httpserver's thread then it's
        trapped here, and the bus (and therefore our httpserver)
        are shut down.
        """
        try:
            self.httpserver.start()
        except KeyboardInterrupt, exc:
            self.bus.log("<Ctrl-C> hit: shutting down HTTP server")
            self.interrupt = exc
            self.bus.exit()
        except SystemExit, exc:
            self.bus.log("SystemExit raised: shutting down HTTP server")
            self.interrupt = exc
            self.bus.exit()
            raise
        except:
            import sys
            self.interrupt = sys.exc_info()[1]
            self.bus.log("Error in HTTP server: shutting down",
                         traceback=True, level=40)
            self.bus.exit()
            raise
    
    def wait(self):
        """Wait until the HTTP server is ready to receive requests."""
        while not getattr(self.httpserver, "ready", False):
            if self.interrupt:
                raise self.interrupt
            time.sleep(.1)
        
        # Wait for port to be occupied
        if isinstance(self.bind_addr, tuple):
            host, port = self.bind_addr
            wait_for_occupied_port(host, port)
    
    def stop(self):
        """Stop the HTTP server."""
        if self.running:
            # stop() MUST block until the server is *truly* stopped.
            self.httpserver.stop()
            # Wait for the socket to be truly freed.
            if isinstance(self.bind_addr, tuple):
                wait_for_free_port(*self.bind_addr)
            self.running = False
            self.bus.log("HTTP Server %s shut down" % self.httpserver)
        else:
            self.bus.log("HTTP Server %s already shut down" % self.httpserver)
    stop.priority = 25
    
    def restart(self):
        """Restart the HTTP server."""
        self.stop()
        self.start()


class FlupFCGIServer(object):
    """Adapter for a flup.server.fcgi.WSGIServer."""
    
    def __init__(self, *args, **kwargs):
        from flup.server.fcgi import WSGIServer
        self.fcgiserver = WSGIServer(*args, **kwargs)
        # TODO: report this bug upstream to flup.
        # If we don't set _oldSIGs on Windows, we get:
        #   File "C:\Python24\Lib\site-packages\flup\server\threadedserver.py",
        #   line 108, in run
        #     self._restoreSignalHandlers()
        #   File "C:\Python24\Lib\site-packages\flup\server\threadedserver.py",
        #   line 156, in _restoreSignalHandlers
        #     for signum,handler in self._oldSIGs:
        #   AttributeError: 'WSGIServer' object has no attribute '_oldSIGs'
        self.fcgiserver._oldSIGs = []
        self.ready = False
    
    def start(self):
        """Start the FCGI server."""
        self.ready = True
        self.fcgiserver.run()
    
    def stop(self):
        """Stop the HTTP server."""
        self.ready = False
        # Forcibly stop the fcgi server main event loop.
        self.fcgiserver._keepGoing = False
        # Force all worker threads to die off.
        self.fcgiserver._threadPool.maxSpare = 0


def client_host(server_host):
    """Return the host on which a client can connect to the given listener."""
    if server_host == '0.0.0.0':
        # 0.0.0.0 is INADDR_ANY, which should answer on localhost.
        return '127.0.0.1'
    if server_host == '::':
        # :: is IN6ADDR_ANY, which should answer on localhost.
        return '::1'
    return server_host

def check_port(host, port, timeout=1.0):
    """Raise an error if the given port is not free on the given host."""
    if not host:
        raise ValueError("Host values of '' or None are not allowed.")
    host = client_host(host)
    port = int(port)
    
    import socket
    
    # AF_INET or AF_INET6 socket
    # Get the correct address family for our host (allows IPv6 addresses)
    for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC,
                                  socket.SOCK_STREAM):
        af, socktype, proto, canonname, sa = res
        s = None
        try:
            s = socket.socket(af, socktype, proto)
            # See http://groups.google.com/group/cherrypy-users/
            #        browse_frm/thread/bbfe5eb39c904fe0
            s.settimeout(timeout)
            s.connect((host, port))
            s.close()
            raise IOError("Port %s is in use on %s; perhaps the previous "
                          "httpserver did not shut down properly." %
                          (repr(port), repr(host)))
        except socket.error:
            if s:
                s.close()

def wait_for_free_port(host, port):
    """Wait for the specified port to become free (drop requests)."""
    if not host:
        raise ValueError("Host values of '' or None are not allowed.")
    
    for trial in xrange(50):
        try:
            # we are expecting a free port, so reduce the timeout
            check_port(host, port, timeout=0.1)
        except IOError:
            # Give the old server thread time to free the port.
            time.sleep(0.1)
        else:
            return
    
    raise IOError("Port %r not free on %r" % (port, host))

def wait_for_occupied_port(host, port):
    """Wait for the specified port to become active (receive requests)."""
    if not host:
        raise ValueError("Host values of '' or None are not allowed.")
    
    for trial in xrange(50):
        try:
            check_port(host, port)
        except IOError:
            return
        else:
            time.sleep(.1)
    
    raise IOError("Port %r not bound on %r" % (port, host))
