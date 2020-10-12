#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, sys, re

from calibre.prints import is_binary
from calibre.constants import iswindows
from polyglot.builtins import iteritems, range, zip

if iswindows:
    import ctypes.wintypes

    class CONSOLE_SCREEN_BUFFER_INFO(ctypes.Structure):
        _fields_ = [
            ('dwSize', ctypes.wintypes._COORD),
            ('dwCursorPosition', ctypes.wintypes._COORD),
            ('wAttributes', ctypes.wintypes.WORD),
            ('srWindow', ctypes.wintypes._SMALL_RECT),
            ('dwMaximumWindowSize', ctypes.wintypes._COORD)
        ]


def fmt(code):
    return '\033[%dm' % code


def polyglot_write(stream, is_binary, encoding, text):
    binary = isinstance(text, bytes)
    if binary:
        if is_binary:
            return stream.write(text)
        buffer = getattr(stream, 'buffer', None)
        if buffer is None:
            return stream.write(text.decode('utf-8', 'replace'))
        return buffer.write(text)
    if is_binary:
        text = text.encode(encoding, 'replace')
    return stream.write(text)


RATTRIBUTES = dict(
        zip(range(1, 9), (
            'bold',
            'dark',
            '',
            'underline',
            'blink',
            '',
            'reverse',
            'concealed'
            )
        ))
ATTRIBUTES = {v:fmt(k) for k, v in iteritems(RATTRIBUTES)}
del ATTRIBUTES['']

RBACKGROUNDS = dict(
        zip(range(41, 48), (
            'red',
            'green',
            'yellow',
            'blue',
            'magenta',
            'cyan',
            'white'
            ),
    ))
BACKGROUNDS = {v:fmt(k) for k, v in iteritems(RBACKGROUNDS)}

RCOLORS = dict(
        zip(range(31, 38), (
            'red',
            'green',
            'yellow',
            'blue',
            'magenta',
            'cyan',
            'white',
            ),
        ))
COLORS = {v:fmt(k) for k, v in iteritems(RCOLORS)}

RESET = fmt(0)


def colored(text, fg=None, bg=None, bold=False):
    prefix = []
    if fg is not None:
        prefix.append(COLORS[fg])
    if bg is not None:
        prefix.append(BACKGROUNDS[bg])
    if bold:
        prefix.append(ATTRIBUTES['bold'])
    prefix = ''.join(prefix)
    suffix = RESET
    if isinstance(text, bytes):
        prefix = prefix.encode('ascii')
        suffix = suffix.encode('ascii')
    return prefix + text + suffix


class Detect(object):

    def __init__(self, stream):
        self.stream = stream or sys.stdout
        self.is_binary = is_binary(self.stream)
        self.isatty = getattr(self.stream, 'isatty', lambda : False)()
        force_ansi = 'CALIBRE_FORCE_ANSI' in os.environ
        if not self.isatty and force_ansi:
            self.isatty = True
        self.isansi = force_ansi or not iswindows or (iswindows and sys.getwindowsversion().major >= 10)


class ColoredStream(Detect):

    def __init__(self, stream=None, fg=None, bg=None, bold=False):
        Detect.__init__(self, stream)
        self.fg, self.bg, self.bold = fg, bg, bold

    def cwrite(self, what):
        if self.is_binary:
            if not isinstance(what, bytes):
                what = what.encode('utf-8')
        else:
            if isinstance(what, bytes):
                what = what.decode('utf-8', 'replace')
        self.stream.write(what)

    def __enter__(self):
        if not self.isatty:
            return self
        if self.isansi:
            if self.bold:
                self.cwrite(ATTRIBUTES['bold'])
            if self.bg is not None:
                self.cwrite(BACKGROUNDS[self.bg])
            if self.fg is not None:
                self.cwrite(COLORS[self.fg])
        return self

    def __exit__(self, *args, **kwargs):
        if not self.isatty:
            return
        if not self.fg and not self.bg and not self.bold:
            return
        if self.isansi:
            self.cwrite(RESET)
            self.stream.flush()


class ANSIStream(Detect):

    ANSI_RE = r'\033\[((?:\d|;)*)([a-zA-Z])'

    def __init__(self, stream=None):
        super(ANSIStream, self).__init__(stream)
        self.encoding = getattr(self.stream, 'encoding', None) or 'utf-8'
        self._ansi_re_bin = self._ansi_re_unicode = None

    def ansi_re(self, binary=False):
        attr = '_ansi_re_bin' if binary else '_ansi_re_unicode'
        ans = getattr(self, attr)
        if ans is None:
            expr = self.ANSI_RE
            if binary:
                expr = expr.encode('ascii')
            ans = re.compile(expr)
            setattr(self, attr, ans)
        return ans

    def write(self, text):
        if not self.isatty:
            return self.strip_and_write(text)

        if self.isansi:
            return self.polyglot_write(text)

        return self.strip_and_write(text)

    def polyglot_write(self, text):
        return polyglot_write(self.stream, self.is_binary, self.encoding, text)

    def strip_and_write(self, text):
        binary = isinstance(text, bytes)
        pat = self.ansi_re(binary)
        repl = b'' if binary else ''
        return self.polyglot_write(pat.sub(repl, text))


def windows_terminfo():
    from ctypes import Structure, byref
    from ctypes.wintypes import SHORT, WORD

    class COORD(Structure):

        """struct in wincon.h"""
        _fields_ = [
            ('X', SHORT),
            ('Y', SHORT),
        ]

    class SMALL_RECT(Structure):

        """struct in wincon.h."""
        _fields_ = [
            ("Left", SHORT),
            ("Top", SHORT),
            ("Right", SHORT),
            ("Bottom", SHORT),
        ]

    class CONSOLE_SCREEN_BUFFER_INFO(Structure):

        """struct in wincon.h."""
        _fields_ = [
            ("dwSize", COORD),
            ("dwCursorPosition", COORD),
            ("wAttributes", WORD),
            ("srWindow", SMALL_RECT),
            ("dwMaximumWindowSize", COORD),
        ]
    csbi = CONSOLE_SCREEN_BUFFER_INFO()
    import msvcrt
    file_handle = msvcrt.get_osfhandle(sys.stdout.fileno())
    from ctypes import windll
    success = windll.kernel32.GetConsoleScreenBufferInfo(file_handle,
                                                         byref(csbi))
    if not success:
        raise Exception('stdout is not a console?')
    return csbi


def get_term_geometry():
    import fcntl, termios, struct

    def ioctl_GWINSZ(fd):
        try:
            return struct.unpack(b'HHHH', fcntl.ioctl(fd, termios.TIOCGWINSZ, b'\0'*8))[:2]
        except Exception:
            return None, None

    for f in (sys.stdin, sys.stdout, sys.stderr):
        lines, cols = ioctl_GWINSZ(f.fileno())
        if lines is not None:
            return lines, cols
    try:
        fd = os.open(os.ctermid(), os.O_RDONLY)
        try:
            lines, cols = ioctl_GWINSZ(fd)
            if lines is not None:
                return lines, cols
        finally:
            os.close(fd)
    except Exception:
        pass
    return None, None


def geometry():
    if iswindows:
        try:

            ti = windows_terminfo()
            return (ti.dwSize.X or 80, ti.dwSize.Y or 25)
        except:
            return 80, 25
    else:
        try:
            lines, cols = get_term_geometry()
            if lines is not None:
                return cols, lines
        except Exception:
            pass
        return 80, 25


def test():
    s = ANSIStream()

    text = [colored(t, fg=t)+'. '+colored(t, fg=t, bold=True)+'.' for t in
            ('red', 'yellow', 'green', 'white', 'cyan', 'magenta', 'blue',)]
    s.write('\n'.join(text))
    u = '\u041c\u0438\u0445\u0430\u0438\u043b fällen'
    print()
    s.write(u)
    print()
