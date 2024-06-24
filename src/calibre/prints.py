#!/usr/bin/env python
# License: GPL v3 Copyright: 2019, Kovid Goyal <kovid at kovidgoyal.net>

import io
import sys
import time

from polyglot.builtins import as_bytes, as_unicode


def is_binary(stream):
    mode = getattr(stream, 'mode', None)
    if mode:
        return 'b' in mode
    return not isinstance(stream, io.TextIOBase)


def prints(*a, **kw):
    ' Print either unicode or bytes to either binary or text mode streams '
    stream = kw.get('file', sys.stdout)
    if stream is None:
        return
    sep, end = kw.get('sep'), kw.get('end')
    if sep is None:
        sep = ' '
    if end is None:
        end = '\n'
    if is_binary(stream):
        encoding = getattr(stream, 'encoding', None) or 'utf-8'
        a = (as_bytes(x, encoding=encoding) for x in a)
        sep = as_bytes(sep)
        end = as_bytes(end)
    else:
        a = (as_unicode(x, errors='replace') for x in a)
        sep = as_unicode(sep)
        end = as_unicode(end)
    for i, x in enumerate(a):
        if sep and i != 0:
            stream.write(sep)
        stream.write(x)
    if end:
        stream.write(end)
    if kw.get('flush'):
        try:
            stream.flush()
        except Exception:
            pass

def debug_print(*args, **kw):
    '''
    Prints debug information to the console if debugging is enabled.

    This function prints a message prefixed with a timestamp showing the elapsed time
    since the first call to this function. The message is printed only if debugging is enabled.

    Parameters:
    *args : tuple
        Variable length argument list to be printed.
    **kw : dict
        Arbitrary keyword arguments to be passed to the `print` function.

    Attributes:
    base_time : float
        The timestamp of the first call to this function. Stored as an attribute of the function.

    Behavior:
    - On the first call, initializes `base_time` to the current time using `time.monotonic()`.
    - If `is_debugging()` returns True, prints the elapsed time since `base_time` along with the provided arguments.
    '''
    from calibre.constants import is_debugging

    # Get the base_time attribute, initializing it on the first call
    base_time = getattr(debug_print, 'base_time', None)
    if base_time is None:
        # Set base_time to the current monotonic time if it hasn't been set
        debug_print.base_time = base_time = time.monotonic()

    # Check if debugging is enabled
    if is_debugging():
        # Print the elapsed time and the provided arguments if debugging is enabled
        prints('DEBUG: %6.1f' % (time.monotonic() - base_time), *args, **kw)
