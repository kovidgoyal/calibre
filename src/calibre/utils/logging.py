#!/usr/bin/env python
# vim:fileencoding=utf-8
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid at kovidgoyal.net>

'A simplified logging system'

DEBUG = 0
INFO  = 1
WARN  = 2
ERROR = 3

import io
import sys
import traceback
from functools import partial
from threading import Lock

from calibre.prints import prints
from polyglot.builtins import as_unicode


class Stream(object):

    def __init__(self, stream=None):
        if stream is None:
            stream = io.StringIO()
        self.stream = stream
        self.encoding = getattr(self.stream, 'encoding', None) or 'utf-8'
        self._prints = partial(prints, file=self.stream)

    def write(self, text):
        self._prints(text, end='')

    def flush(self):
        self.stream.flush()

    def prints(self, level, *args, **kwargs):
        self._prints(*args, **kwargs)


class ANSIStream(Stream):

    def __init__(self, stream=sys.stdout):
        Stream.__init__(self, stream)
        self.color = {
            DEBUG: 'green',
            INFO: None,
            WARN: 'yellow',
            ERROR: 'red',
        }

    def prints(self, level, *args, **kwargs):
        from calibre.utils.terminal import ColoredStream
        with ColoredStream(self.stream, self.color[level]):
            self._prints(*args, **kwargs)

    def flush(self):
        self.stream.flush()


class FileStream(Stream):

    def __init__(self, stream=None):
        Stream.__init__(self, stream)

    def prints(self, level, *args, **kwargs):
        self._prints(*args, **kwargs)


class HTMLStream(Stream):

    color = {
        DEBUG: '<span style="color:green">',
        INFO: '<span>',
        WARN: '<span style="color:blue">',
        ERROR: '<span style="color:red">'
    }
    normal = '</span>'

    def __init__(self, stream=sys.stdout):
        Stream.__init__(self, stream)

    def prints(self, level, *args, **kwargs):
        self._prints(self.color[level], end='')
        self._prints(*args, **kwargs)
        self._prints(self.normal, end='')

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

        sep  = kwargs.get('sep', ' ')
        end  = kwargs.get('end', '\n')

        for arg in args:
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
        end = self.normal if self.data else ''
        return ''.join(self.data) + end

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

        self.debug = partial(self.print_with_flush, DEBUG)
        self.info  = partial(self.print_with_flush, INFO)
        self.warn  = self.warning = partial(self.print_with_flush, WARN)
        self.error = partial(self.print_with_flush, ERROR)

    def prints(self, level, *args, **kwargs):
        if level < self.filter_level:
            return
        for output in self.outputs:
            output.prints(level, *args, **kwargs)

    def print_with_flush(self, level, *args, **kwargs):
        if level < self.filter_level:
            return
        for output in self.outputs:
            output.prints(level, *args, **kwargs)
        self.flush()

    def exception(self, *args, **kwargs):
        limit = kwargs.pop('limit', None)
        self.print_with_flush(ERROR, *args, **kwargs)
        self.print_with_flush(DEBUG, traceback.format_exc(limit))

    def __call__(self, *args, **kwargs):
        self.info(*args, **kwargs)

    def __enter__(self):
        self.orig_filter_level = self.filter_level
        self.filter_level = self.ERROR + 100

    def __exit__(self, *args):
        self.filter_level = self.orig_filter_level

    def flush(self):
        for o in self.outputs:
            if hasattr(o, 'flush'):
                o.flush()

    def close(self):
        for o in self.outputs:
            if hasattr(o, 'close'):
                o.close()


class DevNull(Log):

    def __init__(self):
        Log.__init__(self, level=Log.ERROR)
        self.outputs = []


class ThreadSafeLog(Log):
    exception_traceback_level = Log.DEBUG

    def __init__(self, level=Log.INFO):
        Log.__init__(self, level=level)
        self._lock = Lock()

    def prints(self, *args, **kwargs):
        with self._lock:
            Log.prints(self, *args, **kwargs)

    def print_with_flush(self, *args, **kwargs):
        with self._lock:
            Log.print_with_flush(self, *args, **kwargs)

    def exception(self, *args, **kwargs):
        limit = kwargs.pop('limit', None)
        with self._lock:
            Log.print_with_flush(self, ERROR, *args, **kwargs)
            Log.print_with_flush(self, self.exception_traceback_level, traceback.format_exc(limit))


class ThreadSafeWrapper(Log):

    def __init__(self, other_log):
        Log.__init__(self, level=other_log.filter_level)
        self.outputs = list(other_log.outputs)
        self._lock = Lock()

    def prints(self, *args, **kwargs):
        with self._lock:
            Log.prints(self, *args, **kwargs)

    def print_with_flush(self, *args, **kwargs):
        with self._lock:
            Log.print_with_flush(self, *args, **kwargs)


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
        return ''.join(self.outputs[0].plain_text)

    def dump(self):
        return self.outputs[0].dump()

    def load(self, dump):
        return self.outputs[0].load(dump)

    def append_dump(self, dump):
        return self.outputs[0].append_dump(dump)


default_log = Log()
