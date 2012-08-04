__license__   = 'GPL v3'
__copyright__ = '2008, Kovid Goyal <kovid at kovidgoyal.net>'
"""
Defines the errors that the device drivers generate.

G{classtree ProtocolError}
"""

class ProtocolError(Exception):
    """ The base class for all exceptions in this package """
    def __init__(self, msg):
        Exception.__init__(self, msg)

class TimeoutError(ProtocolError):
    """ There was a timeout during communication """
    def __init__(self, func_name):
        ProtocolError.__init__(self, \
        "There was a timeout while communicating with the device in function: "\
        +func_name)

class DeviceError(ProtocolError):
    """ Raised when device is not found """
    def __init__(self, msg=None):
        if msg is None:
            msg = "Unable to find SONY Reader. Is it connected?"
        ProtocolError.__init__(self, msg)

class UserFeedback(DeviceError):
   INFO = 0
   WARN = WARNING = 1
   ERROR = 2

   def __init__(self, msg, details, level):
       Exception.__init__(self, msg)
       self.level = level
       self.details = details
       self.msg = msg

class OpenFeedback(DeviceError):
    def __init__(self, msg):
        self.feedback_msg = msg
        DeviceError.__init__(self, msg)

    def custom_dialog(self, parent):
        '''
        If you need to show the user a custom dialog, instead of just
        displaying the feedback_msg, create and return it here.
        '''
        raise NotImplementedError

class InitialConnectionError(OpenFeedback):
    """ Errors detected during connection after detection but before open, for
    e.g. in the is_connected() method. """

class OpenFailed(ProtocolError):
    """ Raised when device cannot be opened this time. No retry is to be done.
        The device should continue to be polled for future opens. If the
        message is empty, no exception trace is produced. """

    def __init__(self, msg):
        ProtocolError.__init__(self, msg)
        self.show_me = bool(msg and msg.strip())

class DeviceBusy(ProtocolError):
    """ Raised when device is busy """
    def __init__(self, uerr=""):
        ProtocolError.__init__(self, "Device is in use by another application:"\
                               "\nUnderlying error:" + str(uerr))

class DeviceLocked(ProtocolError):
    """ Raised when device has been locked """
    def __init__(self):
        ProtocolError.__init__(self, "Device is locked")

class PacketError(ProtocolError):
    """ Errors with creating/interpreting packets """

class FreeSpaceError(ProtocolError):
    """ Errors caused when trying to put files onto an overcrowded device """

class ArgumentError(ProtocolError):
    """ Errors caused by invalid arguments to a public interface function """

class PathError(ArgumentError):
    """ When a user supplies an incorrect/invalid path """
    def __init__(self, msg, path=None):
        ArgumentError.__init__(self, msg)
        self.path = path

class ControlError(ProtocolError):
    """ Errors in Command/Response pairs while communicating with the device """
    def __init__(self, query=None, response=None, desc=None):
        self.query = query
        self.response = response
        ProtocolError.__init__(self, desc)

    def __str__(self):
        if self.query and self.response:
            return "Got unexpected response:\n" + \
           "query:\n"+str(self.query.query)+"\n"+\
           "expected:\n"+str(self.query.response)+"\n" +\
           "actual:\n"+str(self.response)
        if self.desc:
            return self.desc
        return "Unknown control error occurred"
