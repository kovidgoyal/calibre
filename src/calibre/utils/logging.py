from __future__ import with_statement
__license__ = 'GPL 3'
__copyright__ = '2009, Kovid Goyal <kovid@kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

'A simplified logging system'

DEBUG = 0
INFO  = 1
WARN  = 2
ERROR = 3

import sys, traceback, cStringIO
from functools import partial
from threading import RLock



class Stream(object):

    def __init__(self, stream=None):
        from calibre import prints
        self._prints = partial(prints, safe_encode=True)
        if stream is None:
            stream = cStringIO.StringIO()
        self.stream = stream

    def flush(self):
        self.stream.flush()


class ANSIStream(Stream):

    def __init__(self, stream=sys.stdout):
        Stream.__init__(self, stream)
        from calibre.utils.terminfo import TerminalController
        tc = TerminalController(stream)
        self.color = {
                      DEBUG: bytes(tc.GREEN),
                      INFO: bytes(''),
                      WARN: bytes(tc.YELLOW),
                      ERROR: bytes(tc.RED)
                      }
        self.normal = bytes(tc.NORMAL)

    def prints(self, level, *args, **kwargs):
        self.stream.write(self.color[level])
        kwargs['file'] = self.stream
        self._prints(*args, **kwargs)
        self.stream.write(self.normal)

    def flush(self):
        self.stream.flush()

class FileStream(Stream):

    def __init__(self, stream=None):
        Stream.__init__(self, stream)

    def prints(self, level, *args, **kwargs):
        kwargs['file'] = self.stream
        self._prints(*args, **kwargs)

class HTMLStream(Stream):

    def __init__(self, stream=sys.stdout):
        Stream.__init__(self, stream)
        self.color = {
                      DEBUG: '<span style="color:green">',
                      INFO:'<span>',
                      WARN: '<span style="color:yellow">',
                      ERROR: '<span style="color:red">'
                      }
        self.normal = '</span>'

    def prints(self, level, *args, **kwargs):
        self.stream.write(self.color[level])
        kwargs['file'] = self.stream
        self._prints(*args, **kwargs)
        self.stream.write(self.normal)

    def flush(self):
        self.stream.flush()

class Log(object):

    DEBUG = DEBUG
    INFO  = INFO
    WARN  = WARN
    ERROR = ERROR

    def __init__(self, level=INFO):
        self.filter_level = level
        default_output = ANSIStream()
        self.outputs = [default_output]

        self.debug = partial(self.prints, DEBUG)
        self.info  = partial(self.prints, INFO)
        self.warn  = self.warning = partial(self.prints, WARN)
        self.error = partial(self.prints, ERROR)


    def prints(self, level, *args, **kwargs):
        if level < self.filter_level:
            return
        for output in self.outputs:
            output.prints(level, *args, **kwargs)

    def exception(self, *args, **kwargs):
        limit = kwargs.pop('limit', None)
        self.prints(ERROR, *args, **kwargs)
        self.prints(DEBUG, traceback.format_exc(limit))

    def __call__(self, *args, **kwargs):
        self.prints(INFO, *args, **kwargs)

class ThreadSafeLog(Log):

    def __init__(self, level=Log.INFO):
        Log.__init__(self, level=level)
        self._lock = RLock()

    def prints(self, *args, **kwargs):
        with self._lock:
            Log.prints(self, *args, **kwargs)

default_log = Log()
