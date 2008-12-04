"""Windows service. Requires pywin32."""

import os
import thread
import win32api
import win32con
import win32event
import win32service
import win32serviceutil

from cherrypy.process import wspbus, plugins


class ConsoleCtrlHandler(plugins.SimplePlugin):
    """A WSPBus plugin for handling Win32 console events (like Ctrl-C)."""
    
    def __init__(self, bus):
        self.is_set = False
        plugins.SimplePlugin.__init__(self, bus)
    
    def start(self):
        if self.is_set:
            self.bus.log('Handler for console events already set.', level=40)
            return
        
        result = win32api.SetConsoleCtrlHandler(self.handle, 1)
        if result == 0:
            self.bus.log('Could not SetConsoleCtrlHandler (error %r)' %
                         win32api.GetLastError(), level=40)
        else:
            self.bus.log('Set handler for console events.', level=40)
            self.is_set = True
    
    def stop(self):
        if not self.is_set:
            self.bus.log('Handler for console events already off.', level=40)
            return
        
        try:
            result = win32api.SetConsoleCtrlHandler(self.handle, 0)
        except ValueError:
            # "ValueError: The object has not been registered"
            result = 1
        
        if result == 0:
            self.bus.log('Could not remove SetConsoleCtrlHandler (error %r)' %
                         win32api.GetLastError(), level=40)
        else:
            self.bus.log('Removed handler for console events.', level=40)
            self.is_set = False
    
    def handle(self, event):
        """Handle console control events (like Ctrl-C)."""
        if event in (win32con.CTRL_C_EVENT, win32con.CTRL_LOGOFF_EVENT,
                     win32con.CTRL_BREAK_EVENT, win32con.CTRL_SHUTDOWN_EVENT,
                     win32con.CTRL_CLOSE_EVENT):
            self.bus.log('Console event %s: shutting down bus' % event)
            
            # Remove self immediately so repeated Ctrl-C doesn't re-call it.
            try:
                self.stop()
            except ValueError:
                pass
            
            self.bus.exit()
            # 'First to return True stops the calls'
            return 1
        return 0


class Win32Bus(wspbus.Bus):
    """A Web Site Process Bus implementation for Win32.
    
    Instead of time.sleep, this bus blocks using native win32event objects.
    """
    
    def __init__(self):
        self.events = {}
        wspbus.Bus.__init__(self)
    
    def _get_state_event(self, state):
        """Return a win32event for the given state (creating it if needed)."""
        try:
            return self.events[state]
        except KeyError:
            event = win32event.CreateEvent(None, 0, 0,
                                           u"WSPBus %s Event (pid=%r)" %
                                           (state.name, os.getpid()))
            self.events[state] = event
            return event
    
    def _get_state(self):
        return self._state
    def _set_state(self, value):
        self._state = value
        event = self._get_state_event(value)
        win32event.PulseEvent(event)
    state = property(_get_state, _set_state)
    
    def wait(self, state, interval=0.1):
        """Wait for the given state(s), KeyboardInterrupt or SystemExit.
        
        Since this class uses native win32event objects, the interval
        argument is ignored.
        """
        if isinstance(state, (tuple, list)):
            # Don't wait for an event that beat us to the punch ;)
            if self.state not in state:
                events = tuple([self._get_state_event(s) for s in state])
                win32event.WaitForMultipleObjects(events, 0, win32event.INFINITE)
        else:
            # Don't wait for an event that beat us to the punch ;)
            if self.state != state:
                event = self._get_state_event(state)
                win32event.WaitForSingleObject(event, win32event.INFINITE)


class _ControlCodes(dict):
    """Control codes used to "signal" a service via ControlService.
    
    User-defined control codes are in the range 128-255. We generally use
    the standard Python value for the Linux signal and add 128. Example:
    
        >>> signal.SIGUSR1
        10
        control_codes['graceful'] = 128 + 10
    """
    
    def key_for(self, obj):
        """For the given value, return its corresponding key."""
        for key, val in self.iteritems():
            if val is obj:
                return key
        raise ValueError("The given object could not be found: %r" % obj)

control_codes = _ControlCodes({'graceful': 138})


def signal_child(service, command):
    if command == 'stop':
        win32serviceutil.StopService(service)
    elif command == 'restart':
        win32serviceutil.RestartService(service)
    else:
        win32serviceutil.ControlService(service, control_codes[command])


class PyWebService(win32serviceutil.ServiceFramework):
    """Python Web Service."""
    
    _svc_name_ = "Python Web Service"
    _svc_display_name_ = "Python Web Service"
    _svc_deps_ = None        # sequence of service names on which this depends
    _exe_name_ = "pywebsvc"
    _exe_args_ = None        # Default to no arguments
    
    # Only exists on Windows 2000 or later, ignored on windows NT
    _svc_description_ = "Python Web Service"
    
    def SvcDoRun(self):
        from cherrypy import process
        process.bus.start()
        process.bus.block()
    
    def SvcStop(self):
        from cherrypy import process
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        process.bus.exit()
    
    def SvcOther(self, control):
        process.bus.publish(control_codes.key_for(control))


if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(PyWebService)
