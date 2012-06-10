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

from calibre import isbytestring, force_unicode, as_unicode

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

    color = {
            DEBUG: '<span style="color:green">',
            INFO:'<span>',
            WARN: '<span style="color:blue">',
            ERROR: '<span style="color:red">'
            }
    normal = '</span>'

    def __init__(self, stream=sys.stdout):
        Stream.__init__(self, stream)

    def prints(self, level, *args, **kwargs):
        self.stream.write(self.color[level])
        kwargs['file'] = self.stream
        self._prints(*args, **kwargs)
        self.stream.write(self.normal)

    def flush(self):
        self.stream.flush()

class UnicodeHTMLStream(HTMLStream):

    def __init__(self):
        self.clear()

    def flush(self):
        pass

    def prints(self, level, *args, **kwargs):
        col = self.color[level]
        if col != self.last_col:
            if self.data:
                self.data.append(self.normal)
            self.data.append(col)
            self.last_col = col

        sep  = kwargs.get(u'sep', u' ')
        end  = kwargs.get(u'end', u'\n')

        for arg in args:
            if isbytestring(arg):
                arg = force_unicode(arg)
            elif not isinstance(arg, unicode):
                arg = as_unicode(arg)
            self.data.append(arg+sep)
            self.plain_text.append(arg+sep)
        self.data.append(end)
        self.plain_text.append(end)

    def clear(self):
        self.data = []
        self.plain_text = []
        self.last_col = self.color[INFO]

    @property
    def html(self):
        end = self.normal if self.data else u''
        return u''.join(self.data) + end

    def dump(self):
        return [self.data, self.plain_text, self.last_col]

    def load(self, dump):
        self.data, self.plain_text, self.last_col = dump

    def append_dump(self, dump):
        d, p, lc = dump
        self.data.extend(d)
        self.plain_text.extend(p)
        self.last_col = lc


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

class GUILog(ThreadSafeLog):

    '''
    Logs in HTML and plain text as unicode. Ideal for display in a GUI context.
    '''

    def __init__(self):
        ThreadSafeLog.__init__(self, level=self.DEBUG)
        self.outputs = [UnicodeHTMLStream()]

    def clear(self):
        self.outputs[0].clear()

    @property
    def html(self):
        return self.outputs[0].html

    @property
    def plain_text(self):
        return u''.join(self.outputs[0].plain_text)

    def dump(self):
        return self.outputs[0].dump()

    def load(self, dump):
        return self.outputs[0].load(dump)

    def append_dump(self, dump):
        return self.outputs[0].append_dump(dump)


default_log = Log()
