"""An implementation of the Web Site Process Bus.

This module is completely standalone, depending only on the stdlib.

Web Site Process Bus
--------------------

A Bus object is used to contain and manage site-wide behavior:
daemonization, HTTP server start/stop, process reload, signal handling,
drop privileges, PID file management, logging for all of these,
and many more.

In addition, a Bus object provides a place for each web framework
to register code that runs in response to site-wide events (like
process start and stop), or which controls or otherwise interacts with
the site-wide components mentioned above. For example, a framework which
uses file-based templates would add known template filenames to an
autoreload component.

Ideally, a Bus object will be flexible enough to be useful in a variety
of invocation scenarios:

 1. The deployer starts a site from the command line via a
    framework-neutral deployment script; applications from multiple frameworks
    are mixed in a single site. Command-line arguments and configuration
    files are used to define site-wide components such as the HTTP server,
    WSGI component graph, autoreload behavior, signal handling, etc.
 2. The deployer starts a site via some other process, such as Apache;
    applications from multiple frameworks are mixed in a single site.
    Autoreload and signal handling (from Python at least) are disabled.
 3. The deployer starts a site via a framework-specific mechanism;
    for example, when running tests, exploring tutorials, or deploying
    single applications from a single framework. The framework controls
    which site-wide components are enabled as it sees fit.

The Bus object in this package uses topic-based publish-subscribe
messaging to accomplish all this. A few topic channels are built in
('start', 'stop', 'exit', 'graceful', 'log', and 'main'). Frameworks and
site containers are free to define their own. If a message is sent to a
channel that has not been defined or has no listeners, there is no effect.

In general, there should only ever be a single Bus object per process.
Frameworks and site containers share a single Bus object by publishing
messages and subscribing listeners.

The Bus object works as a finite state machine which models the current
state of the process. Bus methods move it from one state to another;
those methods then publish to subscribed listeners on the channel for
the new state.::

                        O
                        |
                        V
       STOPPING --> STOPPED --> EXITING -> X
          A   A         |
          |    \___     |
          |        \    |
          |         V   V
        STARTED <-- STARTING

"""

import atexit
import os
import sys
import threading
import time
import traceback as _traceback
import warnings

from cherrypy._cpcompat import set

# Here I save the value of os.getcwd(), which, if I am imported early enough,
# will be the directory from which the startup script was run.  This is needed
# by _do_execv(), to change back to the original directory before execv()ing a
# new process.  This is a defense against the application having changed the
# current working directory (which could make sys.executable "not found" if
# sys.executable is a relative-path, and/or cause other problems).
_startup_cwd = os.getcwd()

class ChannelFailures(Exception):
    """Exception raised when errors occur in a listener during Bus.publish()."""
    delimiter = '\n'
    
    def __init__(self, *args, **kwargs):
        # Don't use 'super' here; Exceptions are old-style in Py2.4
        # See http://www.cherrypy.org/ticket/959
        Exception.__init__(self, *args, **kwargs)
        self._exceptions = list()
    
    def handle_exception(self):
        """Append the current exception to self."""
        self._exceptions.append(sys.exc_info()[1])
    
    def get_instances(self):
        """Return a list of seen exception instances."""
        return self._exceptions[:]
    
    def __str__(self):
        exception_strings = map(repr, self.get_instances())
        return self.delimiter.join(exception_strings)

    __repr__ = __str__

    def __bool__(self):
        return bool(self._exceptions)
    __nonzero__ = __bool__

# Use a flag to indicate the state of the bus.
class _StateEnum(object):
    class State(object):
        name = None
        def __repr__(self):
            return "states.%s" % self.name
    
    def __setattr__(self, key, value):
        if isinstance(value, self.State):
            value.name = key
        object.__setattr__(self, key, value)
states = _StateEnum()
states.STOPPED = states.State()
states.STARTING = states.State()
states.STARTED = states.State()
states.STOPPING = states.State()
states.EXITING = states.State()


try:
    import fcntl
except ImportError:
    max_files = 0
else:
    try:
        max_files = os.sysconf('SC_OPEN_MAX')
    except AttributeError:
        max_files = 1024


class Bus(object):
    """Process state-machine and messenger for HTTP site deployment.
    
    All listeners for a given channel are guaranteed to be called even
    if others at the same channel fail. Each failure is logged, but
    execution proceeds on to the next listener. The only way to stop all
    processing from inside a listener is to raise SystemExit and stop the
    whole server.
    """
    
    states = states
    state = states.STOPPED
    execv = False
    max_cloexec_files = max_files
    
    def __init__(self):
        self.execv = False
        self.state = states.STOPPED
        self.listeners = dict(
            [(channel, set()) for channel
             in ('start', 'stop', 'exit', 'graceful', 'log', 'main')])
        self._priorities = {}
    
    def subscribe(self, channel, callback, priority=None):
        """Add the given callback at the given channel (if not present)."""
        if channel not in self.listeners:
            self.listeners[channel] = set()
        self.listeners[channel].add(callback)
        
        if priority is None:
            priority = getattr(callback, 'priority', 50)
        self._priorities[(channel, callback)] = priority
    
    def unsubscribe(self, channel, callback):
        """Discard the given callback (if present)."""
        listeners = self.listeners.get(channel)
        if listeners and callback in listeners:
            listeners.discard(callback)
            del self._priorities[(channel, callback)]
    
    def publish(self, channel, *args, **kwargs):
        """Return output of all subscribers for the given channel."""
        if channel not in self.listeners:
            return []
        
        exc = ChannelFailures()
        output = []
        
        items = [(self._priorities[(channel, listener)], listener)
                 for listener in self.listeners[channel]]
        try:
            items.sort(key=lambda item: item[0])
        except TypeError:
            # Python 2.3 had no 'key' arg, but that doesn't matter
            # since it could sort dissimilar types just fine.
            items.sort()
        for priority, listener in items:
            try:
                output.append(listener(*args, **kwargs))
            except KeyboardInterrupt:
                raise
            except SystemExit:
                e = sys.exc_info()[1]
                # If we have previous errors ensure the exit code is non-zero
                if exc and e.code == 0:
                    e.code = 1
                raise
            except:
                exc.handle_exception()
                if channel == 'log':
                    # Assume any further messages to 'log' will fail.
                    pass
                else:
                    self.log("Error in %r listener %r" % (channel, listener),
                             level=40, traceback=True)
        if exc:
            raise exc
        return output
    
    def _clean_exit(self):
        """An atexit handler which asserts the Bus is not running."""
        if self.state != states.EXITING:
            warnings.warn(
                "The main thread is exiting, but the Bus is in the %r state; "
                "shutting it down automatically now. You must either call "
                "bus.block() after start(), or call bus.exit() before the "
                "main thread exits." % self.state, RuntimeWarning)
            self.exit()
    
    def start(self):
        """Start all services."""
        atexit.register(self._clean_exit)
        
        self.state = states.STARTING
        self.log('Bus STARTING')
        try:
            self.publish('start')
            self.state = states.STARTED
            self.log('Bus STARTED')
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            self.log("Shutting down due to error in start listener:",
                     level=40, traceback=True)
            e_info = sys.exc_info()[1]
            try:
                self.exit()
            except:
                # Any stop/exit errors will be logged inside publish().
                pass
            # Re-raise the original error
            raise e_info
    
    def exit(self):
        """Stop all services and prepare to exit the process."""
        exitstate = self.state
        try:
            self.stop()
            
            self.state = states.EXITING
            self.log('Bus EXITING')
            self.publish('exit')
            # This isn't strictly necessary, but it's better than seeing
            # "Waiting for child threads to terminate..." and then nothing.
            self.log('Bus EXITED')
        except:
            # This method is often called asynchronously (whether thread,
            # signal handler, console handler, or atexit handler), so we
            # can't just let exceptions propagate out unhandled.
            # Assume it's been logged and just die.
            os._exit(70) # EX_SOFTWARE
        
        if exitstate == states.STARTING:
            # exit() was called before start() finished, possibly due to
            # Ctrl-C because a start listener got stuck. In this case,
            # we could get stuck in a loop where Ctrl-C never exits the
            # process, so we just call os.exit here.
            os._exit(70) # EX_SOFTWARE
    
    def restart(self):
        """Restart the process (may close connections).
        
        This method does not restart the process from the calling thread;
        instead, it stops the bus and asks the main thread to call execv.
        """
        self.execv = True
        self.exit()
    
    def graceful(self):
        """Advise all services to reload."""
        self.log('Bus graceful')
        self.publish('graceful')
    
    def block(self, interval=0.1):
        """Wait for the EXITING state, KeyboardInterrupt or SystemExit.
        
        This function is intended to be called only by the main thread.
        After waiting for the EXITING state, it also waits for all threads
        to terminate, and then calls os.execv if self.execv is True. This
        design allows another thread to call bus.restart, yet have the main
        thread perform the actual execv call (required on some platforms).
        """
        try:
            self.wait(states.EXITING, interval=interval, channel='main')
        except (KeyboardInterrupt, IOError):
            # The time.sleep call might raise
            # "IOError: [Errno 4] Interrupted function call" on KBInt.
            self.log('Keyboard Interrupt: shutting down bus')
            self.exit()
        except SystemExit:
            self.log('SystemExit raised: shutting down bus')
            self.exit()
            raise
        
        # Waiting for ALL child threads to finish is necessary on OS X.
        # See http://www.cherrypy.org/ticket/581.
        # It's also good to let them all shut down before allowing
        # the main thread to call atexit handlers.
        # See http://www.cherrypy.org/ticket/751.
        self.log("Waiting for child threads to terminate...")
        for t in threading.enumerate():
            if t != threading.currentThread() and t.isAlive():
                # Note that any dummy (external) threads are always daemonic.
                if hasattr(threading.Thread, "daemon"):
                    # Python 2.6+
                    d = t.daemon
                else:
                    d = t.isDaemon()
                if not d:
                    self.log("Waiting for thread %s." % t.getName())
                    t.join()
        
        if self.execv:
            self._do_execv()
    
    def wait(self, state, interval=0.1, channel=None):
        """Poll for the given state(s) at intervals; publish to channel."""
        if isinstance(state, (tuple, list)):
            states = state
        else:
            states = [state]
        
        def _wait():
            while self.state not in states:
                time.sleep(interval)
                self.publish(channel)
        
        # From http://psyco.sourceforge.net/psycoguide/bugs.html:
        # "The compiled machine code does not include the regular polling
        # done by Python, meaning that a KeyboardInterrupt will not be
        # detected before execution comes back to the regular Python
        # interpreter. Your program cannot be interrupted if caught
        # into an infinite Psyco-compiled loop."
        try:
            sys.modules['psyco'].cannotcompile(_wait)
        except (KeyError, AttributeError):
            pass
        
        _wait()
    
    def _do_execv(self):
        """Re-execute the current process.
        
        This must be called from the main thread, because certain platforms
        (OS X) don't allow execv to be called in a child thread very well.
        """
        args = sys.argv[:]
        self.log('Re-spawning %s' % ' '.join(args))
        
        if sys.platform[:4] == 'java':
            from _systemrestart import SystemRestart
            raise SystemRestart
        else:
            args.insert(0, sys.executable)
            if sys.platform == 'win32':
                args = ['"%s"' % arg for arg in args]

            os.chdir(_startup_cwd)
            if self.max_cloexec_files:
                self._set_cloexec()
            os.execv(sys.executable, args)
    
    def _set_cloexec(self):
        """Set the CLOEXEC flag on all open files (except stdin/out/err).
        
        If self.max_cloexec_files is an integer (the default), then on
        platforms which support it, it represents the max open files setting
        for the operating system. This function will be called just before
        the process is restarted via os.execv() to prevent open files
        from persisting into the new process.
        
        Set self.max_cloexec_files to 0 to disable this behavior.
        """
        for fd in range(3, self.max_cloexec_files): # skip stdin/out/err
            try:
                flags = fcntl.fcntl(fd, fcntl.F_GETFD)
            except IOError:
                continue
            fcntl.fcntl(fd, fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)
    
    def stop(self):
        """Stop all services."""
        self.state = states.STOPPING
        self.log('Bus STOPPING')
        self.publish('stop')
        self.state = states.STOPPED
        self.log('Bus STOPPED')
    
    def start_with_callback(self, func, args=None, kwargs=None):
        """Start 'func' in a new thread T, then start self (and return T)."""
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}
        args = (func,) + args
        
        def _callback(func, *a, **kw):
            self.wait(states.STARTED)
            func(*a, **kw)
        t = threading.Thread(target=_callback, args=args, kwargs=kwargs)
        t.setName('Bus Callback ' + t.getName())
        t.start()
        
        self.start()
        
        return t
    
    def log(self, msg="", level=20, traceback=False):
        """Log the given message. Append the last traceback if requested."""
        if traceback:
            msg += "\n" + "".join(_traceback.format_exception(*sys.exc_info()))
        self.publish('log', msg, level)

bus = Bus()
