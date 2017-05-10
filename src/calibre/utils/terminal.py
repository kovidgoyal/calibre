#!/usr/bin/env python2
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, sys, re
from itertools import izip

from calibre.constants import iswindows

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
    return ('\033[%dm'%code).encode('ascii')


RATTRIBUTES = dict(
        izip(xrange(1, 9), (
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
ATTRIBUTES = {v:fmt(k) for k, v in RATTRIBUTES.iteritems()}
del ATTRIBUTES['']

RBACKGROUNDS = dict(
        izip(xrange(41, 48), (
            'red',
            'green',
            'yellow',
            'blue',
            'magenta',
            'cyan',
            'white'
            ),
    ))
BACKGROUNDS = {v:fmt(k) for k, v in RBACKGROUNDS.iteritems()}

RCOLORS = dict(
        izip(xrange(31, 38), (
            'red',
            'green',
            'yellow',
            'blue',
            'magenta',
            'cyan',
            'white',
            ),
        ))
COLORS = {v:fmt(k) for k, v in RCOLORS.iteritems()}

RESET = fmt(0)

if iswindows:
    # From wincon.h
    WCOLORS = {c:i for i, c in enumerate((
        'black', 'blue', 'green', 'cyan', 'red', 'magenta', 'yellow', 'white'))}

    def to_flag(fg, bg, bold):
        val = 0
        if bold:
            val |= 0x08
        if fg in WCOLORS:
            val |= WCOLORS[fg]
        if bg in WCOLORS:
            val |= (WCOLORS[bg] << 4)
        return val


def colored(text, fg=None, bg=None, bold=False):
    prefix = []
    if fg is not None:
        prefix.append(COLORS[fg])
    if bg is not None:
        prefix.append(BACKGROUNDS[bg])
    if bold:
        prefix.append(ATTRIBUTES['bold'])
    prefix = b''.join(prefix)
    suffix = RESET
    if isinstance(text, type(u'')):
        prefix = prefix.decode('ascii')
        suffix = suffix.decode('ascii')
    return prefix + text + suffix


class Detect(object):

    def __init__(self, stream):
        self.stream = stream or sys.stdout
        self.isatty = getattr(self.stream, 'isatty', lambda : False)()
        force_ansi = 'CALIBRE_FORCE_ANSI' in os.environ
        if not self.isatty and force_ansi:
            self.isatty = True
        self.isansi = force_ansi or not iswindows
        self.set_console = self.write_console = None
        self.is_console = False
        if not self.isansi:
            try:
                import msvcrt
                self.msvcrt = msvcrt
                self.file_handle = msvcrt.get_osfhandle(self.stream.fileno())
                from ctypes import windll, wintypes, byref, POINTER, WinDLL
                mode = wintypes.DWORD(0)
                f = windll.kernel32.GetConsoleMode
                f.argtypes, f.restype = [wintypes.HANDLE, POINTER(wintypes.DWORD)], wintypes.BOOL
                if f(self.file_handle, byref(mode)):
                    # Stream is a console
                    self.set_console = windll.kernel32.SetConsoleTextAttribute
                    kernel32 = WinDLL(b'kernel32', use_last_error=True)
                    self.write_console = kernel32.WriteConsoleW
                    self.write_console.argtypes = [wintypes.HANDLE, wintypes.c_wchar_p, wintypes.DWORD, POINTER(wintypes.DWORD), wintypes.LPVOID]
                    self.write_console.restype = wintypes.BOOL
                    kernel32.GetConsoleScreenBufferInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(CONSOLE_SCREEN_BUFFER_INFO)]
                    kernel32.GetConsoleScreenBufferInfo.restype = wintypes.BOOL
                    csbi = CONSOLE_SCREEN_BUFFER_INFO()
                    self.default_console_text_attributes = WCOLORS['white']
                    if kernel32.GetConsoleScreenBufferInfo(self.file_handle, byref(csbi)):
                        self.default_console_text_attributes = csbi.wAttributes
                    self.is_console = True
            except:
                pass

    def write_unicode_text(self, text, ignore_errors=False):
        ' Windows only method that writes unicode strings correctly to the windows console using the Win32 API '
        if self.is_console:
            from ctypes import wintypes, byref, c_wchar_p
            written = wintypes.DWORD(0)
            text = text.replace('\0', '')
            chunk = len(text)
            while text:
                t, text = text[:chunk], text[chunk:]
                wt = c_wchar_p(t)
                # Use the fact that len(t) == wcslen(wt) in python 2.7 on
                # windows where the python unicode type uses UTF-16
                if not self.write_console(self.file_handle, wt, len(t), byref(written), None):
                    # Older versions of windows can fail to write large strings
                    # to console with WriteConsoleW (seen it happen on Win XP)
                    import winerror
                    err = ctypes.get_last_error()
                    if err == winerror.ERROR_NOT_ENOUGH_MEMORY and chunk >= 128:
                        # Retry with a smaller chunk size (give up if chunk < 128)
                        chunk = chunk // 2
                        text = t + text
                        continue
                    if err == winerror.ERROR_GEN_FAILURE:
                        # On newer windows, this happens when trying to write
                        # non-ascii chars to the console and the console is set
                        # to use raster fonts (the default). In this case
                        # rather than failing, write an informative error
                        # message and the asciized version of the text.
                        print ('Non-ASCII text detected. You must set your Console\'s font to'
                               ' Lucida Console or Consolas or some other TrueType font to see this text', file=self.stream, end=' -- ')
                        from calibre.utils.filenames import ascii_text
                        print (ascii_text(t + text), file=self.stream, end='')
                        continue
                    if not ignore_errors:
                        raise ctypes.WinError(err)


class ColoredStream(Detect):

    def __init__(self, stream=None, fg=None, bg=None, bold=False):
        Detect.__init__(self, stream)
        self.fg, self.bg, self.bold = fg, bg, bold
        if self.set_console is not None:
            self.wval = to_flag(self.fg, self.bg, bold)
            if not self.bg:
                self.wval |= self.default_console_text_attributes & 0xF0

    def __enter__(self):
        if not self.isatty:
            return self
        if self.isansi:
            if self.bold:
                self.stream.write(ATTRIBUTES['bold'])
            if self.bg is not None:
                self.stream.write(BACKGROUNDS[self.bg])
            if self.fg is not None:
                self.stream.write(COLORS[self.fg])
        elif self.set_console is not None:
            if self.wval != 0:
                self.set_console(self.file_handle, self.wval)
        return self

    def __exit__(self, *args, **kwargs):
        if not self.isatty:
            return
        if not self.fg and not self.bg and not self.bold:
            return
        if self.isansi:
            self.stream.write(RESET)
            self.stream.flush()
        elif self.set_console is not None:
            self.set_console(self.file_handle, self.default_console_text_attributes)


class ANSIStream(Detect):

    ANSI_RE = re.compile(br'\033\[((?:\d|;)*)([a-zA-Z])')

    def __init__(self, stream=None):
        super(ANSIStream, self).__init__(stream)
        self.encoding = getattr(self.stream, 'encoding', 'utf-8') or 'utf-8'
        self.last_state = (None, None, False)

    def write(self, text):
        if isinstance(text, type(u'')):
            text = text.encode(self.encoding, 'replace')

        if not self.isatty:
            return self.strip_and_write(text)

        if self.isansi:
            return self.stream.write(text)

        if not self.isansi and self.set_console is None:
            return self.strip_and_write(text)

        self.write_and_convert(text)

    def strip_and_write(self, text):
        self.stream.write(self.ANSI_RE.sub(b'', text))

    def write_and_convert(self, text):
        '''
        Write the given text to our wrapped stream, stripping any ANSI
        sequences from the text, and optionally converting them into win32
        calls.
        '''
        cursor = 0
        for match in self.ANSI_RE.finditer(text):
            start, end = match.span()
            self.write_plain_text(text, cursor, start)
            self.convert_ansi(*match.groups())
            cursor = end
        self.write_plain_text(text, cursor, len(text))
        self.set_console(self.file_handle, self.default_console_text_attributes)
        self.stream.flush()

    def write_plain_text(self, text, start, end):
        if start < end:
            text = text[start:end]
            if self.is_console and isinstance(text, bytes):
                try:
                    utext = text.decode(self.encoding)
                except ValueError:
                    pass
                else:
                    return self.write_unicode_text(utext)
            self.stream.write(text)

    def convert_ansi(self, paramstring, command):
        params = self.extract_params(paramstring)
        self.call_win32(command, params)

    def extract_params(self, paramstring):
        def split(paramstring):
            for p in paramstring.split(b';'):
                if p:
                    yield int(p)
        return tuple(split(paramstring))

    def call_win32(self, command, params):
        if command != b'm':
            return
        fg, bg, bold = self.last_state

        for param in params:
            if param in RCOLORS:
                fg = RCOLORS[param]
            elif param in RBACKGROUNDS:
                bg = RBACKGROUNDS[param]
            elif param == 1:
                bold = True
            elif param == 0:
                fg, bg, bold = None, None, False

        self.last_state = (fg, bg, bold)
        if fg or bg or bold:
            val = to_flag(fg, bg, bold)
            if not bg:
                val |= self.default_console_text_attributes & 0xF0
            self.set_console(self.file_handle, val)
        else:
            self.set_console(self.file_handle, self.default_console_text_attributes)


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
    u = u'\u041c\u0438\u0445\u0430\u0438\u043b fällen'
    print()
    s.write_unicode_text(u)
    print()
