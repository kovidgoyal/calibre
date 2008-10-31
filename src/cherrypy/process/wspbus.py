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

 1. The deployer starts a site from the command line via a framework-
     neutral deployment script; applications from multiple frameworks
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
('start', 'stop', 'exit', and 'graceful'). Frameworks and site containers
are free to define their own. If a message is sent to a channel that has
not been defined or has no listeners, there is no effect.

In general, there should only ever be a single Bus object per process.
Frameworks and site containers share a single Bus object by publishing
messages and subscribing listeners.

The Bus object works as a finite state machine which models the current
state of the process. Bus methods move it from one state to another;
those methods then publish to subscribed listeners on the channel for
the new state.

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
try:
    set
except NameError:
    from sets import Set as set
import sys
import threading
import time
import traceback as _traceback
import warnings


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
    
    def __init__(self):
        self.execv = False
        self.state = states.STOPPED
        self.listeners = dict(
            [(channel, set()) for channel
             in ('start', 'stop', 'exit', 'graceful', 'log')])
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
        
        exc = None
        output = []
        
        items = [(self._priorities[(channel, listener)], listener)
                 for listener in self.listeners[channel]]
        items.sort()
        for priority, listener in items:
            try:
                output.append(listener(*args, **kwargs))
            except KeyboardInterrupt:
                raise
            except SystemExit, e:
                # If we have previous errors ensure the exit code is non-zero
                if exc and e.code == 0:
                    e.code = 1
                raise
            except:
                self.log("Error in %r listener %r" % (channel, listener),
                         level=40, traceback=True)
                exc = sys.exc_info()[1]
        if exc:
            raise
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
            e_info = sys.exc_info()
            try:
                self.exit()
            except:
                # Any stop/exit errors will be logged inside publish().
                pass
            raise e_info[0], e_info[1], e_info[2]
    
    def exit(self):
        """Stop all services and prepare to exit the process."""
        self.stop()
        
        self.state = states.EXITING
        self.log('Bus EXITING')
        self.publish('exit')
        # This isn't strictly necessary, but it's better than seeing
        # "Waiting for child threads to terminate..." and then nothing.
        self.log('Bus EXITED')
    
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
        """Wait for the EXITING state, KeyboardInterrupt or SystemExit."""
        try:
            self.wait(states.EXITING, interval=interval)
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
            if (t != threading.currentThread() and t.isAlive()
                # Note that any dummy (external) threads are always daemonic.
                and not t.isDaemon()):
                t.join()
        
        if self.execv:
            self._do_execv()
    
    def wait(self, state, interval=0.1):
        """Wait for the given state."""
        def _wait():
            while self.state != state:
                time.sleep(interval)
        
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
        args.insert(0, sys.executable)
        if sys.platform == 'win32':
            args = ['"%s"' % arg for arg in args]
        
        os.execv(sys.executable, args)
    
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
            exc = sys.exc_info()
            msg += "\n" + "".join(_traceback.format_exception(*exc))
        self.publish('log', msg, level)

bus = Bus()
