#!/usr/bin/env python
# License: GPLv3 Copyright: 2009, Kovid Goyal <kovid at kovidgoyal.net>

# A simplified logging system

import io
import sys
import traceback
from contextlib import suppress
from enum import Enum
from functools import partial
from threading import Lock
from typing import IO, TYPE_CHECKING, Any, Final, TypedDict, Unpack

from calibre.prints import prints
from polyglot.builtins import as_unicode

DEBUG = 0
INFO = 1
WARN = 2
ERROR = 3

if TYPE_CHECKING:

    class PrintKwargs(TypedDict, total=False):
        sep: str
        end: str
        flush: bool

    class ExceptionKwargs(PrintKwargs, total=False):
        limit: int | None


class Stream:
    def __init__(self, stream: IO[str] | IO[bytes] | None = None) -> None:
        if stream is None:
            stream = io.StringIO()
        self.stream = stream
        self.encoding = getattr(self.stream, 'encoding', None) or 'utf-8'

    def write(self, text: str | bytes) -> None:
        self._prints(text, end='')

    def flush(self) -> None:
        with suppress(BrokenPipeError):
            # Don't fail if we were logging to a pipe and it got closed
            self.stream.flush()

    def prints(self, level: int, *args: object, **kwargs: Unpack[PrintKwargs]) -> None:
        self._prints(*args, **kwargs)

    def _prints(self, *args: object, **kwargs: Unpack[PrintKwargs]) -> None:
        prints(*args, **kwargs, file=self.stream)


class _Sentinel(Enum):
    stdout = object()


stdout_sentinel: Final = _Sentinel.stdout


class ANSIStream(Stream):
    def __init__(self, stream: IO[str] | IO[bytes] | _Sentinel | None = stdout_sentinel) -> None:
        if stream is stdout_sentinel:
            stream = sys.stdout
        Stream.__init__(self, stream)
        self.color = {
            DEBUG: 'green',
            INFO: None,
            WARN: 'yellow',
            ERROR: 'red',
        }

    def prints(self, level: int, *args: object, **kwargs: Unpack[PrintKwargs]) -> None:
        from calibre.utils.terminal import ColoredStream

        with ColoredStream(self.stream, self.color[level]):
            self._prints(*args, **kwargs)


class FileStream(Stream):
    def __init__(self, stream: IO[str] | IO[bytes] | None = None) -> None:
        Stream.__init__(self, stream)

    def prints(self, level: int, *args: object, **kwargs: Unpack[PrintKwargs]) -> None:
        self._prints(*args, **kwargs)


class HTMLStream(Stream):
    color = {
        DEBUG: '<span style="color:green">',
        INFO: '<span>',
        WARN: '<span style="color:blue">',
        ERROR: '<span style="color:red">',
    }
    normal = '</span>'

    def __init__(self, stream: IO[str] | IO[bytes] | _Sentinel | None = stdout_sentinel) -> None:
        if stream is stdout_sentinel:
            stream = sys.stdout
        Stream.__init__(self, stream)

    def prints(self, level: int, *args: object, **kwargs: Unpack[PrintKwargs]) -> None:
        self._prints(self.color[level], end='')
        self._prints(*args, **kwargs)
        self._prints(self.normal, end='')


class UnicodeHTMLStream(HTMLStream):
    def __init__(self) -> None:
        self.clear()

    def flush(self) -> None:
        pass

    def prints(self, level: int, *args: object, **kwargs: Unpack[PrintKwargs]) -> None:
        col = self.color[level]
        if col != self.last_col:
            if self.data:
                self.data.append(self.normal)
            self.data.append(col)
            self.last_col = col

        sep = kwargs.get('sep', ' ')
        end = kwargs.get('end', '\n')

        for arg in args:
            arg = as_unicode(arg)
            self.data.append(arg + sep)
            self.plain_text.append(arg + sep)
        self.data.append(end)
        self.plain_text.append(end)

    def clear(self) -> None:
        self.data: list[str] = []
        self.plain_text: list[str] = []
        self.last_col = self.color[INFO]

    @property
    def html(self) -> str:
        end = self.normal if self.data else ''
        return ''.join(self.data) + end

    def dump(self) -> list[Any]:
        return [self.data, self.plain_text, self.last_col]

    def load(self, dump: list[Any]) -> None:
        self.data, self.plain_text, self.last_col = dump

    def append_dump(self, dump: list[Any]) -> None:
        d, p, lc = dump
        self.data.extend(d)
        self.plain_text.extend(p)
        self.last_col = lc


class Log:
    DEBUG = DEBUG
    INFO = INFO
    WARN = WARN
    ERROR = ERROR

    def __init__(self, level: int = INFO) -> None:
        self.filter_level = level
        default_output = ANSIStream()
        self.outputs = [default_output]

        self.debug = partial(self.print_with_flush, DEBUG)
        self.info = partial(self.print_with_flush, INFO)
        self.warn = self.warning = partial(self.print_with_flush, WARN)
        self.error = partial(self.print_with_flush, ERROR)

    def prints(self, level: int, *args: object, **kwargs: Unpack[PrintKwargs]) -> None:
        if level < self.filter_level:
            return
        for output in self.outputs:
            output.prints(level, *args, **kwargs)

    def print_with_flush(self, level: int, *args: object, **kwargs: Unpack[PrintKwargs]) -> None:
        if level < self.filter_level:
            return
        for output in self.outputs:
            output.prints(level, *args, **kwargs)
        self.flush()

    def exception(self, *args: object, **kwargs: Unpack[ExceptionKwargs]) -> None:
        limit = kwargs.pop('limit', None)
        self.print_with_flush(ERROR, *args, **kwargs)
        self.print_with_flush(DEBUG, traceback.format_exc(limit))

    def __call__(self, *args: object, **kwargs: Unpack[PrintKwargs]) -> None:
        self.info(*args, **kwargs)

    def __enter__(self) -> None:
        self.orig_filter_level = self.filter_level
        self.filter_level = self.ERROR + 100

    def __exit__(self, *args: object) -> None:
        self.filter_level = self.orig_filter_level

    def flush(self) -> None:
        for o in self.outputs:
            if hasattr(o, 'flush'):
                o.flush()

    def close(self) -> None:
        for o in self.outputs:
            if (close := getattr(o, 'close', None)) is not None:
                close()


class DevNull(Log):
    def __init__(self) -> None:
        Log.__init__(self, level=Log.ERROR)
        self.outputs = []


class ThreadSafeLog(Log):
    exception_traceback_level = Log.DEBUG

    def __init__(self, level: int = Log.INFO) -> None:
        Log.__init__(self, level=level)
        self._lock = Lock()

    def prints(self, *args: *tuple[int, *tuple[object, ...]], **kwargs: Unpack[PrintKwargs]) -> None:  # ty: ignore[invalid-method-override]
        with self._lock:
            Log.prints(self, *args, **kwargs)

    def print_with_flush(self, *args: *tuple[int, *tuple[object, ...]], **kwargs: Unpack[PrintKwargs]) -> None:  # ty: ignore[invalid-method-override]
        with self._lock:
            Log.print_with_flush(self, *args, **kwargs)

    def exception(self, *args: object, **kwargs: Unpack[ExceptionKwargs]) -> None:
        limit = kwargs.pop('limit', None)
        with self._lock:
            Log.print_with_flush(self, ERROR, *args, **kwargs)
            Log.print_with_flush(self, self.exception_traceback_level, traceback.format_exc(limit))


class ThreadSafeWrapper(Log):
    def __init__(self, other_log: Log) -> None:
        Log.__init__(self, level=other_log.filter_level)
        self.outputs = list(other_log.outputs)
        self._lock = Lock()

    def prints(self, *args: *tuple[int, *tuple[object, ...]], **kwargs: Unpack[PrintKwargs]) -> None:  # ty: ignore[invalid-method-override]
        with self._lock:
            Log.prints(self, *args, **kwargs)

    def print_with_flush(self, *args: *tuple[int, *tuple[object, ...]], **kwargs: Unpack[PrintKwargs]) -> None:  # ty: ignore[invalid-method-override]
        with self._lock:
            Log.print_with_flush(self, *args, **kwargs)


class GUILog(ThreadSafeLog):
    """
    Logs in HTML and plain text as unicode. Ideal for display in a GUI context.
    """

    outputs: list[UnicodeHTMLStream]

    def __init__(self) -> None:
        ThreadSafeLog.__init__(self, level=self.DEBUG)
        self.outputs = [UnicodeHTMLStream()]

    def clear(self) -> None:
        self.outputs[0].clear()

    @property
    def html(self) -> str:
        return self.outputs[0].html

    @property
    def plain_text(self) -> str:
        return ''.join(self.outputs[0].plain_text)

    def dump(self) -> list[Any]:
        return self.outputs[0].dump()

    def load(self, dump: list[Any]) -> None:
        return self.outputs[0].load(dump)

    def append_dump(self, dump: list[Any]) -> None:
        return self.outputs[0].append_dump(dump)


default_log = Log()
