"""Site services for use with a Web Site Process Bus."""

import os
import re
import signal as _signal
import sys
import time
import threading

from cherrypy._cpcompat import basestring, get_daemon, get_thread_ident, ntob, set

# _module__file__base is used by Autoreload to make
# absolute any filenames retrieved from sys.modules which are not
# already absolute paths.  This is to work around Python's quirk
# of importing the startup script and using a relative filename
# for it in sys.modules.
#
# Autoreload examines sys.modules afresh every time it runs. If an application
# changes the current directory by executing os.chdir(), then the next time
# Autoreload runs, it will not be able to find any filenames which are
# not absolute paths, because the current directory is not the same as when the
# module was first imported.  Autoreload will then wrongly conclude the file has
# "changed", and initiate the shutdown/re-exec sequence.
# See ticket #917.
# For this workaround to have a decent probability of success, this module
# needs to be imported as early as possible, before the app has much chance
# to change the working directory.
_module__file__base = os.getcwd()


class SimplePlugin(object):
    """Plugin base class which auto-subscribes methods for known channels."""
    
    bus = None
    """A :class:`Bus <cherrypy.process.wspbus.Bus>`, usually cherrypy.engine."""
    
    def __init__(self, bus):
        self.bus = bus
    
    def subscribe(self):
        """Register this object as a (multi-channel) listener on the bus."""
        for channel in self.bus.listeners:
            # Subscribe self.start, self.exit, etc. if present.
            method = getattr(self, channel, None)
            if method is not None:
                self.bus.subscribe(channel, method)
    
    def unsubscribe(self):
        """Unregister this object as a listener on the bus."""
        for channel in self.bus.listeners:
            # Unsubscribe self.start, self.exit, etc. if present.
            method = getattr(self, channel, None)
            if method is not None:
                self.bus.unsubscribe(channel, method)



class SignalHandler(object):
    """Register bus channels (and listeners) for system signals.
    
    You can modify what signals your application listens for, and what it does
    when it receives signals, by modifying :attr:`SignalHandler.handlers`,
    a dict of {signal name: callback} pairs. The default set is::
    
        handlers = {'SIGTERM': self.bus.exit,
                    'SIGHUP': self.handle_SIGHUP,
                    'SIGUSR1': self.bus.graceful,
                   }
    
    The :func:`SignalHandler.handle_SIGHUP`` method calls
    :func:`bus.restart()<cherrypy.process.wspbus.Bus.restart>`
    if the process is daemonized, but
    :func:`bus.exit()<cherrypy.process.wspbus.Bus.exit>`
    if the process is attached to a TTY. This is because Unix window
    managers tend to send SIGHUP to terminal windows when the user closes them.
    
    Feel free to add signals which are not available on every platform. The
    :class:`SignalHandler` will ignore errors raised from attempting to register
    handlers for unknown signals.
    """
    
    handlers = {}
    """A map from signal names (e.g. 'SIGTERM') to handlers (e.g. bus.exit)."""
    
    signals = {}
    """A map from signal numbers to names."""
    
    for k, v in vars(_signal).items():
        if k.startswith('SIG') and not k.startswith('SIG_'):
            signals[v] = k
    del k, v
    
    def __init__(self, bus):
        self.bus = bus
        # Set default handlers
        self.handlers = {'SIGTERM': self.bus.exit,
                         'SIGHUP': self.handle_SIGHUP,
                         'SIGUSR1': self.bus.graceful,
                         }

        if sys.platform[:4] == 'java':
            del self.handlers['SIGUSR1']
            self.handlers['SIGUSR2'] = self.bus.graceful
            self.bus.log("SIGUSR1 cannot be set on the JVM platform. "
                         "Using SIGUSR2 instead.")
            self.handlers['SIGINT'] = self._jython_SIGINT_handler

        self._previous_handlers = {}
    
    def _jython_SIGINT_handler(self, signum=None, frame=None):
        # See http://bugs.jython.org/issue1313
        self.bus.log('Keyboard Interrupt: shutting down bus')
        self.bus.exit()
        
    def subscribe(self):
        """Subscribe self.handlers to signals."""
        for sig, func in self.handlers.items():
            try:
                self.set_handler(sig, func)
            except ValueError:
                pass
    
    def unsubscribe(self):
        """Unsubscribe self.handlers from signals."""
        for signum, handler in self._previous_handlers.items():
            signame = self.signals[signum]
            
            if handler is None:
                self.bus.log("Restoring %s handler to SIG_DFL." % signame)
                handler = _signal.SIG_DFL
            else:
                self.bus.log("Restoring %s handler %r." % (signame, handler))
            
            try:
                our_handler = _signal.signal(signum, handler)
                if our_handler is None:
                    self.bus.log("Restored old %s handler %r, but our "
                                 "handler was not registered." %
                                 (signame, handler), level=30)
            except ValueError:
                self.bus.log("Unable to restore %s handler %r." %
                             (signame, handler), level=40, traceback=True)
    
    def set_handler(self, signal, listener=None):
        """Subscribe a handler for the given signal (number or name).
        
        If the optional 'listener' argument is provided, it will be
        subscribed as a listener for the given signal's channel.
        
        If the given signal name or number is not available on the current
        platform, ValueError is raised.
        """
        if isinstance(signal, basestring):
            signum = getattr(_signal, signal, None)
            if signum is None:
                raise ValueError("No such signal: %r" % signal)
            signame = signal
        else:
            try:
                signame = self.signals[signal]
            except KeyError:
                raise ValueError("No such signal: %r" % signal)
            signum = signal
        
        prev = _signal.signal(signum, self._handle_signal)
        self._previous_handlers[signum] = prev
        
        if listener is not None:
            self.bus.log("Listening for %s." % signame)
            self.bus.subscribe(signame, listener)
    
    def _handle_signal(self, signum=None, frame=None):
        """Python signal handler (self.set_handler subscribes it for you)."""
        signame = self.signals[signum]
        self.bus.log("Caught signal %s." % signame)
        self.bus.publish(signame)
    
    def handle_SIGHUP(self):
        """Restart if daemonized, else exit."""
        if os.isatty(sys.stdin.fileno()):
            # not daemonized (may be foreground or background)
            self.bus.log("SIGHUP caught but not daemonized. Exiting.")
            self.bus.exit()
        else:
            self.bus.log("SIGHUP caught while daemonized. Restarting.")
            self.bus.restart()


try:
    import pwd, grp
except ImportError:
    pwd, grp = None, None


class DropPrivileges(SimplePlugin):
    """Drop privileges. uid/gid arguments not available on Windows.
    
    Special thanks to Gavin Baker: http://antonym.org/node/100.
    """
    
    def __init__(self, bus, umask=None, uid=None, gid=None):
        SimplePlugin.__init__(self, bus)
        self.finalized = False
        self.uid = uid
        self.gid = gid
        self.umask = umask
    
    def _get_uid(self):
        return self._uid
    def _set_uid(self, val):
        if val is not None:
            if pwd is None:
                self.bus.log("pwd module not available; ignoring uid.",
                             level=30)
                val = None
            elif isinstance(val, basestring):
                val = pwd.getpwnam(val)[2]
        self._uid = val
    uid = property(_get_uid, _set_uid,
        doc="The uid under which to run. Availability: Unix.")
    
    def _get_gid(self):
        return self._gid
    def _set_gid(self, val):
        if val is not None:
            if grp is None:
                self.bus.log("grp module not available; ignoring gid.",
                             level=30)
                val = None
            elif isinstance(val, basestring):
                val = grp.getgrnam(val)[2]
        self._gid = val
    gid = property(_get_gid, _set_gid,
        doc="The gid under which to run. Availability: Unix.")
    
    def _get_umask(self):
        return self._umask
    def _set_umask(self, val):
        if val is not None:
            try:
                os.umask
            except AttributeError:
                self.bus.log("umask function not available; ignoring umask.",
                             level=30)
                val = None
        self._umask = val
    umask = property(_get_umask, _set_umask,
        doc="""The default permission mode for newly created files and directories.
        
        Usually expressed in octal format, for example, ``0644``.
        Availability: Unix, Windows.
        """)
    
    def start(self):
        # uid/gid
        def current_ids():
            """Return the current (uid, gid) if available."""
            name, group = None, None
            if pwd:
                name = pwd.getpwuid(os.getuid())[0]
            if grp:
                group = grp.getgrgid(os.getgid())[0]
            return name, group
        
        if self.finalized:
            if not (self.uid is None and self.gid is None):
                self.bus.log('Already running as uid: %r gid: %r' %
                             current_ids())
        else:
            if self.uid is None and self.gid is None:
                if pwd or grp:
                    self.bus.log('uid/gid not set', level=30)
            else:
                self.bus.log('Started as uid: %r gid: %r' % current_ids())
                if self.gid is not None:
                    os.setgid(self.gid)
                    os.setgroups([])
                if self.uid is not None:
                    os.setuid(self.uid)
                self.bus.log('Running as uid: %r gid: %r' % current_ids())
        
        # umask
        if self.finalized:
            if self.umask is not None:
                self.bus.log('umask already set to: %03o' % self.umask)
        else:
            if self.umask is None:
                self.bus.log('umask not set', level=30)
            else:
                old_umask = os.umask(self.umask)
                self.bus.log('umask old: %03o, new: %03o' %
                             (old_umask, self.umask))
        
        self.finalized = True
    # This is slightly higher than the priority for server.start
    # in order to facilitate the most common use: starting on a low
    # port (which requires root) and then dropping to another user.
    start.priority = 77


class Daemonizer(SimplePlugin):
    """Daemonize the running script.
    
    Use this with a Web Site Process Bus via::
    
        Daemonizer(bus).subscribe()
    
    When this component finishes, the process is completely decoupled from
    the parent environment. Please note that when this component is used,
    the return code from the parent process will still be 0 if a startup
    error occurs in the forked children. Errors in the initial daemonizing
    process still return proper exit codes. Therefore, if you use this
    plugin to daemonize, don't use the return code as an accurate indicator
    of whether the process fully started. In fact, that return code only
    indicates if the process succesfully finished the first fork.
    """
    
    def __init__(self, bus, stdin='/dev/null', stdout='/dev/null',
                 stderr='/dev/null'):
        SimplePlugin.__init__(self, bus)
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.finalized = False
    
    def start(self):
        if self.finalized:
            self.bus.log('Already deamonized.')
        
        # forking has issues with threads:
        # http://www.opengroup.org/onlinepubs/000095399/functions/fork.html
        # "The general problem with making fork() work in a multi-threaded
        #  world is what to do with all of the threads..."
        # So we check for active threads:
        if threading.activeCount() != 1:
            self.bus.log('There are %r active threads. '
                         'Daemonizing now may cause strange failures.' %
                         threading.enumerate(), level=30)
        
        # See http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
        # (or http://www.faqs.org/faqs/unix-faq/programmer/faq/ section 1.7)
        # and http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/66012
        
        # Finish up with the current stdout/stderr
        sys.stdout.flush()
        sys.stderr.flush()
        
        # Do first fork.
        try:
            pid = os.fork()
            if pid == 0:
                # This is the child process. Continue.
                pass
            else:
                # This is the first parent. Exit, now that we've forked.
                self.bus.log('Forking once.')
                os._exit(0)
        except OSError:
            # Python raises OSError rather than returning negative numbers.
            exc = sys.exc_info()[1]
            sys.exit("%s: fork #1 failed: (%d) %s\n"
                     % (sys.argv[0], exc.errno, exc.strerror))
        
        os.setsid()
        
        # Do second fork
        try:
            pid = os.fork()
            if pid > 0:
                self.bus.log('Forking twice.')
                os._exit(0) # Exit second parent
        except OSError:
            exc = sys.exc_info()[1]
            sys.exit("%s: fork #2 failed: (%d) %s\n"
                     % (sys.argv[0], exc.errno, exc.strerror))
        
        os.chdir("/")
        os.umask(0)
        
        si = open(self.stdin, "r")
        so = open(self.stdout, "a+")
        se = open(self.stderr, "a+")

        # os.dup2(fd, fd2) will close fd2 if necessary,
        # so we don't explicitly close stdin/out/err.
        # See http://docs.python.org/lib/os-fd-ops.html
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())
        
        self.bus.log('Daemonized to PID: %s' % os.getpid())
        self.finalized = True
    start.priority = 65


class PIDFile(SimplePlugin):
    """Maintain a PID file via a WSPBus."""
    
    def __init__(self, bus, pidfile):
        SimplePlugin.__init__(self, bus)
        self.pidfile = pidfile
        self.finalized = False
    
    def start(self):
        pid = os.getpid()
        if self.finalized:
            self.bus.log('PID %r already written to %r.' % (pid, self.pidfile))
        else:
            open(self.pidfile, "wb").write(ntob("%s" % pid, 'utf8'))
            self.bus.log('PID %r written to %r.' % (pid, self.pidfile))
            self.finalized = True
    start.priority = 70
    
    def exit(self):
        try:
            os.remove(self.pidfile)
            self.bus.log('PID file removed: %r.' % self.pidfile)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            pass


class PerpetualTimer(threading._Timer):
    """A responsive subclass of threading._Timer whose run() method repeats.
    
    Use this timer only when you really need a very interruptible timer;
    this checks its 'finished' condition up to 20 times a second, which can
    results in pretty high CPU usage 
    """
    
    def run(self):
        while True:
            self.finished.wait(self.interval)
            if self.finished.isSet():
                return
            try:
                self.function(*self.args, **self.kwargs)
            except Exception:
                self.bus.log("Error in perpetual timer thread function %r." %
                             self.function, level=40, traceback=True)
                # Quit on first error to avoid massive logs.
                raise


class BackgroundTask(threading.Thread):
    """A subclass of threading.Thread whose run() method repeats.
    
    Use this class for most repeating tasks. It uses time.sleep() to wait
    for each interval, which isn't very responsive; that is, even if you call
    self.cancel(), you'll have to wait until the sleep() call finishes before
    the thread stops. To compensate, it defaults to being daemonic, which means
    it won't delay stopping the whole process.
    """
    
    def __init__(self, interval, function, args=[], kwargs={}, bus=None):
        threading.Thread.__init__(self)
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.running = False
        self.bus = bus
    
    def cancel(self):
        self.running = False
    
    def run(self):
        self.running = True
        while self.running:
            time.sleep(self.interval)
            if not self.running:
                return
            try:
                self.function(*self.args, **self.kwargs)
            except Exception:
                if self.bus:
                    self.bus.log("Error in background task thread function %r."
                                 % self.function, level=40, traceback=True)
                # Quit on first error to avoid massive logs.
                raise
    
    def _set_daemon(self):
        return True


class Monitor(SimplePlugin):
    """WSPBus listener to periodically run a callback in its own thread."""
    
    callback = None
    """The function to call at intervals."""
    
    frequency = 60
    """The time in seconds between callback runs."""
    
    thread = None
    """A :class:`BackgroundTask<cherrypy.process.plugins.BackgroundTask>` thread."""
    
    def __init__(self, bus, callback, frequency=60, name=None):
        SimplePlugin.__init__(self, bus)
        self.callback = callback
        self.frequency = frequency
        self.thread = None
        self.name = name
    
    def start(self):
        """Start our callback in its own background thread."""
        if self.frequency > 0:
            threadname = self.name or self.__class__.__name__
            if self.thread is None:
                self.thread = BackgroundTask(self.frequency, self.callback,
                                             bus = self.bus)
                self.thread.setName(threadname)
                self.thread.start()
                self.bus.log("Started monitor thread %r." % threadname)
            else:
                self.bus.log("Monitor thread %r already started." % threadname)
    start.priority = 70
    
    def stop(self):
        """Stop our callback's background task thread."""
        if self.thread is None:
            self.bus.log("No thread running for %s." % self.name or self.__class__.__name__)
        else:
            if self.thread is not threading.currentThread():
                name = self.thread.getName()
                self.thread.cancel()
                if not get_daemon(self.thread):
                    self.bus.log("Joining %r" % name)
                    self.thread.join()
                self.bus.log("Stopped thread %r." % name)
            self.thread = None
    
    def graceful(self):
        """Stop the callback's background task thread and restart it."""
        self.stop()
        self.start()


class Autoreloader(Monitor):
    """Monitor which re-executes the process when files change.
    
    This :ref:`plugin<plugins>` restarts the process (via :func:`os.execv`)
    if any of the files it monitors change (or is deleted). By default, the
    autoreloader monitors all imported modules; you can add to the
    set by adding to ``autoreload.files``::
    
        cherrypy.engine.autoreload.files.add(myFile)
    
    If there are imported files you do *not* wish to monitor, you can adjust the
    ``match`` attribute, a regular expression. For example, to stop monitoring
    cherrypy itself::
    
        cherrypy.engine.autoreload.match = r'^(?!cherrypy).+'
    
    Like all :class:`Monitor<cherrypy.process.plugins.Monitor>` plugins,
    the autoreload plugin takes a ``frequency`` argument. The default is
    1 second; that is, the autoreloader will examine files once each second.
    """
    
    files = None
    """The set of files to poll for modifications."""
    
    frequency = 1
    """The interval in seconds at which to poll for modified files."""
    
    match = '.*'
    """A regular expression by which to match filenames."""
    
    def __init__(self, bus, frequency=1, match='.*'):
        self.mtimes = {}
        self.files = set()
        self.match = match
        Monitor.__init__(self, bus, self.run, frequency)
    
    def start(self):
        """Start our own background task thread for self.run."""
        if self.thread is None:
            self.mtimes = {}
        Monitor.start(self)
    start.priority = 70 
    
    def sysfiles(self):
        """Return a Set of sys.modules filenames to monitor."""
        files = set()
        for k, m in sys.modules.items():
            if re.match(self.match, k):
                if hasattr(m, '__loader__') and hasattr(m.__loader__, 'archive'):
                    f = m.__loader__.archive
                else:
                    f = getattr(m, '__file__', None)
                    if f is not None and not os.path.isabs(f):
                        # ensure absolute paths so a os.chdir() in the app doesn't break me
                        f = os.path.normpath(os.path.join(_module__file__base, f))
                files.add(f)
        return files
    
    def run(self):
        """Reload the process if registered files have been modified."""
        for filename in self.sysfiles() | self.files:
            if filename:
                if filename.endswith('.pyc'):
                    filename = filename[:-1]
                
                oldtime = self.mtimes.get(filename, 0)
                if oldtime is None:
                    # Module with no .py file. Skip it.
                    continue
                
                try:
                    mtime = os.stat(filename).st_mtime
                except OSError:
                    # Either a module with no .py file, or it's been deleted.
                    mtime = None
                
                if filename not in self.mtimes:
                    # If a module has no .py file, this will be None.
                    self.mtimes[filename] = mtime
                else:
                    if mtime is None or mtime > oldtime:
                        # The file has been deleted or modified.
                        self.bus.log("Restarting because %s changed." % filename)
                        self.thread.cancel()
                        self.bus.log("Stopped thread %r." % self.thread.getName())
                        self.bus.restart()
                        return


class ThreadManager(SimplePlugin):
    """Manager for HTTP request threads.
    
    If you have control over thread creation and destruction, publish to
    the 'acquire_thread' and 'release_thread' channels (for each thread).
    This will register/unregister the current thread and publish to
    'start_thread' and 'stop_thread' listeners in the bus as needed.
    
    If threads are created and destroyed by code you do not control
    (e.g., Apache), then, at the beginning of every HTTP request,
    publish to 'acquire_thread' only. You should not publish to
    'release_thread' in this case, since you do not know whether
    the thread will be re-used or not. The bus will call
    'stop_thread' listeners for you when it stops.
    """
    
    threads = None
    """A map of {thread ident: index number} pairs."""
    
    def __init__(self, bus):
        self.threads = {}
        SimplePlugin.__init__(self, bus)
        self.bus.listeners.setdefault('acquire_thread', set())
        self.bus.listeners.setdefault('start_thread', set())
        self.bus.listeners.setdefault('release_thread', set())
        self.bus.listeners.setdefault('stop_thread', set())

    def acquire_thread(self):
        """Run 'start_thread' listeners for the current thread.
        
        If the current thread has already been seen, any 'start_thread'
        listeners will not be run again.
        """
        thread_ident = get_thread_ident()
        if thread_ident not in self.threads:
            # We can't just use get_ident as the thread ID
            # because some platforms reuse thread ID's.
            i = len(self.threads) + 1
            self.threads[thread_ident] = i
            self.bus.publish('start_thread', i)
    
    def release_thread(self):
        """Release the current thread and run 'stop_thread' listeners."""
        thread_ident = get_thread_ident()
        i = self.threads.pop(thread_ident, None)
        if i is not None:
            self.bus.publish('stop_thread', i)
    
    def stop(self):
        """Release all threads and run all 'stop_thread' listeners."""
        for thread_ident, i in self.threads.items():
            self.bus.publish('stop_thread', i)
        self.threads.clear()
    graceful = stop

