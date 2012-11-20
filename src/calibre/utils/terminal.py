#!/usr/bin/env python
# vim:fileencoding=UTF-8:ts=4:sw=4:sta:et:sts=4:fdm=marker:ai
from __future__ import (unicode_literals, division, absolute_import,
                        print_function)

__license__   = 'GPL v3'
__copyright__ = '2012, Kovid Goyal <kovid at kovidgoyal.net>'
__docformat__ = 'restructuredtext en'

import os, sys, re
from itertools import izip

from calibre.constants import iswindows

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
        force_ansi = os.environ.has_key('CALIBRE_FORCE_ANSI')
        if not self.isatty and force_ansi:
            self.isatty = True
        self.isansi = force_ansi or not iswindows
        self.set_console = None
        if not self.isansi:
            try:
                import msvcrt
                self.msvcrt = msvcrt
                self.file_handle = msvcrt.get_osfhandle(self.stream.fileno())
                from ctypes import windll
                self.set_console = windll.kernel32.SetConsoleTextAttribute
            except:
                pass

class ColoredStream(Detect):

    def __init__(self, stream=None, fg=None, bg=None, bold=False):
        super(ColoredStream, self).__init__(stream)
        self.fg, self.bg, self.bold = fg, bg, bold
        if self.set_console is not None:
            self.wval = to_flag(self.fg, self.bg, bold)

    def __enter__(self):
        if not self.isatty:
            return
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

    def __exit__(self, *args, **kwargs):
        if not self.isatty:
            return
        if not self.fg and not self.bg and not self.bold:
            return
        if self.isansi:
            self.stream.write(RESET)
        elif self.set_console is not None:
            self.set_console(self.file_handle, WCOLORS['white'])

class ANSIStream(Detect):

    ANSI_RE = re.compile(br'\033\[((?:\d|;)*)([a-zA-Z])')

    def __init__(self, stream=None):
        super(ANSIStream, self).__init__(stream)
        self.encoding = getattr(self.stream, 'encoding', 'utf-8')

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
        self.last_state = (None, None, False)
        cursor = 0
        for match in self.ANSI_RE.finditer(text):
            start, end = match.span()
            self.write_plain_text(text, cursor, start)
            self.convert_ansi(*match.groups())
            cursor = end
        self.write_plain_text(text, cursor, len(text))

    def write_plain_text(self, text, start, end):
        if start < end:
            self.stream.write(text[start:end])
            self.stream.flush()

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
        if command != b'm': return
        fg, bg, bold = self.last_state

        for param in params:
            if param in RCOLORS:
                fg = RCOLORS[param]
            elif param in RBACKGROUNDS:
                bg = RBACKGROUNDS[param]
            elif param == 1:
                bold = True
            elif param == 0:
                fg = 'white'
                bg, bold =  None, False

        self.last_state = (fg, bg, bold)
        if fg or bg or bold:
            self.set_console(self.file_handle, to_flag(fg, bg, bold))
        else:
            self.set_console(self.file_handle, WCOLORS['white'])

def geometry():
    try:
        import curses
        curses.setupterm()
    except:
        return 80, 80
    else:
        width = curses.tigetnum('cols') or 80
        height = curses.tigetnum('lines') or 80
        return width, height

def test():
    s = ANSIStream()

    text = [colored(t, fg=t)+'. '+colored(t, fg=t, bold=True)+'.' for t in
            ('red', 'yellow', 'green', 'white', 'cyan', 'magenta', 'blue',)]
    s.write('\n'.join(text))
    print()

