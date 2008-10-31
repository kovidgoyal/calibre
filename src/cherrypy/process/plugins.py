"""Site services for use with a Web Site Process Bus."""

import os
import re
try:
    set
except NameError:
    from sets import Set as set
import signal as _signal
import sys
import time
import threading


class SimplePlugin(object):
    """Plugin base class which auto-subscribes methods for known channels."""
    
    def __init__(self, bus):
        self.bus = bus
    
    def subscribe(self):
        """Register this object as a (multi-channel) listener on the bus."""
        for channel in self.bus.listeners:
            method = getattr(self, channel, None)
            if method is not None:
                self.bus.subscribe(channel, method)
    
    def unsubscribe(self):
        """Unregister this object as a listener on the bus."""
        for channel in self.bus.listeners:
            method = getattr(self, channel, None)
            if method is not None:
                self.bus.unsubscribe(channel, method)



class SignalHandler(object):
    """Register bus channels (and listeners) for system signals.
    
    By default, instantiating this object subscribes the following signals
    and listeners:
    
        TERM: bus.exit
        HUP : bus.restart
        USR1: bus.graceful
    """
    
    # Map from signal numbers to names
    signals = {}
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
        
        self._previous_handlers = {}
    
    def subscribe(self):
        for sig, func in self.handlers.iteritems():
            try:
                self.set_handler(sig, func)
            except ValueError:
                pass
    
    def unsubscribe(self):
        for signum, handler in self._previous_handlers.iteritems():
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
    uid = property(_get_uid, _set_uid, doc="The uid under which to run.")
    
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
    gid = property(_get_gid, _set_gid, doc="The gid under which to run.")
    
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
    umask = property(_get_umask, _set_umask, doc="The umask under which to run.")
    
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
                    os.setgid(gid)
                if self.uid is not None:
                    os.setuid(uid)
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
    start.priority = 75


class Daemonizer(SimplePlugin):
    """Daemonize the running script.
    
    Use this with a Web Site Process Bus via:
        
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
        except OSError, exc:
            # Python raises OSError rather than returning negative numbers.
            sys.exit("%s: fork #1 failed: (%d) %s\n"
                     % (sys.argv[0], exc.errno, exc.strerror))
        
        os.setsid()
        
        # Do second fork
        try:
            pid = os.fork()
            if pid > 0:
                self.bus.log('Forking twice.')
                os._exit(0) # Exit second parent
        except OSError, exc:
            sys.exit("%s: fork #2 failed: (%d) %s\n"
                     % (sys.argv[0], exc.errno, exc.strerror))
        
        os.chdir("/")
        os.umask(0)
        
        si = open(self.stdin, "r")
        so = open(self.stdout, "a+")
        se = open(self.stderr, "a+", 0)

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
            open(self.pidfile, "wb").write(str(pid))
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
    """A subclass of threading._Timer whose run() method repeats."""
    
    def run(self):
        while True:
            self.finished.wait(self.interval)
            if self.finished.isSet():
                return
            self.function(*self.args, **self.kwargs)


class Monitor(SimplePlugin):
    """WSPBus listener to periodically run a callback in its own thread.
    
    bus: a Web Site Process Bus object.
    callback: the function to call at intervals.
    frequency: the time in seconds between callback runs.
    """
    
    frequency = 60
    
    def __init__(self, bus, callback, frequency=60):
        SimplePlugin.__init__(self, bus)
        self.callback = callback
        self.frequency = frequency
        self.thread = None
    
    def start(self):
        """Start our callback in its own perpetual timer thread."""
        if self.frequency > 0:
            threadname = self.__class__.__name__
            if self.thread is None:
                self.thread = PerpetualTimer(self.frequency, self.callback)
                self.thread.setName(threadname)
                self.thread.start()
                self.bus.log("Started monitor thread %r." % threadname)
            else:
                self.bus.log("Monitor thread %r already started." % threadname)
    start.priority = 70
    
    def stop(self):
        """Stop our callback's perpetual timer thread."""
        if self.thread is None:
            self.bus.log("No thread running for %s." % self.__class__.__name__)
        else:
            if self.thread is not threading.currentThread():
                name = self.thread.getName()
                self.thread.cancel()
                self.thread.join()
                self.bus.log("Stopped thread %r." % name)
            self.thread = None
    
    def graceful(self):
        """Stop the callback's perpetual timer thread and restart it."""
        self.stop()
        self.start()


class Autoreloader(Monitor):
    """Monitor which re-executes the process when files change."""
    
    frequency = 1
    match = '.*'
    
    def __init__(self, bus, frequency=1, match='.*'):
        self.mtimes = {}
        self.files = set()
        self.match = match
        Monitor.__init__(self, bus, self.run, frequency)
    
    def start(self):
        """Start our own perpetual timer thread for self.run."""
        if self.thread is None:
            self.mtimes = {}
        Monitor.start(self)
    start.priority = 70 
    
    def run(self):
        """Reload the process if registered files have been modified."""
        sysfiles = set()
        for k, m in sys.modules.items():
            if re.match(self.match, k):
                if hasattr(m, '__loader__'):
                    if hasattr(m.__loader__, 'archive'):
                        k = m.__loader__.archive
                k = getattr(m, '__file__', None)
                sysfiles.add(k)
        
        for filename in sysfiles | self.files:
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
    
    def __init__(self, bus):
        self.threads = {}
        SimplePlugin.__init__(self, bus)
        self.bus.listeners.setdefault('acquire_thread', set())
        self.bus.listeners.setdefault('release_thread', set())
    
    def acquire_thread(self):
        """Run 'start_thread' listeners for the current thread.
        
        If the current thread has already been seen, any 'start_thread'
        listeners will not be run again.
        """
        thread_ident = threading._get_ident()
        if thread_ident not in self.threads:
            # We can't just use _get_ident as the thread ID
            # because some platforms reuse thread ID's.
            i = len(self.threads) + 1
            self.threads[thread_ident] = i
            self.bus.publish('start_thread', i)
    
    def release_thread(self):
        """Release the current thread and run 'stop_thread' listeners."""
        thread_ident = threading._get_ident()
        i = self.threads.pop(thread_ident, None)
        if i is not None:
            self.bus.publish('stop_thread', i)
    
    def stop(self):
        """Release all threads and run all 'stop_thread' listeners."""
        for thread_ident, i in self.threads.iteritems():
            self.bus.publish('stop_thread', i)
        self.threads.clear()
    graceful = stop

